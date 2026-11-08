"""Stage2 correction contracts; fixture inference is explicitly mocked."""
import copy
import json
from pathlib import Path
from unittest.mock import Mock

from core.ocr_overrides import OCRRegionOverrides, OCROverrideError
from core.storage import file_digest
from core.storage import digest
from core.pipeline import TranslationService, JobControl
from providers.online import ProviderError
from tests.test_core import WorkspaceCase, FakeOCR, region


class OverrideTests(WorkspaceCase):
    def rule(self, source, text='3子'):
        from core.paths import ROOT
        return dict(id='fixture-ignore-decoration', version=1, enabled=True,
                    action='SKIP_FALSE_POSITIVE_REGION', image_sha256=file_digest(source),
                    text=text, polygon=region(text).polygon, reason='Fixture: decoration, not text',
                    evidence='MANUAL FIXTURE, not a real OCR accuracy test',
                    source_relative_path=source.relative_to(ROOT).as_posix())

    def manager_rule(self, source, rule):
        provider = Mock(online=False, identity='unit-no-mt', engine_name='MockOffline')
        manager = self.manager(provider=provider, ocr=FakeOCR([region('3子')]))
        manager.override_registry = OCRRegionOverrides([rule])
        manager.diagnostic_root = self.folder/'diagnostics'
        return manager,provider

    def test_exact_hash_polygon_excludes_false_positive_without_provider_call(self):
        source=self.image();rule=self.rule(source)
        manager,provider=self.manager_rule(source,rule)
        result=manager.run()
        self.assertEqual(result['completed'],1)
        self.assertEqual(result['fallback_original'],0)
        provider.translate.assert_not_called()
        self.assertEqual(file_digest(manager.destination(source)),file_digest(source))
        raw=self.cache.connection.execute("SELECT value FROM cache WHERE kind='ocr'").fetchone()[0]
        self.assertEqual(json.loads(raw)['regions'][0]['text'],'3子')
        meta=json.loads(self.cache.connection.execute("SELECT value FROM cache WHERE kind='metadata'").fetchone()[0])
        self.assertTrue(meta['no_text_to_translate'])
        self.assertEqual(meta['ocr_overrides'][0]['version'],1)

    def test_hash_mismatch_on_intended_image_blocks_override_and_logs(self):
        source=self.image();rule=self.rule(source);rule['image_sha256']='a'*64
        manager,provider=self.manager_rule(source,rule)
        result=manager.run()
        self.assertEqual(result['fallback_original'],1)
        self.assertEqual(result['review_pages'][0]['error_code'],'OCR_OVERRIDE_HASH_MISMATCH')
        provider.translate.assert_not_called()

    def test_polygon_mismatch_does_not_remove_nearby_region(self):
        source=self.image();rule=self.rule(source);rule['polygon'][0][0]+=1
        manager,provider=self.manager_rule(source,rule)
        result=manager.run()
        self.assertEqual(result['fallback_original'],1)
        self.assertEqual(result['review_pages'][0]['error_code'],'OCR_OVERRIDE_REGION_MISMATCH')
        provider.translate.assert_not_called()

    def test_text_mismatch_blocks_override(self):
        source=self.image();rule=self.rule(source,text='different')
        manager,_=self.manager_rule(source,rule)
        result=manager.run()
        self.assertEqual(result['review_pages'][0]['error_code'],'OCR_OVERRIDE_REGION_MISMATCH')

    def test_disabled_override_keeps_real_region(self):
        source=self.image();rule=self.rule(source);rule['enabled']=False
        registry=OCRRegionOverrides([rule]);regions=[region('3子')]
        rules=registry.for_image(file_digest(source),source)
        kept,receipts=registry.apply(regions,rules)
        self.assertEqual(kept,regions);self.assertEqual(receipts,[])

    def test_unrelated_hash_not_affected(self):
        source=self.image();rule=self.rule(source)
        self.assertEqual(OCRRegionOverrides([rule]).for_image('a'*64,self.source/'other.png'),[])

    def test_other_real_text_kept_when_one_false_positive_removed(self):
        source=self.image();rule=self.rule(source)
        original=[region('3子'),region('第15话',box=(10,10,30,30))]
        saved=copy.deepcopy(original)
        kept,_=OCRRegionOverrides.apply(original,[rule])
        self.assertEqual([r.text for r in kept],['第15话'])
        self.assertEqual(original,saved)

    def test_ambiguous_identical_regions_are_not_removed(self):
        source=self.image();rule=self.rule(source)
        with self.assertRaises(OCROverrideError):
            OCRRegionOverrides.apply([region('3子'),region('3子')],[rule])

    def test_version_changes_only_per_image_revision(self):
        source=self.image();rule=self.rule(source)
        first=OCRRegionOverrides.revision([rule]);rule['version']=2
        self.assertNotEqual(first,OCRRegionOverrides.revision([rule]))
        self.assertIsNone(OCRRegionOverrides.revision([]))

    def test_schema_requires_evidence_and_valid_locator(self):
        source=self.image();rule=self.rule(source);rule['evidence']=''
        with self.assertRaises(OCROverrideError):OCRRegionOverrides([rule])
        rule=self.rule(source);rule['source_relative_path']='../outside'
        with self.assertRaises(OCROverrideError):OCRRegionOverrides([rule])

    def test_fallback_to_override_success_preserves_job_id_and_old_fallback(self):
        source=self.image();rule=self.rule(source)
        first,provider=self.manager_rule(source,rule)
        first.override_registry=OCRRegionOverrides()
        provider.translate.return_value='Không có số'
        failed=first.run();old=Path(failed['review_pages'][0]['output_path']);old_hash=file_digest(old)
        second,provider=self.manager_rule(source,rule)
        result=second.run(only=[str(source)])
        self.assertEqual(result['completed'],1)
        self.assertEqual(second.job_id,first.job_id)
        self.assertEqual(file_digest(old),old_hash)
        provider.translate.assert_not_called()
        self.assertEqual(self.cache.item(second.job_id,str(source))['status'],'done')


class NumericStage2Tests(WorkspaceCase):
    def service(self, output):
        provider=Mock(online=False,identity='numeric-stage2-fixture',engine_name='MockOffline')
        provider.translate.return_value=output
        return TranslationService(self.options(),self.cache,JobControl(),offline=provider),provider

    def rejected(self, source, target):
        service,_=self.service(target)
        with self.assertRaises(ProviderError):service.translate(source,'zh',source+'|'+target)

    def test_arabic_year_and_chapter(self):
        for source,target in [('15','15'),('第15话','Chương 15')]:
            service,_=self.service(target)
            self.assertEqual(service.translate(source,'zh',source),target)
        for source,target in [('15','16'),('2024','2025'),('第15话','Chương 16')]:self.rejected(source,target)

    def test_date_range_keeps_conservative_validation(self):
        for source in ['5月20日5月30日','5月20日—5月30日']:
            for target in ['20/5 đến 30/5','21/5 đến 30/5','30/5 đến 20/5','20 giờ 30 tháng 5']:
                self.rejected(source,target)
        # Correct-format dates are still conservative rejections, not model errors.
        # No production date normalization without a need demonstrated by the real target.
        self.rejected('5月6日','05/06')

    def test_decimal_locale_changes_require_context_and_are_not_auto_accepted(self):
        self.rejected('1.5','1,5')
        self.rejected('1,000','1.000')

    def test_phone_id_and_money_values_cannot_change(self):
        for source,target in [('电话13800138000','Điện thoại 13800138001'),
                              ('编号0015','Mã 0016'),('100元','101 đồng')]:self.rejected(source,target)

    def test_leading_sign_loss_is_rejected(self):
        for source in ['-15','−15','－15','+15','＋15']:
            self.rejected(source,'15')

    def test_leading_sign_addition_is_rejected(self):
        self.rejected('15','-15')

    def test_sign_and_numeric_value_change_is_rejected(self):
        self.rejected('-15','-16')

    def test_fullwidth_digits_preserved_but_not_silently_normalized(self):
        service,_=self.service('１５')
        self.assertEqual(service.translate('１５','zh','fullwidth'),'１５')
        self.rejected('１５','15')

    def test_legacy_cache_with_signed_target_is_not_trusted(self):
        service,provider=self.service('15')
        old_key=digest(['15','zh','vi',provider.identity,{},'legacy','glossary-v3-literal-numbers'])
        self.cache.put('translation',old_key,'-15')
        self.assertEqual(service.translate('15','zh','legacy'),'15')
        provider.translate.assert_called_once()
        self.assertEqual(self.cache.get('translation',old_key),'-15')

    def test_legacy_unsigned_cache_is_reused(self):
        service,provider=self.service('MUST NOT CALL')
        key=digest(['第15话','zh','vi',provider.identity,{},'legacy','glossary-v3-literal-numbers'])
        self.cache.put('translation',key,'Chương 15')
        self.assertEqual(service.translate('第15话','zh','legacy'),'Chương 15')
        provider.translate.assert_not_called()
