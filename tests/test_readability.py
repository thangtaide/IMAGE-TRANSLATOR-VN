"""Raster/layout regressions. No provider, OCR inference or network requests."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from core.imaging import TextLayoutError, TextRemovalError, TextRenderer, build_mask, erase_text
from core.paths import ROOT
from core.types import OCRResult, Options
from tests.test_core import WorkspaceCase


def region(box, text='Original'):
    x0,y0,x1,y1 = box
    return OCRResult(text,[[x0,y0],[x1,y0],[x1,y1],[x0,y1]],.99,'zh')


def compact(text):
    return ''.join(text.split())


def audit(test, renderer, size, regions, texts):
    plans = renderer.plan_layout(size,regions,texts)
    indices = [i for p in plans for i in p['region_indices']+p['duplicate_indices']]
    test.assertEqual(sorted(indices),list(range(len(texts))))
    for n,p in enumerate(plans):
        test.assertEqual(compact(p['wrapped']),compact(' '.join(texts[i] for i in p['region_indices'])))
        x0,y0,x1,y1 = p['paint_box']
        test.assertGreaterEqual(x0,0); test.assertGreaterEqual(y0,0)
        test.assertLessEqual(x1,size[0]); test.assertLessEqual(y1,size[1])
        test.assertGreaterEqual(p['font_size'],renderer.options.font_min)
        for q in plans[n+1:]:
            test.assertFalse(renderer._intersects(p['paint_box'],q['paint_box']))
    return plans


class ReadableLayoutTests(unittest.TestCase):
    def test_intersecting_multiline_box_flows_each_translation_once(self):
        boxes=[(6,6,60,42),(75,5,310,83),(208,7,533,42),(556,9,862,40),(5,49,83,87),(294,52,927,86),(9,96,946,130)]
        regions=[region(b,str(i)) for i,b in enumerate(boxes)]
        texts=['Thông báo!', 'Chúc mừng bạn, phần thưởng đã được thêm vào túi đồ',
               'Nhiệm vụ hoàn thành,', 'nhận được danh hiệu mới', 'Phần thưởng',
               'Hai vật phẩm sử dụng cho các nhiệm vụ tiếp theo.', 'Dòng thứ ba phải giữ nguyên nội dung.']
        plans=audit(self,TextRenderer(Options(font_min=12)),(1280,720),regions,texts)
        self.assertEqual(len(plans),2)
        self.assertEqual(plans[0]['region_indices'],list(range(6)))
        self.assertGreaterEqual(plans[0]['font_size'],16)

    def test_union_closure_cannot_overlap_third_box_inside_merged_envelope(self):
        regions=[region((5,5,100,60),'a'),region((90,50,180,100),'b'),region((130,5,180,30),'c')]
        plans=audit(self,TextRenderer(Options(font_min=10)),(220,130),regions,['Một','Hai','Ba'])
        self.assertEqual(len(plans),1)

    def test_exact_duplicate_is_drawn_once_but_both_ids_are_accounted_for(self):
        regions=[region((5,5,180,55),'相同'),region((5,5,180,55),'相同')]
        plans=audit(self,TextRenderer(Options()),(200,100),regions,['Nội dung giống nhau','Nội dung giống nhau'])
        self.assertEqual(plans[0]['region_indices'],[0])
        self.assertEqual(plans[0]['duplicate_indices'],[1])
        self.assertEqual(plans[0]['text'],'Nội dung giống nhau')

    def test_same_phrase_in_distinct_locations_is_not_dropped(self):
        plans=audit(self,TextRenderer(Options()),(400,100),[region((1,1,180,40)),region((210,50,390,95))],['Xin chào','Xin chào'])
        self.assertEqual(len(plans),2)

    def test_different_targets_in_same_box_are_both_kept(self):
        plans=audit(self,TextRenderer(Options()),(400,100),[region((0,0,390,90)),region((0,0,390,90))],['Nội dung một','Nội dung hai'])
        self.assertEqual(plans[0]['region_indices'],[0,1])

    def test_matching_bounding_boxes_with_different_polygons_are_not_deduplicated(self):
        a=region((0,0,200,100),'same')
        b=OCRResult('same',[[0,0],[200,0],[100,100]],.99,'zh')
        plans=audit(self,TextRenderer(Options()),(220,120),[a,b],['Xin chào','Xin chào'])
        self.assertEqual(plans[0]['region_indices'],[0,1])

    def test_image_edge_text_and_explicit_newlines_are_not_clipped(self):
        regions=[region((-5,-2,250,60)),region((0,65,250,125),'next')]
        plans=audit(self,TextRenderer(Options(font_min=12)),(250,125),regions,['Dòng đầu\nDòng tiếp theo','Chữ Việt ở sát mép dưới'])
        self.assertIn('\n',plans[0]['wrapped'])

    def test_no_room_raises_before_drawing_any_region(self):
        renderer=TextRenderer(Options(font_min=14))
        original=Image.new('RGB',(200,100),'white')
        before=original.tobytes()
        with patch.object(ImageDraw.ImageDraw,'multiline_text') as draw:
            with self.assertRaises(TextLayoutError):
                renderer.render(original,[region((0,0,150,40)),region((180,80,183,83))],
                    ['Đọc được','Không được cắt mất câu này '*30])
            draw.assert_not_called()
        self.assertEqual(before,original.tobytes())
        self.assertEqual(renderer.last_layout,[])

    def test_tiny_frame_recovers_when_background_overlap_is_available(self):
        renderer=TextRenderer(Options(font_min=14))
        image=Image.new('RGB',(200,100),'white')
        output=renderer.render(image,[region((0,0,150,40)),region((180,80,183,83))],
            ['Đọc được','Không được cắt mất câu này'])
        self.assertEqual(output.size,image.size)
        self.assertEqual(renderer.last_layout[1]['layout_strategy'],'background-overlap-wrap')
        self.assertEqual(renderer.last_layout[1]['wrapped'].split(),'Không được cắt mất câu này'.split())
        self.assertFalse(renderer._intersects(renderer.last_layout[0]['paint_box'],renderer.last_layout[1]['paint_box']))

    def test_long_word_is_never_truncated(self):
        with self.assertRaises(TextLayoutError):
            TextRenderer(Options(font_min=14)).plan_layout((60,40),[region((0,0,60,40))],['X'*100])

    def test_diagonal_sparse_group_is_rejected_instead_of_covering_artwork(self):
        with self.assertRaisesRegex(TextLayoutError,'vùng trống quá lớn'):
            TextRenderer(Options()).plan_layout((200,200),
                [region((0,0,100,20)),region((80,10,100,100),'second')],['Một','Hai'])


class OutlinedMaskTests(unittest.TestCase):
    def fixture(self,inverse=False,shadow=False,top=8,lines=1):
        font_path=Path(os.environ.get('WINDIR',''))/'Fonts/msyh.ttc'
        if not font_path.is_file(): self.skipTest('Installed Chinese font missing; do not substitute square glyphs')
        font=ImageFont.truetype(str(font_path),32)
        yy,xx=np.mgrid[:180,:430]
        image=Image.fromarray(np.stack([75+xx%60,80+yy%55,95+(xx+yy)%45],axis=2).astype(np.uint8))
        truth=Image.new('L',image.size); regions=[]
        for n in range(lines):
            xy=(8,top+n*43); text='中国文字测试'
            if shadow:
                shifted=(xy[0]+3,xy[1]+3)
                ImageDraw.Draw(image).text(shifted,text,font=font,anchor='lt',fill=(20,20,20),stroke_width=4,stroke_fill=(20,20,20))
                ImageDraw.Draw(truth).text(shifted,text,font=font,anchor='lt',fill=255,stroke_width=4,stroke_fill=255)
            ImageDraw.Draw(image).text(xy,text,font=font,anchor='lt',fill='black' if inverse else 'white',stroke_width=4,stroke_fill='white' if inverse else 'black')
            ImageDraw.Draw(truth).text(xy,text,font=font,anchor='lt',fill=255,stroke_width=4,stroke_fill=255)
            regions.append(region(ImageDraw.Draw(image).textbbox(xy,text,font=font,anchor='lt')))
        return image,np.array(truth),regions

    def test_white_body_outline_and_shadow_are_masked(self):
        image,truth,regions=self.fixture(shadow=True)
        mask=build_mask(np.array(image),regions)
        self.assertGreater(np.mean(mask[truth>96]>0),.99)

    def test_inverse_polarity_is_masked(self):
        image,truth,regions=self.fixture(inverse=True)
        self.assertGreater(np.mean(build_mask(np.array(image),regions)[truth>96]>0),.99)

    def test_multiline_clipped_at_image_edge_and_duplicate_regions(self):
        image,truth,regions=self.fixture(top=0,lines=2)
        mask=build_mask(np.array(image),regions)
        self.assertGreater(np.mean(mask[truth>96]>0),.99)
        self.assertTrue(np.any(mask[0]))
        np.testing.assert_array_equal(mask,build_mask(np.array(image),regions+[regions[0]]))

    def test_pixels_outside_mask_and_alpha_are_preserved(self):
        image,_,regions=self.fixture(); image.putalpha(128)
        mask=build_mask(np.array(image.convert('RGB')),regions)
        before=np.array(image); after=np.array(erase_text(image,regions,Options()))
        np.testing.assert_array_equal(before[mask==0],after[mask==0])
        np.testing.assert_array_equal(before[:,:,3],after[:,:,3])

    def test_empty_mask_is_explicit_error(self):
        image,_,regions=self.fixture()
        with patch('core.imaging.build_mask',return_value=np.zeros((180,430),np.uint8)):
            with self.assertRaises(TextRemovalError): erase_text(image,regions,Options())

    def test_opencv_failure_is_explicit_error(self):
        image,_,regions=self.fixture()
        with patch('core.imaging.cv2.inpaint',side_effect=cv2.error('intentional fixture failure')):
            with self.assertRaises(TextRemovalError): erase_text(image,regions,Options())


class RemovalPipelineTests(WorkspaceCase):
    def test_renderer_uses_inpainted_object_and_correct_order(self):
        self.image(); marker=Image.new('RGBA',(480,160),(10,70,90,190)); order=[]
        def remove(*args): order.append('remove'); return marker
        def render(renderer,image,*args,**kwargs):
            self.assertIn('protected_regions',kwargs)
            self.assertIs(image,marker); order.append('render'); return image.copy()
        with patch('core.pipeline.erase_text',side_effect=remove),patch.object(TextRenderer,'render',render):
            result=self.manager().run()
        self.assertEqual(order,['remove','render']); self.assertEqual(result['translated_success'],1)

    def test_removal_failure_never_renders_or_reports_translation_success(self):
        self.image()
        with patch('core.pipeline.erase_text',side_effect=TextRemovalError('TEXT_REMOVAL_FAILED')),patch.object(TextRenderer,'render') as renderer:
            result=self.manager().run()
        renderer.assert_not_called(); self.assertEqual(result['translated_success'],0)
        self.assertEqual(result['failed'],1); self.assertEqual(result['state'],'completed_with_warnings')

    def test_layout_failure_is_reported_without_publishing_a_translation(self):
        self.image(); manager=self.manager()
        with patch.object(TextRenderer,'plan_layout',side_effect=TextLayoutError('LAYOUT_UNFIT')):
            result=manager.run()
        self.assertEqual(result['translated_success'],0)
        self.assertEqual(result['failed'],1)
        self.assertEqual(result['state'],'completed_with_warnings')
        logs=list(manager.diagnostics.directory.glob('errors*.jsonl'))
        self.assertTrue(logs)
        self.assertIn('LAYOUT_UNFIT',logs[0].read_text(encoding='utf-8'))


class ExistingRealPageTests(unittest.TestCase):
    def test_saved_three_pages_have_complete_nonoverlapping_layout(self):
        directory=ROOT/'output/readability-review'
        if not directory.is_dir(): self.skipTest('Run local debug capture from existing cache first')
        for case in ('0002','0007','0011'):
            with self.subTest(case=case):
                folder=directory/case
                if not (folder/'metadata.json').exists(): self.skipTest('Real page not available in current cache: '+case)
                record=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
                options=Options.from_dict(json.loads((folder/'options.json').read_text(encoding='utf-8')))
                regions=[OCRResult(**r) for r in record['regions']]
                plans=audit(self,TextRenderer(options),tuple(record['size']),regions,record['translations'])
                if case=='0011':
                    self.assertEqual(len(regions),14)
                    self.assertGreaterEqual(plans[0]['font_size'],16)
