"""Numbers and bounded layout: sanitized inputs, no provider or OCR requests."""
import json
from pathlib import Path
from unittest.mock import Mock

from PIL import Image,ImageDraw,ImageFont

from core.pipeline import numeric_tokens,NUMBER_PATTERN,NumericMismatchError,TranslationService,JobControl
from core.storage import digest
from core.imaging import TextRenderer,TextLayoutError
from core.types import Options,OCRResult
from tests.test_core import WorkspaceCase
from tests.test_readability import audit,region

FIXTURE=json.loads((Path(__file__).parent/'fixtures/selective_numeric_layout.json').read_text(encoding='utf-8'))


class SelectiveNumericTests(WorkspaceCase):
    def test_real_failure_shapes_and_true_mismatches(self):
        provider=Mock(online=False,identity='SYNTHETIC-NO-TRANSPORT',engine_name='fixture')
        provider.translate.side_effect=AssertionError('Network/provider must not run')
        service=TranslationService(self.options(),self.cache,JobControl())
        for i,case in enumerate(FIXTURE['numeric']):
            with self.subTest(i=i):
                if case['accepted']:
                    self.assertEqual(service._translate_using(provider,case['source'],'zh',str(i),raw_target=case['target']),case['target'])
                else:
                    with self.assertRaises(NumericMismatchError):service._translate_using(provider,case['source'],'zh',str(i),raw_target=case['target'])
        provider.translate.assert_not_called()

    def test_legacy_percent_cache_cannot_bypass_missing_unit_protection(self):
        provider=Mock(online=False,identity='fixture-percent')
        source='百分之20';context='old'
        key=digest([source,'zh','vi',provider.identity,{},context,'glossary-v3-literal-numbers'])
        self.cache.put('translation',key,'20')
        service=TranslationService(self.options(),self.cache,JobControl())
        with self.assertRaises(NumericMismatchError):service._translate_using(provider,source,'zh',context,raw_target='20')
        self.assertEqual(service._translate_using(provider,source,'zh',context,raw_target='20%'),'20%')
        self.assertEqual(self.cache.get('translation',key),'20');provider.translate.assert_not_called()

    def test_plain_number_cache_and_signed_guards_remain_unchanged(self):
        provider=Mock(online=False,identity='fixture-normal')
        key=digest(['第14话','zh','vi',provider.identity,{},'normal','glossary-v3-literal-numbers'])
        self.cache.put('translation',key,'Chương 14')
        service=TranslationService(self.options(),self.cache,JobControl())
        self.assertEqual(service._translate_using(provider,'第14话','zh','normal'),'Chương 14')
        self.assertEqual(numeric_tokens('百分之-20 和 3333'),['-20%','3333'])
        self.assertEqual(numeric_tokens('1,000 1.5 12:30 -15 +4 7/8'),['1,000','1.5','12:30','-15','+4','7/8'])
        provider.translate.assert_not_called()


class SelectiveLayoutTests(WorkspaceCase):
    def renderer(self):return TextRenderer(Options(font_min=8,font_max=40,stroke=1,line_spacing=3))

    def test_actual_0085_identifier_local_padding_preserves_all_content(self):
        data=FIXTURE['layout_0085'];regions=[region(tuple(data['box']),data['source']),region((9,679,275,711),'甲'),region((260,679,1147,710),'乙')]
        texts=[data['target'],'Dừng lại được rồi?!','May mà phản ứng nhanh! Có thấy xe không?!']
        renderer=self.renderer();plans=audit(self,renderer,tuple(data['image_size']),regions,texts)
        plan=plans[0]
        self.assertEqual(plan['source_box'],data['box']);self.assertEqual(plan['layout_strategy'],'verbatim-ascii-local-padding')
        self.assertEqual(plan['font_size'],8);self.assertEqual(plan['text'],data['target'])
        self.assertLessEqual(data['box'][0]-plan['box'][0],9);self.assertLessEqual(plan['box'][2]-data['box'][2],9)
        renderer.render(Image.new('RGB',tuple(data['image_size']),'gray'),regions,texts)

    def test_nearby_region_blocks_expansion(self):
        with self.assertRaises(TextLayoutError):self.renderer().plan_layout((1280,720),
            [region((407,457,469,468),'ETDKTENOAOSTEE'),region((475,457,520,470),'旁')],['ETDKTENOAOSTEE','A'])

    def test_changed_target_or_cjk_does_not_receive_identifier_fallback(self):
        for source,target in [('different','ETDKTENOAOSTEE'),('中文'*20,'中文'*20)]:
            with self.subTest(source=source),self.assertRaises(TextLayoutError):
                self.renderer().plan_layout((1280,720),[region((407,457,469,468),source)],[target])

    def test_boundary_vertical_overflow_and_excessive_expansion_still_fail(self):
        for box,target in [((0,457,62,468),'ETDKTENOAOSTEE'),((407,457,469,460),'ETDKTENOAOSTEE'),((407,457,469,468),'A'*100)]:
            with self.subTest(box=box,target=target),self.assertRaises(TextLayoutError):
                self.renderer().plan_layout((1280,720),[region(box,target)],[target])

    def test_regular_layout_has_no_new_fallback_metadata(self):
        plan=self.renderer().plan_layout((1280,720),[region((20,20,500,90),'例')],['Chữ Việt bình thường, đủ nội dung'])[0]
        self.assertNotIn('layout_strategy',plan);self.assertEqual(plan['box'],[20,20,500,90])
