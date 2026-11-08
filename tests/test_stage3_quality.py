"""QA-only candidate tests. These do not enable any production date handling."""
import unittest

from qa.translation_quality import normalize_source,split_sentences,parse_date_range,date_integrity


class QADateTests(unittest.TestCase):
    def test_explicit_range_and_required_similar_examples(self):
        for source,target in [
            ('5月20日—5月30日','Từ ngày 20/5 đến ngày 30/5'),
            ('6月1日至6月10日','Từ ngày 1/6 đến ngày 10/6'),
            ('12月28日—1月3日','Từ ngày 28/12 đến ngày 3/1'),
            ('2024年12月28日—2025年1月3日','Từ ngày 28/12/2024 đến ngày 3/1/2025'),
            ('5月30日 到 6月2日','Từ ngày 30/5 đến ngày 2/6')]:
            value=parse_date_range(source)
            self.assertIsNotNone(value)
            self.assertEqual(value.vi(),target)
            self.assertTrue(date_integrity(source,target))

    def test_target_wrong_day_reordered_added_year_or_time_rejected(self):
        source='5月20日—5月30日'
        for target in ['Từ ngày 21/5 đến ngày 30/5','Từ ngày 30/5 đến ngày 20/5',
                       'Từ ngày 20/5/2024 đến ngày 30/5/2024','20 giờ 30 tháng 5']:
            self.assertFalse(date_integrity(source,target))

    def test_calendar_invalid_and_ambiguous_year_are_rejected(self):
        for source in ['2月30日—3月1日','2025年2月29日—2025年3月1日',
                       '2月29日—3月1日','2024年5月20日—5月30日','5月30日—5月20日']:
            self.assertIsNone(parse_date_range(source))
        self.assertIsNotNone(parse_date_range('2024年2月29日—2024年3月1日'))

    def test_adjacent_dates_without_separator_remain_ambiguous(self):
        for source in ['5月20日5月30日','6月1日6月10日','12月28日1月3日']:
            self.assertIsNone(parse_date_range(source))

    def test_time_money_phone_quantity_id_and_surroundings_are_not_dates(self):
        for source in ['20:00—20:30','20点—30点','20-30元','3—5个','13800138000',
                       'ID-20240520-20240530','活动时间：5月20日—5月30日',
                       '5月20日—5月30日（除外）','5月20日—5月30日20点',
                       '农历5月20日—5月30日','-15','1.5','５月２０日—５月３０日']:
            self.assertIsNone(parse_date_range(source))

    def test_date_roles_and_year_values_are_not_lost(self):
        source='2024年5月20日—2025年6月1日'
        value=parse_date_range(source)
        self.assertEqual((value.start.year,value.start.month,value.start.day),(2024,5,20))
        self.assertEqual((value.end.year,value.end.month,value.end.day),(2025,6,1))
        self.assertFalse(date_integrity(source,'Từ ngày 20/5/2025 đến ngày 1/6/2025'))


class QANormalizationTests(unittest.TestCase):
    def test_normalization_preserves_numbers_signs_and_unicode_digits(self):
        source='  -15  1.5  １３  ①\r\n'
        self.assertEqual(normalize_source(source),'-15  1.5  １３  ①')

    def test_sentence_split_loses_no_character_and_stays_in_one_region(self):
        source='你好！你是谁？\n请等一下。还有3个'
        parts=split_sentences(source)
        self.assertEqual(''.join(parts),source)
        self.assertEqual(parts,['你好！','你是谁？','\n请等一下。','还有3个'])
        self.assertEqual(split_sentences('20:30-21:30'),['20:30-21:30'])

    def test_empty_and_one_sentence(self):
        self.assertEqual(split_sentences(''),[])
        self.assertEqual(split_sentences('你好'),['你好'])
