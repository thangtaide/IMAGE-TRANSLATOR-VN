"""Safety contracts for numbers and unchanged symbol-only image regions (unit)."""
import unittest
from unittest.mock import Mock

import numpy as np

from core.imaging import open_image
from core.pipeline import TranslationService,JobControl
from providers.online import ProviderError
from tests.test_core import WorkspaceCase,FakeOCR,region


class NumberSafetyTests(WorkspaceCase):
    def service(self,output):
        provider=Mock(online=False,identity='UNIT-NUMBER-TRANSLATOR')
        provider.translate.return_value=output
        service=TranslationService(self.options(),self.cache,JobControl(),offline=provider)
        return service,provider

    def test_numbers_sent_literally_and_verified(self):
        service,provider=self.service('Chương 13')
        self.assertEqual(service.translate('第13话','zh','context'),'Chương 13')
        self.assertEqual(provider.translate.call_args.args[0],'第13话')

    def test_dropped_changed_added_or_reordered_numbers_rejected(self):
        for output in ['Chapter thirteen','Chapter 14','Chapters 13 and 14 and 15','14 before 13']:
            service,_=self.service(output)
            with self.assertRaises(ProviderError):service.translate('第13话和14话','zh',output)

    def test_number_like_region_preserves_pixels_and_skips_mt(self):
        path=self.image(mode='RGB')
        provider=Mock(online=False,identity='MUST-NOT-TRANSLATE')
        manager=self.manager(provider=provider,ocr=FakeOCR([region('3333')]))
        result=manager.run()
        self.assertEqual(result['completed'],1)
        provider.translate.assert_not_called()
        output=next(self.output.glob('*.png'))
        np.testing.assert_array_equal(np.array(open_image(path)),np.array(open_image(output)))
