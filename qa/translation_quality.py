"""QA-only candidates. No provider registration, settings, cache or checkpoint writes."""
from __future__ import annotations

import calendar
import re
import unicodedata
from dataclasses import dataclass

DATE_POLICY_VERSION = 'qa-cjk-complete-date-range-v1'


def normalize_source(text: str) -> str:
    return unicodedata.normalize('NFC', text.replace('\r\n', '\n')).strip()


def split_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = re.findall(r'.+?(?:[。！？!?]+|$)', text, flags=re.S)
    if ''.join(parts) != text:
        raise ValueError('Sentence segmentation lost source content')
    return parts


@dataclass(frozen=True)
class CalendarDate:
    year: int | None
    month: int
    day: int

    def valid(self) -> bool:
        if not 1 <= self.month <= 12 or self.year is not None and not 1 <= self.year <= 9999:
            return False
        # Unspecified year stays unspecified: no leap-year assumption.
        maximum = calendar.monthrange(self.year if self.year is not None else 2001, self.month)[1]
        return 1 <= self.day <= maximum

    def vi(self) -> str:
        return f'{self.day}/{self.month}' + (f'/{self.year}' if self.year is not None else '')


@dataclass(frozen=True)
class DateRange:
    start: CalendarDate
    end: CalendarDate

    def valid(self) -> bool:
        if not self.start.valid() or not self.end.valid():
            return False
        if (self.start.year is None) != (self.end.year is None):
            return False  # No guessed/inherited year.
        if self.start.year is not None:
            return (self.start.year,self.start.month,self.start.day) <= (self.end.year,self.end.month,self.end.day)
        if self.start.month == 12 and self.end.month == 1:
            return True  # Preserve explicit endpoints, add no inferred year.
        return (self.start.month,self.start.day) <= (self.end.month,self.end.day)

    def vi(self) -> str:
        if not self.valid():
            raise ValueError('Invalid/ambiguous date range')
        return f'Từ ngày {self.start.vi()} đến ngày {self.end.vi()}'


_CJK_DATE = r'(?:(?P<{p}y>[0-9]{{4}})\s*年\s*)?(?P<{p}m>[0-9]{{1,2}})\s*月\s*(?P<{p}d>[0-9]{{1,2}})\s*日'
_RANGE = re.compile(r'\s*'+_CJK_DATE.format(p='s')+r'\s*(?:—|–|-|至|到|~|～)\s*'+_CJK_DATE.format(p='e')+r'\s*')
_VI = re.compile(r'Từ ngày (?P<sd>[0-9]{1,2})/(?P<sm>[0-9]{1,2})(?:/(?P<sy>[0-9]{4}))? đến ngày '
                 r'(?P<ed>[0-9]{1,2})/(?P<em>[0-9]{1,2})(?:/(?P<ey>[0-9]{4}))?')


def _date(match, prefix: str) -> CalendarDate:
    year=match.group(prefix+'y')
    return CalendarDate(int(year) if year is not None else None, int(match.group(prefix+'m')), int(match.group(prefix+'d')))


def parse_date_range(text: str) -> DateRange | None:
    """Only two complete CJK dates and an explicit delimiter, nothing else."""
    match=_RANGE.fullmatch(text)
    if match is None:
        return None
    value=DateRange(_date(match,'s'),_date(match,'e'))
    return value if value.valid() else None


def date_integrity(source: str, target: str) -> bool:
    """Ordered, role-aware endpoint equality; never compare a multiset of numbers."""
    expected=parse_date_range(source)
    match=_VI.fullmatch(target)
    if expected is None or match is None:
        return False
    actual=DateRange(_date(match,'s'),_date(match,'e'))
    return actual.valid() and actual == expected
