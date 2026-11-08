"""Analyze supplied HTML/rendered DOM offline; never fetch page/image bytes.

Results are file-parser evidence, never a live website/download test.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import sys
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import ROOT
from core.storage import file_digest
from sources.kuaikan import KuaikanAdapter


def report_image(image) -> dict:
    """Keep exact URLs inside the parser; never write signed query values to reports."""
    row = asdict(image)
    url = row.get('source_url')
    if url:
        parsed = urlsplit(url)
        if parsed.query:
            row['source_url_sha256'] = hashlib.sha256(url.encode('utf-8')).hexdigest()
            row['source_url'] = urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                urlencode([(key, '[REDACTED]') for key, _ in parse_qsl(parsed.query, keep_blank_values=True)]), ''))
            row['source_url_is_redacted'] = True
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--html', type=Path, required=True)
    parser.add_argument('--input-kind', choices=['unverified_html', 'manual_fixture', 'saved_html', 'rendered_dom'], default='unverified_html')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:6]
    folder = ROOT / 'output' / 'kuaikan-html-analysis' / stamp
    folder.mkdir(parents=True, exist_ok=False)
    report = {'input_kind': args.input_kind, 'live_test': False, 'downloaded_images': 0,
              'http_status': None, 'overall': 'FAIL', 'network_attempts': 0, 'warnings': []}
    report['test_classification'] = ('MANUAL FIXTURE TEST' if args.input_kind == 'manual_fixture' else
                                   'CAPTURED REAL DOM TEST' if args.input_kind in ('rendered_dom', 'saved_html') else 'UNVERIFIED FILE TEST')
    report.update(live_http_test='NOT TESTED (out of scope)', image_download_test='NOT TESTED (out of scope)')

    def audit(event, details):
        if event == 'socket.connect':
            report['network_attempts'] += 1
            raise RuntimeError('HTML analysis must remain offline')

    sys.addaudithook(audit)
    original_hash = None
    try:
        if args.html.stat().st_size > 5_000_000:
            raise ValueError('HTML/DOM exceeds 5 MB')
        original_hash = file_digest(args.html)
        html = args.html.read_text(encoding='utf-8-sig')
        adapter = KuaikanAdapter()
        report['source_url'] = adapter.normalize_url(args.url)
        report['source_sha256'] = original_hash
        adapter.load_document(args.url, html)
        comic = adapter.get_comic_info(args.url)
        report['comic'] = asdict(comic)
        chapters = adapter.get_chapters(comic)
        report.update(chapters=[asdict(chapter) for chapter in chapters],
                      chapter_list_complete=chapters.complete, warnings=list(chapters.warnings),
                      topic_analysis=chapters.analysis)
        if comic.source_kind == 'chapter':
            reader = adapter.parse_reader_html(args.url, html)
            report.update(previous_url=reader.previous_url, next_url=reader.next_url)
            images = adapter.get_chapter_images(chapters[0])
            report.update(images=[report_image(image) for image in images], image_list_complete=images.complete,
                          image_analysis=images.analysis,
                          download_decision=asdict(adapter.download_decision(chapters[0])))
            report['warnings'] += list(images.warnings)
        report['overall'] = 'PASS_FILE_PARSER'
    except Exception as exc:
        report['error'] = {'category': getattr(exc, 'category', 'technical'), 'detail': str(exc)}
        # No raw HTML or unfiltered image URL is logged.
    finally:
        report['source_unchanged'] = original_hash is not None and file_digest(args.html) == original_hash
        (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'result': report['overall'], 'input_kind': args.input_kind, 'live_test': False,
                          'chapters': len(report.get('chapters', [])), 'images': len(report.get('images', [])),
                          'evidence': str(folder)}, ensure_ascii=False))
    return 0 if report['overall'] == 'PASS_FILE_PARSER' else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    raise SystemExit(main())
