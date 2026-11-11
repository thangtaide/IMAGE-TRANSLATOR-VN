"""Neutral geometric OCR/layout fixtures. No saved story images or AI calls."""
import copy
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from core.imaging import TextRenderer, TextLayoutError
from core.ocr import group_lines
from core.types import Options
from tests.test_readability import audit, region


class OfflineCornerLayoutTests(unittest.TestCase):
    def renderer(self):
        return TextRenderer(Options(font_min=8, font_max=32))

    def test_small_corner_with_vertical_column_does_not_form_sparse_envelope(self):
        regions = [region((410, 18, 550, 44), 'Header'),
                   region((300, 38, 430, 430), 'Column')]
        texts = ['Thông báo mới', 'Nội dung mẫu xuống dòng trong cột hẹp.']
        before = copy.deepcopy(regions)
        renderer = self.renderer()
        plans = audit(self, renderer, (640, 480), regions, texts)
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0]['region_indices'], [0])
        self.assertEqual(plans[1]['region_indices'], [1])
        self.assertEqual(plans[1]['layout_strategy'], 'corner-overlap-trim')
        self.assertEqual(plans[1]['source_box'], [300, 38, 430, 430])
        self.assertEqual(plans[1]['box'], [300, 44, 430, 430])
        self.assertEqual(regions, before)
        renderer.render(Image.new('RGB', (640, 480), 'white'), regions, texts)

    def test_diagonal_short_labels_remain_separate_and_complete(self):
        regions = [region((40, 100, 68, 136), 'First'),
                   region((64, 132, 89, 160), 'Second')]
        plans = audit(self, self.renderer(), (200, 200), regions, ['Một', 'Hai'])
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0]['box'], [40, 100, 68, 132])
        self.assertEqual([p['text'] for p in plans], ['Một', 'Hai'])

    def test_corner_trim_preserves_duplicate_receipts(self):
        a = region((40, 100, 68, 136), 'First')
        regions = [a, copy.deepcopy(a), region((64, 132, 89, 160), 'Second')]
        plans = audit(self, self.renderer(), (200, 200), regions, ['Một', 'Một', 'Hai'])
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0]['duplicate_indices'], [1])

    def test_dense_overlapping_line_still_uses_original_grouping(self):
        regions = [region((10, 10, 130, 48), 'One'), region((100, 14, 230, 52), 'Two')]
        plans = audit(self, self.renderer(), (260, 100), regions, ['Dòng đầu', 'Dòng tiếp'])
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['region_indices'], [0, 1])
        self.assertNotIn('layout_strategy', plans[0])

    def test_local_ocr_grouping_keeps_header_and_vertical_column_separate(self):
        regions = [region((410, 18, 550, 44), 'Header'),
                   region((300, 38, 430, 430), 'Column')]
        grouped = group_lines(regions, np.full((480, 640, 3), 255, np.uint8), 'ltr')
        self.assertEqual([r.text for r in grouped], ['Header', 'Column'])
        plans = audit(self, self.renderer(), (640, 480), grouped,
                      ['Thông báo mới', 'Nội dung mẫu trong cột hẹp.'])
        self.assertEqual(len(plans), 2)

    def test_large_sparse_intersection_is_still_rejected(self):
        with self.assertRaisesRegex(TextLayoutError, 'vùng trống quá lớn'):
            self.renderer().plan_layout((240, 240),
                [region((0, 0, 100, 20)), region((80, 10, 100, 100))], ['Một', 'Hai'])

    def test_even_a_small_relative_overlap_cannot_move_an_edge_over_eight_pixels(self):
        with self.assertRaisesRegex(TextLayoutError, 'vùng trống quá lớn'):
            self.renderer().plan_layout((260, 460),
                [region((0, 0, 200, 40)), region((190, 30, 230, 440))], ['Một', 'Hai'])

    def test_trim_cannot_discard_an_unfittable_translation_or_draw_partially(self):
        renderer = self.renderer()
        image = Image.new('RGB', (200, 200), 'white')
        before = image.tobytes()
        with patch('core.imaging.ImageDraw.ImageDraw.multiline_text') as draw:
            with self.assertRaises(TextLayoutError):
                renderer.render(image, [region((40, 100, 68, 136)), region((64, 132, 89, 160))],
                    ['Nội_dung_rất_dài_không_được_cắt_bỏ', 'Hai'])
            draw.assert_not_called()
        self.assertEqual(image.tobytes(), before)
        self.assertEqual(renderer.last_layout, [])

    def test_boundary_labels_remain_within_image(self):
        plans = audit(self, self.renderer(), (200, 160),
            [region((-2, 100, 28, 136)), region((24, 132, 49, 160))], ['Một', 'Hai'])
        self.assertEqual(len(plans), 2)

    def test_general_layout_and_text_are_unchanged_without_collision(self):
        plans = audit(self, self.renderer(), (300, 160),
            [region((10, 10, 280, 60)), region((10, 80, 280, 150))],
            ['Nội dung bình thường', 'Giữ nguyên đầy đủ câu.'])
        self.assertTrue(all('layout_strategy' not in p for p in plans))


if __name__ == '__main__':
    unittest.main()
