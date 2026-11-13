from __future__ import annotations

import os
import math
import re
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from core.paths import ASSETS
from core.types import LayoutError, OCRResult, Options

SUPPORTED = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
IMAGING_REVISION = 'readable-outline-layout-v5-corner-trim'


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

    def _fit_text(self, text, width, height, draw, *, minimum_only=False, alternate_wrap=False):
        sizes = (self.options.font_min,) if minimum_only else range(
            self.options.font_max, self.options.font_min-1, -1)
        for size in sizes:
            font = ImageFont.truetype(str(self.font_path), size)
            spacing = max(0, min(self.options.line_spacing, size // 4))
            widths = (width, max(1,int(width*.9)), max(1,int(width*.8))) if alternate_wrap else (width,)
            for wrap_width in dict.fromkeys(widths):
                wrapped = self._wrap(text, font, wrap_width, draw)
                if wrapped is None:
                    continue
                bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing,
                                              align=self.options.alignment, stroke_width=self.options.stroke)
                if bbox[2]-bbox[0] <= width and bbox[3]-bbox[1] <= height:
                    return font, wrapped, spacing, bbox
        return None

    def _expand_on_flat_background(self, image, source_box, text, obstacles, draw):
        """Bounded, pixel-checked fallback; never infer free space from box geometry.

        Only new pixels in the same local, nearly flat connected background as
        the erased source box are eligible. Strong edges, texture, alpha and
        other OCR/protected/planned rectangles stop growth. Accepted old layouts
        never enter this method.
        """
        x0,y0,x1,y1 = source_box
        width,height = x1-x0,y1-y0
        dx = min(96,max(12,math.ceil(width*.4)))
        dy = min(64,max(8,height*2))
        roi = [max(0,x0-dx),max(0,y0-dy),min(image.width,x1+dx),min(image.height,y1+dy)]
        if (roi[2]-roi[0])*(roi[3]-roi[1]) > 2_000_000:
            return None
        patch = np.array(image.crop(tuple(roi)).convert('RGBA'))
        rgb = patch[:,:,:3]
        sx0,sy0,sx1,sy1 = x0-roi[0],y0-roi[1],x1-roi[0],y1-roi[1]
        original = rgb[sy0:sy1,sx0:sx1]
        reference = np.median(original.reshape(-1,3),axis=0)
        delta = np.max(np.abs(rgb.astype(np.float32)-reference),axis=2)
        gray = cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY).astype(np.float32)
        gx = cv2.Sobel(gray,cv2.CV_32F,1,0,borderType=cv2.BORDER_REPLICATE)
        gy = cv2.Sobel(gray,cv2.CV_32F,0,1,borderType=cv2.BORDER_REPLICATE)
        flat = (delta<=10) & (np.maximum(np.abs(gx),np.abs(gy))<=16) & (patch[:,:,3]==255)
        _,labels = cv2.connectedComponents(flat.astype(np.uint8),connectivity=4)
        counts = np.bincount(labels[sy0:sy1,sx0:sx1].ravel())
        counts[0] = 0
        component = int(np.argmax(counts))
        if counts[component] < width*height*.85:
            return None
        unsafe = (labels!=component).astype(np.uint8)
        # Original pixels are already allocated to this OCR group. Only added
        # pixels must be uniformly safe; do not classify the entire image blank.
        unsafe[sy0:sy1,sx0:sx1] = 0
        integral = cv2.integral(unsafe)

        def is_safe(box):
            if any(self._intersects(box,other) for other in obstacles):
                return False
            a,b,c,d = box[0]-roi[0],box[1]-roi[1],box[2]-roi[0],box[3]-roi[1]
            return integral[d,c]-integral[b,c]-integral[d,a]+integral[b,a] == 0

        return self._fit_expanded_frame(source_box,text,draw,roi,is_safe)

    def _expand_over_background(self, image, source_box, text, obstacles, draw):
        """Last resort authorized to cover artwork, never other text or alpha.

        Search to image edges instead of the conservative flat-background ROI.
        Keep the original anchor inside the frame and prefer a readable, local
        frame over pushing the type to font_max across the whole image.
        """
        alpha = image.getchannel('A') if image.mode == 'RGBA' else None
        if alpha is not None and alpha.getextrema() == (255,255):
            alpha = None

        def is_safe(box):
            return (not any(self._intersects(box,other) for other in obstacles) and
                (alpha is None or alpha.crop(box).getextrema() == (255,255)))

        preferred_size = min(self.options.font_max,max(self.options.font_min,
            min(20,round((source_box[3]-source_box[1])*.65))))
        return self._fit_expanded_frame(source_box,text,draw,
            [0,0,image.width,image.height],is_safe,max_size=preferred_size)

    def _fit_expanded_frame(self, source_box, text, draw, roi, is_safe, *, max_size=None):
        x0,y0,x1,y1 = source_box
        width,height = x1-x0,y1-y0

        def dimensions(original,maximum):
            steps = (0,2,4,8,12,16,24,32,48,64,96,128,192,256,384,512,768,1024,maximum-original)
            return sorted({min(maximum,original+n) for n in steps if n>=0})

        def positions(lo,hi,extent,roi_lo,roi_hi):
            return {max(roi_lo,min(roi_hi-extent,int(start)))
                for start in ((lo+hi-extent)//2,lo,hi-extent)}

        candidates = set()
        for w in dimensions(width,roi[2]-roi[0]):
            for h in dimensions(height,roi[3]-roi[1]):
                if w==width and h==height:
                    continue
                for x in positions(x0,x1,w,roi[0],roi[2]):
                    for y in positions(y0,y1,h,roi[1],roi[3]):
                        box = (x,y,x+w,y+h)
                        if x<=x0 and y<=y0 and x+w>=x1 and y+h>=y1 and is_safe(box):
                            candidates.add(box)
        # Prefer readable type, then the least growth/drift, then fewer lines.
        ranked = sorted(candidates,key=lambda b:((b[2]-b[0])*(b[3]-b[1]),
            abs(b[0]+b[2]-x0-x1)+abs(b[1]+b[3]-y0-y1),b))
        if not ranked:
            return None
        for size in range(max_size or self.options.font_max,self.options.font_min-1,-1):
            font = ImageFont.truetype(str(self.font_path),size)
            spacing = max(0,min(self.options.line_spacing,size//4))
            wrapped_cache = {}
            fitting = []
            for box in ranked:
                w,h = box[2]-box[0]-2,box[3]-box[1]-2  # Raster safety padding.
                for wrap_width in dict.fromkeys((w,max(1,int(w*.9)),max(1,int(w*.8)))):
                    if wrap_width not in wrapped_cache:
                        wrapped = self._wrap(text,font,wrap_width,draw)
                        bbox = (draw.multiline_textbbox((0,0),wrapped,font=font,spacing=spacing,
                            align=self.options.alignment,stroke_width=self.options.stroke) if wrapped is not None else None)
                        wrapped_cache[wrap_width] = (wrapped,bbox)
                    wrapped,bbox = wrapped_cache[wrap_width]
                    if bbox is not None and bbox[2]-bbox[0]<=w and bbox[3]-bbox[1]<=h:
                        score = ((box[2]-box[0])*(box[3]-box[1]),
                            abs(box[0]+box[2]-x0-x1)+abs(box[1]+box[3]-y0-y1),wrapped.count('\n'),box)
                        fitting.append((score,box,(font,wrapped,spacing,bbox)))
            if fitting:
                _,box,fit = min(fitting,key=lambda entry:entry[0])
                return list(box),fit
        return None

    def _separate_sparse_corners(self, group, regions, translations, image_size, draw):
        """Recover only small corner collisions within the original OCR boxes.

        No expansion or text changes. Keep at least 85% of each box, move an
        edge at most 8px, and require every complete target to fit at font_min.
        Dense/valid groups never enter this fallback; complex overlaps fail.
        """
        indices = sorted(group['indices'])
        if not 2 <= len(indices) <= 8:
            return None
        originals = [[max(0, regions[i].box[0]), max(0, regions[i].box[1]),
                      min(image_size[0], regions[i].box[2]), min(image_size[1], regions[i].box[3])]
                     for i in indices]
        boxes = [box.copy() for box in originals]
        for i, a in enumerate(boxes):
            for j in range(i+1, len(boxes)):
                b = boxes[j]
                if not self._intersects(a, b):
                    continue
                cross_x = a[0] < b[0] < a[2] < b[2] or b[0] < a[0] < b[2] < a[2]
                cross_y = a[1] < b[1] < a[3] < b[3] or b[1] < a[1] < b[3] < a[3]
                overlap = (min(a[2], b[2])-max(a[0], b[0])) * (min(a[3], b[3])-max(a[1], b[1]))
                area_a, area_b = (a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1])
                if not (cross_x and cross_y) or overlap > .08*min(area_a, area_b):
                    return None
                candidates = []
                for n, other in ((i, b), (j, a)):
                    box, original = boxes[n], originals[n]
                    original_area = (original[2]-original[0])*(original[3]-original[1])
                    for axis in (0, 1):
                        candidate = box.copy()
                        edge = axis+2 if box[axis] < other[axis] else axis
                        candidate[edge] = other[axis] if edge == axis+2 else other[axis+2]
                        width, height = candidate[2]-candidate[0], candidate[3]-candidate[1]
                        loss = 1-width*height/original_area
                        if (width <= 0 or height <= 0 or loss > .15
                                or max(abs(x-y) for x, y in zip(candidate, original)) > 8
                                or self._intersects(candidate, other)):
                            continue
                        if self._fit_text(translations[indices[n]].strip(), width, height,
                                          draw, minimum_only=True) is not None:
                            candidates.append((loss, n, axis, candidate))
                if not candidates:
                    return None
                _, n, _, candidate = min(candidates)
                boxes[n][:] = candidate
        result = []
        for index, box, original in zip(indices, boxes, originals):
            if self._fit_text(translations[index].strip(), box[2]-box[0], box[3]-box[1],
                              draw, minimum_only=True) is None:
                return None
            item = dict(indices=[index], box=box)
            if box != original:
                item.update(source_box=original, layout_strategy='corner-overlap-trim')
            result.append(item)
        return result

    def plan_layout(self, image_size, regions, translations, *, image=None, protected_regions=()):
        """Resolve intersecting OCR boxes before drawing any text.

        Close groups over their union rectangle so a merged group cannot cover
        another region. Flow each distinct translation exactly once within that
        existing text band first, preserving IDs/text upstream. Failed fits may
        expand over background, reserving other OCR/protected/planned frames.
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
        # Only groups that would previously fail the sparse-area guard may be
        # separated. Do not change existing accepted dense-group layouts.
        resolved = []
        for group in groups:
            indices = group['indices']
            x0,y0,x1,y1 = group['box']
            occupied = sum(max(0,min(image_size[0],regions[i].box[2])-max(0,regions[i].box[0])) *
                           max(0,min(image_size[1],regions[i].box[3])-max(0,regions[i].box[1])) for i in indices)
            if len(indices) > 1 and occupied < (x1-x0)*(y1-y0)*.6:
                separated = self._separate_sparse_corners(group, regions, translations, image_size, draw)
                if separated is None:
                    raise TextLayoutError('LAYOUT_UNFIT: nhóm box tạo vùng trống quá lớn; không mở chữ qua vùng hình quan trọng')
                resolved.extend(separated)
            else:
                resolved.append(group)
        groups = resolved
        protected_boxes = [list(r.box) if hasattr(r,'box') else list(r) for r in protected_regions]
        if image is not None and image.size != tuple(image_size):
            raise ValueError('Kích thước ảnh kiểm tra layout không khớp')
        plans = []
        for group in groups:
            indices = sorted(group['indices'])
            text = '  '.join(translations[index].strip() for index in indices)
            x0,y0,x1,y1 = group['box']
            width, height = x1-x0, y1-y0
            local_expansion = False
            background_expansion = False
            fit = self._fit_text(text, width, height, draw)
            if fit is None:
                # A small unchanged Latin identifier can be wider than its tight
                # OCR box at the configured minimum. Add only local horizontal
                # room; never expand dialogue, merge distant boxes or shrink type.
                literal = regions[indices[0]].text.strip() if len(indices) == 1 else ''
                if (len(indices) == 1 and height <= 24 and text == literal and
                        re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,127}', literal)):
                    font = ImageFont.truetype(str(self.font_path), self.options.font_min)
                    spacing = max(0, min(self.options.line_spacing, font.size // 4))
                    bbox = draw.multiline_textbbox((0,0), text, font=font, spacing=spacing,
                        align=self.options.alignment, stroke_width=self.options.stroke)
                    required = max(math.ceil(bbox[2]-bbox[0]), math.ceil(draw.textlength(text,font=font)+2*self.options.stroke))
                    padding = max(0,math.ceil((required-width)/2))
                    candidate = [max(0,x0-padding),y0,min(image_size[0],x1+padding),y1]
                    if (padding <= min(16,math.ceil(height*.75)) and required <= candidate[2]-candidate[0]
                            and bbox[3]-bbox[1] <= height and not any(
                                other is not group and self._intersects(candidate,other['box']) for other in groups)):
                        x0,y0,x1,y1 = candidate; width,height = x1-x0,y1-y0
                        fit = font,text,spacing,bbox
                if fit is None:
                    fit = self._fit_text(text,width,height,draw,alternate_wrap=True)
                if fit is None and image is not None:
                    members = set(indices)|{i for i,parent in duplicates.items() if parent in indices}
                    blockers = ([other['box'] for other in groups if other is not group]+protected_boxes+
                        [p['box'] for p in plans]+[list(r.box) for i,r in enumerate(regions) if i not in members])
                    blockers = [[b[0]-1,b[1]-1,b[2]+1,b[3]+1] for b in blockers]
                    expanded = self._expand_on_flat_background(image,group['box'],text,blockers,draw)
                    if expanded is None:
                        expanded = self._expand_over_background(image,group['box'],text,blockers,draw)
                        background_expansion = expanded is not None
                    if expanded is not None:
                        (x0,y0,x1,y1),fit = expanded
                        width,height = x1-x0,y1-y0
                        local_expansion = True
                if fit is None:
                    raise TextLayoutError(f'LAYOUT_UNFIT: bản dịch nhóm {indices} không vừa ({width}×{height}px) ở cỡ tối thiểu {self.options.font_min}; không cắt nội dung hoặc vẽ chồng.')
            font, wrapped, spacing, bbox = fit
            pad = 1 if local_expansion else 0
            x = x0 + pad - bbox[0] + ((width-2*pad-(bbox[2]-bbox[0]))/2 if self.options.alignment == 'center' else 0)
            y = y0 + pad - bbox[1] + (height-2*pad-(bbox[3]-bbox[1]))/2
            if ''.join(wrapped.split()) != ''.join(text.split()):
                raise TextLayoutError('LAYOUT_UNFIT: word wrap làm thay đổi nội dung')
            plans.append(dict(region_indices=indices, duplicate_indices=[i for i,v in duplicates.items() if v in indices],
                box=[x0,y0,x1,y1],paint_box=[x+bbox[0],y+bbox[1],x+bbox[2],y+bbox[3]],
                text=text,wrapped=wrapped,font_size=font.size,spacing=spacing,origin=[x,y]))
            if 'layout_strategy' in group:
                plans[-1].update(source_box=group['source_box'], layout_strategy=group['layout_strategy'])
            if [x0,y0,x1,y1] != group['box']:
                plans[-1].update(source_box=group['box'],layout_strategy=
                    'background-overlap-wrap' if background_expansion else
                    'local-flat-background-wrap' if local_expansion else 'verbatim-ascii-local-padding')
        for i,plan in enumerate(plans):
            if any(self._intersects(plan['paint_box'],p['paint_box']) for p in plans[i+1:]):
                raise TextLayoutError('LAYOUT_UNFIT: vùng đặt chữ giao nhau sau bố trí')
        return plans

    def render(self, image: Image.Image, regions: list[OCRResult], translations: list[str], *, protected_regions=()) -> Image.Image:
        self.last_layout = []
        plans = self.plan_layout(image.size,regions,translations,image=image,protected_regions=protected_regions)
        output = image.copy()
        draw = ImageDraw.Draw(output)
        for plan in plans:
            font = ImageFont.truetype(str(self.font_path),plan['font_size'])
            clipped = plan.get('layout_strategy') in ('local-flat-background-wrap','background-overlap-wrap')
            tile = output.crop(tuple(plan['box'])) if clipped else None
            painter = ImageDraw.Draw(tile) if clipped else draw
            origin = (plan['origin'][0]-plan['box'][0],plan['origin'][1]-plan['box'][1]) if clipped else tuple(plan['origin'])
            painter.multiline_text(origin,plan['wrapped'],font=font,fill=self.options.foreground,
                spacing=plan['spacing'],align=self.options.alignment,stroke_width=self.options.stroke,
                stroke_fill='white' if self.options.foreground == 'black' else 'black')
            if clipped:
                output.paste(tile,tuple(plan['box'][:2]))
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
