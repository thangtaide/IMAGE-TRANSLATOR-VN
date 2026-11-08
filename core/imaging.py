from __future__ import annotations

import os
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from core.paths import ASSETS
from core.types import LayoutError, OCRResult, Options

SUPPORTED = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}


def default_font() -> Path:
    bundled = ASSETS / 'fonts/NotoSans-Regular.ttf'
    if bundled.is_file():
        return bundled
    # Runtime use of a Windows-installed font; never redistributed with the app.
    for path in [Path('C:/Windows/Fonts/arial.ttf'), Path('C:/Windows/Fonts/segoeui.ttf')]:
        if path.is_file():
            return path
    raise FileNotFoundError('Thiếu font. Cài Noto Sans bằng scripts/download_assets.py hoặc chọn TTF trong Cài đặt.')


def open_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        if image.width * image.height > 65_000_000:
            raise MemoryError('Ảnh vượt 65 triệu pixel; chia ảnh trước khi xử lý để giới hạn RAM.')
        if getattr(image, 'n_frames', 1) > 1:
            raise ValueError('Ảnh động không được hỗ trợ; xuất từng khung thành ảnh tĩnh.')
        # Keep encoded dimensions: do not apply EXIF rotation silently.
        image.load()
        return image.convert('RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB')


def build_mask(rgb: np.ndarray, regions: list[OCRResult], expansion: int = 1) -> np.ndarray:
    """Include glyph tails outside tight OCR boxes, protecting connected borders.

    Connected components crossing an internal ROI edge are treated as artwork.
    This is conservative on textured backgrounds; preview/custom masks remain
    necessary where character strokes and artwork are physically connected.
    """
    mask = np.zeros(rgb.shape[:2], dtype=np.uint8)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    for region in regions:
        x0, y0, x1, y1 = region.box
        # OCR often trims antialiasing, radicals and punctuation at the edges.
        margin = max(3, min(16, int(min(x1-x0, y1-y0) * .18)))
        x0, y0 = max(0, x0-margin), max(0, y0-margin)
        x1, y1 = min(rgb.shape[1], x1+margin+1), min(rgb.shape[0], y1+margin+1)
        patch = gray[y0:y1, x0:x1]
        if patch.size == 0:
            continue
        polygon_mask = np.zeros(patch.shape, dtype=np.uint8)
        polygon = np.round(region.polygon).astype(np.int32) - np.array([x0, y0], dtype=np.int32)
        cv2.fillPoly(polygon_mask, [polygon], 255)
        threshold, dark = cv2.threshold(patch, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        rim = np.concatenate([patch[0], patch[-1], patch[:, 0], patch[:, -1]])
        glyph = dark if np.median(rim) > threshold else cv2.bitwise_not(dark)
        near = cv2.dilate(polygon_mask, np.ones((margin*2+1, margin*2+1), np.uint8))
        _, labels, stats, _ = cv2.connectedComponentsWithStats(glyph, connectivity=8)
        selected = np.zeros(patch.shape, dtype=np.uint8)
        protected = np.zeros(patch.shape, dtype=np.uint8)
        for label in range(1, len(stats)):
            left, top, width, height, area = stats[label]
            component = labels == label
            crosses = ((left == 0 and x0 > 0) or (top == 0 and y0 > 0) or
                       (left+width == patch.shape[1] and x1 < rgb.shape[1]) or
                       (top+height == patch.shape[0] and y1 < rgb.shape[0]))
            if crosses:
                protected[component] = 255
            elif np.any(near[component]):
                # Keep whole components so a tight polygon cannot clip a stroke.
                selected[component] = 255
        if expansion:
            k = max(0, min(8, expansion)) * 2 + 1
            selected = cv2.dilate(selected, np.ones((k, k), np.uint8))
        # Also guard the antialiased edge of a detected border against dilation.
        protected = cv2.dilate(protected, np.ones((3, 3), np.uint8))
        selected[protected > 0] = 0
        mask[y0:y1, x0:x1] |= selected
    return mask


def erase_text(image: Image.Image, regions: list[OCRResult], options: Options) -> Image.Image:
    rgb = np.array(image.convert('RGB'))
    if not regions:
        return image.copy()
    mask = build_mask(rgb, regions, options.mask_expand)
    if options.erase_mode == 'custom':
        if not options.mask_path:
            raise ValueError('Chọn ảnh mask tùy chỉnh trong Cài đặt')
        with Image.open(options.mask_path) as custom:
            if custom.size != image.size:
                raise ValueError('Kích thước mask phải trùng ảnh nguồn')
            mask = np.array(custom.convert('L'))
    if options.erase_mode == 'white':
        rgb[mask > 0] = 255
    else:
        rgb = cv2.inpaint(rgb, mask, 3, cv2.INPAINT_TELEA)
    result = Image.fromarray(rgb)
    if image.mode == 'RGBA':
        result.putalpha(image.getchannel('A'))
    return result


class TextRenderer:
    def __init__(self, options: Options):
        self.options = options
        self.font_path = Path(options.font) if options.font else default_font()
        if not self.font_path.is_file():
            raise FileNotFoundError(f'Không tìm thấy font: {self.font_path}')

    def _wrap(self, text: str, font: ImageFont.FreeTypeFont, width: int, draw: ImageDraw.ImageDraw) -> str | None:
        lines = []
        for paragraph in text.split('\n'):
            line = ''
            for word in paragraph.split():
                candidate = (line + ' ' + word).strip()
                if draw.textlength(candidate, font=font) + 2*self.options.stroke <= width:
                    line = candidate
                else:
                    if line:
                        lines.append(line)
                    if draw.textlength(word, font=font) + 2*self.options.stroke > width:
                        return None
                    line = word
            lines.append(line)
        return '\n'.join(lines)

    def render(self, image: Image.Image, regions: list[OCRResult], translations: list[str]) -> Image.Image:
        if len(regions) != len(translations):
            raise ValueError('Số vùng OCR không khớp số bản dịch')
        output = image.copy()
        draw = ImageDraw.Draw(output)
        for region, text in zip(regions, translations):
            if not text.strip():
                raise LayoutError('Bản dịch rỗng; không xuất ảnh đã xóa chữ')
            x0, y0, x1, y1 = region.box
            # Use only original OCR bounds; never silently cover neighboring art.
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(image.width, x1), min(image.height, y1)
            width, height = x1-x0, y1-y0
            fit = None
            for size in range(self.options.font_max, self.options.font_min-1, -1):
                font = ImageFont.truetype(str(self.font_path), size)
                wrapped = self._wrap(text, font, width, draw)
                if wrapped is None:
                    continue
                spacing = max(0, min(self.options.line_spacing, size // 4))
                bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing,
                                              align=self.options.alignment, stroke_width=self.options.stroke)
                if bbox[2]-bbox[0] <= width and bbox[3]-bbox[1] <= height:
                    fit = font, wrapped, spacing, bbox
                    break
            if fit is None:
                raise LayoutError(f'Bản dịch vùng {region.reading_order+1} không vừa ({width}×{height}px) ở cỡ tối thiểu {self.options.font_min}. Giảm cỡ chữ hoặc sửa vùng; không cắt nội dung.')
            font, wrapped, spacing, bbox = fit
            x = x0 - bbox[0] + ((width-(bbox[2]-bbox[0]))/2 if self.options.alignment == 'center' else 0)
            y = y0 - bbox[1] + (height-(bbox[3]-bbox[1]))/2
            draw.multiline_text((x, y), wrapped, font=font, fill=self.options.foreground,
                                spacing=spacing, align=self.options.alignment, stroke_width=self.options.stroke,
                                stroke_fill='white' if self.options.foreground == 'black' else 'black')
        if image.mode == 'RGBA':
            output.putalpha(image.getchannel('A'))
        return output


def atomic_save(image: Image.Image, destination: Path, quality: int = 95, *, overwrite: bool = True,
                before_publish=None) -> list[str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    formats = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP', '.bmp': 'BMP'}
    fmt = formats[destination.suffix.lower()]
    warnings = []
    if image.mode == 'RGBA' and fmt in ('JPEG', 'BMP'):
        background = Image.new('RGB', image.size, 'white')
        background.paste(image, mask=image.getchannel('A'))
        image = background
        warnings.append('JPEG/BMP không giữ alpha; đã ghép lên nền trắng. Chọn PNG/WEBP để giữ alpha.')
    handle, temp_name = tempfile.mkstemp(prefix='.itvn-', suffix=destination.suffix, dir=destination.parent)
    os.close(handle)
    temp = Path(temp_name)
    try:
        kwargs = {'quality': quality} if fmt in ('JPEG', 'WEBP') else {}
        if fmt == 'JPEG':
            kwargs['subsampling'] = 0
        image.save(temp, format=fmt, **kwargs)
        with Image.open(temp) as check:
            check.load()
            if check.size != image.size:
                raise IOError('Ảnh xuất không đúng độ phân giải')
        if before_publish:
            before_publish(temp)
        if overwrite:
            os.replace(temp, destination)
        elif os.name == 'nt':
            os.rename(temp, destination)
        else:
            os.link(temp, destination)
    finally:
        temp.unlink(missing_ok=True)
    return warnings
