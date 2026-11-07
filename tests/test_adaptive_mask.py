"""Actual OpenCV tests on labelled synthetic geometry, no fake CV output."""
import unittest

import cv2
import numpy as np
from PIL import Image

from core.imaging import build_mask, erase_text
from core.types import OCRResult, Options


def region(box):
    x0,y0,x1,y1 = box
    return OCRResult('', [[x0,y0],[x1,y0],[x1,y1],[x0,y1]], .99, 'zh')


class AdaptiveMaskTests(unittest.TestCase):
    def test_tight_box_removes_complete_stroke_and_preserves_nearby_border(self):
        image = np.full((100, 240, 3), 255, np.uint8)
        cv2.line(image, (15, 25), (225, 25), (0,0,0), 2)
        cv2.rectangle(image, (50, 32), (59, 62), (0,0,0), -1)
        cv2.rectangle(image, (85, 32), (94, 62), (0,0,0), -1)
        # OCR missed the top 3 pixels; padded ROI includes nearby bubble border.
        regions = [region((48,35,98,64))]
        mask = build_mask(image, regions)
        self.assertTrue(np.all(mask[32:63,50:60] > 0))
        self.assertTrue(np.all(mask[24:27,:] == 0))
        erased = np.array(erase_text(Image.fromarray(image), regions, Options()))
        self.assertGreater(erased[32:63,50:95].min(), 245)
        np.testing.assert_array_equal(erased[24:27],image[24:27])

    def test_white_strokes_on_dark_background(self):
        image = np.zeros((100,180,3),np.uint8)
        cv2.rectangle(image,(40,30),(48,60),(255,255,255),-1)
        mask = build_mask(image,[region((39,33,70,62))])
        self.assertTrue(np.all(mask[30:61,40:49] > 0))
        erased=np.array(erase_text(Image.fromarray(image),[region((39,33,70,62))],Options()))
        self.assertLess(erased[30:61,40:49].max(),10)

    def test_no_text_does_not_mask_bubble_border(self):
        image=np.full((120,240,3),255,np.uint8)
        cv2.rectangle(image,(20,20),(220,100),(0,0,0),2)
        mask=build_mask(image,[region((40,23,200,60))])
        self.assertEqual(np.count_nonzero(mask),0)

    def test_image_edge_and_alpha_are_preserved(self):
        image=np.full((80,130,4),255,np.uint8)
        image[:,:,3]=np.arange(130,dtype=np.uint8)
        image[25:50,:5,:3]=0
        regions=[region((0,23,25,52))]
        result=erase_text(Image.fromarray(image),regions,Options())
        np.testing.assert_array_equal(np.array(result)[:,:,3],image[:,:,3])
        self.assertTrue(np.all(build_mask(image[:,:,:3],regions)[25:50,:5] > 0))
