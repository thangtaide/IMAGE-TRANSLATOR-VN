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
IMAGING_REVISION = 'readable-outline-layout-v4'


class TextRemovalError(ValueError):
    code = 'TEXT_REMOVAL_FAILED'


class TextLayoutError(LayoutError):
    code = 'LAYOUT_UNFIT'


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


def _outlined_glyph_mask(rgb, polygon, scale, image_edges):
    """Local light seeds plus dark outline/shadow; never fill a whole OCR box."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    light = ((gray >= 200) & (rgb.max(2).astype(int)-rgb.min(2) <= 55)).astype(np.uint8)*255
    dark = (gray <= 90).astype(np.uint8)*255
    radius = max(3, min(8, round(scale*.25)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*radius+1,2*radius+1))
    support_radius = max(3, min(8, round(scale*.18)))
    support = cv2.dilate(polygon, cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
        (2*support_radius+1,2*support_radius+1)))
    light[support == 0] = 0
    near_dark = cv2.dilate(dark, kernel)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(light, connectivity=8)
    selected = np.zeros(gray.shape, np.uint8)
    support_pixels = np.count_nonzero(support)
    for label in range(1,count):
        x,y,width,height,area = stats[label]
        crosses = ((x == 0 and not image_edges[0]) or (y == 0 and not image_edges[1]) or
            (x+width == gray.shape[1] and not image_edges[2]) or
            (y+height == gray.shape[0] and not image_edges[3]))
        if crosses or area < 3 or height > scale*1.5 or area > support_pixels*.65:
            continue
        component = labels == label
        if np.count_nonzero(polygon[component]) < area*.35 or np.count_nonzero(near_dark[component]) < area*.55:
            continue
        contours,_ = cv2.findContours(component.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filled = np.zeros(gray.shape,np.uint8)
        cv2.drawContours(filled,contours,-1,255,cv2.FILLED)
        halo = cv2.dilate(filled,kernel)
        filled[(halo > 0) & (gray <= 110)] = 255
        selected |= cv2.dilate(filled,np.ones((3,3),np.uint8))
    return selected


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
        scale = max(1,min(x1-x0,y1-y0))
        margin = max(5,min(24,round(scale*.35)))
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
        selected |= _outlined_glyph_mask(rgb[y0:y1,x0:x1],polygon_mask,scale,
            (x0 == 0,y0 == 0,x1 == rgb.shape[1],y1 == rgb.shape[0]))
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
    for region in regions:
        x0,y0,x1,y1 = region.box
        if not np.any(mask[max(0,y0):min(mask.shape[0],y1+1), max(0,x0):min(mask.shape[1],x1+1)]):
            raise TextRemovalError('TEXT_REMOVAL_FAILED: mask rỗng trong vùng OCR; không render chồng chữ gốc.')
    if options.erase_mode == 'white':
        rgb[mask > 0] = 255
    else:
        try:
            rgb = cv2.inpaint(rgb, mask, 3, cv2.INPAINT_TELEA)
        except cv2.error as exc:
            raise TextRemovalError('TEXT_REMOVAL_FAILED: inpainting thất bại; không render bản dịch.') from exc
    if rgb is None or rgb.shape != (image.height,image.width,3) or rgb.dtype != np.uint8:
        raise TextRemovalError('TEXT_REMOVAL_FAILED: ảnh sau inpaint không hợp lệ.')
    result = Image.fromarray(rgb)
    if image.mode == 'RGBA':
        result.putalpha(image.getchannel('A'))
    return result


class TextRenderer:
    def __init__(self, options: Options):
        self.options = options
        self.font_path = Path(options.font) if options.font else default_font()
        self.last_layout = []
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

    @staticmethod
    def _intersects(a, b):
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    def plan_layout(self, image_size, regions, translations):
        """Resolve intersecting OCR boxes before drawing any text.

        Close groups over their union rectangle so a merged group cannot cover
        another region. Flow each distinct translation exactly once within that
        existing text band, preserving IDs/text upstream and avoiding new art.
        """
        if len(regions) != len(translations):
            raise ValueError('Số vùng OCR không khớp số bản dịch')
        draw = ImageDraw.Draw(Image.new('RGB',(1,1)))
        groups = []
        duplicates = {}
        seen = {}
        for index,(region,text) in enumerate(zip(regions,translations)):
            if not text.strip():
                raise TextLayoutError('LAYOUT_UNFIT: bản dịch rỗng; không xuất ảnh đã xóa chữ')
            x0, y0, x1, y1 = region.box
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(image_size[0], x1), min(image_size[1], y1)
            if x1 <= x0 or y1 <= y0:
                raise TextLayoutError('LAYOUT_UNFIT: vùng chữ nằm ngoài ảnh hoặc không có diện tích')
            key = (tuple(tuple(point) for point in region.polygon),region.text,text)
            if region.text and key in seen:
                duplicates[index] = seen[key]
                continue
            seen[key] = index
            groups.append({'indices':[index],'box':[x0,y0,x1,y1]})
        changed = True
        while changed:
            changed = False
            for i in range(len(groups)):
                for j in range(i+1,len(groups)):
                    a,b = groups[i],groups[j]
                    if self._intersects(a['box'],b['box']):
                        x,y = a['box'],b['box']
                        a['box'] = [min(x[0],y[0]),min(x[1],y[1]),max(x[2],y[2]),max(x[3],y[3])]
                        a['indices'] += b['indices']
                        groups.pop(j)
                        changed = True
                        break
                if changed:
                    break
        plans = []
        for group in groups:
            indices = sorted(group['indices'])
            text = '  '.join(translations[index].strip() for index in indices)
            x0,y0,x1,y1 = group['box']
            width, height = x1-x0, y1-y0
            occupied = sum(max(0,min(image_size[0],regions[i].box[2])-max(0,regions[i].box[0])) *
                           max(0,min(image_size[1],regions[i].box[3])-max(0,regions[i].box[1])) for i in indices)
            if len(indices) > 1 and occupied < width*height*.6:
                raise TextLayoutError('LAYOUT_UNFIT: nhóm box tạo vùng trống quá lớn; không mở chữ qua vùng hình quan trọng')
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
                raise TextLayoutError(f'LAYOUT_UNFIT: bản dịch nhóm {indices} không vừa ({width}×{height}px) ở cỡ tối thiểu {self.options.font_min}; không cắt nội dung hoặc vẽ chồng.')
            font, wrapped, spacing, bbox = fit
            x = x0 - bbox[0] + ((width-(bbox[2]-bbox[0]))/2 if self.options.alignment == 'center' else 0)
            y = y0 - bbox[1] + (height-(bbox[3]-bbox[1]))/2
            if ''.join(wrapped.split()) != ''.join(text.split()):
                raise TextLayoutError('LAYOUT_UNFIT: word wrap làm thay đổi nội dung')
            plans.append(dict(region_indices=indices, duplicate_indices=[i for i,v in duplicates.items() if v in indices],
                box=group['box'],paint_box=[x+bbox[0],y+bbox[1],x+bbox[2],y+bbox[3]],
                text=text,wrapped=wrapped,font_size=font.size,spacing=spacing,origin=[x,y]))
        for i,plan in enumerate(plans):
            if any(self._intersects(plan['paint_box'],p['paint_box']) for p in plans[i+1:]):
                raise TextLayoutError('LAYOUT_UNFIT: vùng đặt chữ giao nhau sau bố trí')
        return plans

    def render(self, image: Image.Image, regions: list[OCRResult], translations: list[str]) -> Image.Image:
        self.last_layout = []
        plans = self.plan_layout(image.size,regions,translations)
        output = image.copy()
        draw = ImageDraw.Draw(output)
        for plan in plans:
            font = ImageFont.truetype(str(self.font_path),plan['font_size'])
            draw.multiline_text(tuple(plan['origin']),plan['wrapped'],font=font,fill=self.options.foreground,
                spacing=plan['spacing'],align=self.options.alignment,stroke_width=self.options.stroke,
                stroke_fill='white' if self.options.foreground == 'black' else 'black')
        self.last_layout = plans
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
