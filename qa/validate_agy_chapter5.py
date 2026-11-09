"""Explicit chapter276880 QA. Isolated outputs; six durable CLI generations max.

prepare never generates. batch/whole require --authorized-live. No automatic retry.
"""
from __future__ import annotations
import argparse
import json
import os
import random
import sqlite3
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


def utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['prepare', 'batch', 'whole', 'verify'])
    parser.add_argument('--authorized-live', action='store_true')
    parser.add_argument('--run-id', default='first', choices=['first', 'corrected'])
    parser.add_argument('--authorized-whole-after-timeout', action='store_true')
    parser.add_argument('--authorized-resume-batch', action='store_true')
    args = parser.parse_args()
    from core.runtime import prepare_inference_runtime
    prepare_inference_runtime()
    from core.paths import ROOT
    from core.storage import TranslationCache, digest, file_digest, atomic_json
    from core.types import Options, OCRResult
    from core.pipeline import ProcessingManager, TranslationService, JobControl
    from core.ocr import PaddleOCREngine
    from core.whole_chapter import WholeChapterJob, AGYWholeChapterTranslator, read_json, verify
    from core.multipage import Item, pack_pages
    from providers import agy
    from sources.cache import inspect_image

    evidence = Path(json.loads((ROOT/'logs/latest-agy-chapter5.json').read_text())['qa'])
    tag = evidence.name.removeprefix('agy-chapter5-')
    source = ROOT/'cache/online_comics/kuaikanmanhua/6677/chapter_276880'
    old = ROOT/'output/stage3g-20261109T072406Z-9cf0024a'
    manifest = verify(read_json(old/'chapter-ocr-manifest.json'))
    old_journal = verify(read_json(old/'chapter-journal.json'))
    assert manifest['region_count'] == 93 and len(manifest['pages']) == 109
    opts = Options.from_dict(old_journal['options'])
    opts = replace(opts, mode=agy.MODE, agy_model='gemini-3.8-flash-medium',
                   agy_timeout=300 if args.authorized_resume_batch else 90, agy_max_requests=6, allow_online_fallback=False,
                   diagnostic_text=False, agy_batch_chars=3000, agy_batch_regions=60)
    engine = PaddleOCREngine()
    assert engine.identity(opts.language) == manifest['ocr_identity'], 'OCR_RECIPE_CHANGED'
    paths = [source/p['page']['relative'] for p in manifest['pages']]
    assert paths == sorted(source.glob('*.jpg')) and len(paths) == 109
    assert all(file_digest(p) == row['page']['source_hash'] for p, row in zip(paths, manifest['pages']))
    suffix = '' if args.run_id == 'first' else '-corrected'
    workspaces = {mode: ROOT/'output'/f'stage3g-chapter5-{tag}{suffix}-{mode}' for mode in ('batch', 'whole')}
    ledger_path = evidence/'invocations.json'

    def save(path, value):
        atomic_json(path, value)

    def event(item):
        # Progress only: no OCR, translations, prompt or raw error strings.
        if item.get('type') in ('whole_manifest_ready', 'whole_progress', 'agy_batch_wait', 'whole_agy_running'):
            print(json.dumps({k:v for k,v in item.items() if k in
                ('type','phase','completed','total','pages','regions','source_characters','remaining_seconds')}, ensure_ascii=True), flush=True)

    if args.phase == 'prepare':
        for mode, workspace in workspaces.items():
            assert not workspace.exists(), 'NEW_WORKSPACE_REQUIRED'
            workspace.mkdir()
            cache = TranslationCache(workspace/'qa.sqlite3')
            for page in manifest['pages']:
                identifier = page['page']['id']
                record_path = old/f'ocr-{identifier}.json'
                assert file_digest(record_path) == old_journal['ocr'][identifier]
                record = verify(read_json(record_path))
                assert record['page'] == page['page'] and record['raw_ocr'] == page['raw_ocr']
                key = digest([page['page']['source_hash'], manifest['ocr_identity'], opts.language,
                              opts.confidence, opts.tile_size, opts.reading_direction])
                cache.put('ocr', key, record['raw_ocr'])
            cache.close()
        job = WholeChapterJob(source, workspaces['whole'], options=opts, chapter_id='276880',
            translator=AGYWholeChapterTranslator(opts), ocr=engine, emit=event, input_paths=paths)
        prepared = job.run(allow_translation=False)
        plan = [dict(pages=len({i.page for i in batch}), regions=len(batch),
                     characters=sum(len(i.region.text) for i in batch))
                for batch in pack_pages([[Item(r['id'], str(p['page']['index']), n, OCRResult(**r['ocr']))
                     for n,r in enumerate(p['regions'])] for p in manifest['pages']],
                     max_pages=24, hard_chars=3000)]
        result = dict(source_pages=109, regions=manifest['region_count'], characters=manifest['source_characters'],
            batch_plan=plan, prepared=prepared, workspaces={k:str(v) for k,v in workspaces.items()},
            reused_verified_ocr_pages=109, reused_translation_cache=False)
        save(evidence/f'plan{suffix}.json', result)
        print(json.dumps(result, ensure_ascii=True), flush=True)
        return

    plan = json.loads((evidence/f'plan{suffix}.json').read_text())
    if args.phase == 'verify':
        results = {}
        for mode, workspace in workspaces.items():
            outputs = sorted((workspace/'rendered').glob('*.jpg'))
            connection = sqlite3.connect((workspace/'qa.sqlite3').resolve().as_uri()+'?mode=ro', uri=True)
            mapping = {Path(output).resolve(): Path(path) for path, output in
                connection.execute("SELECT path,output FROM items WHERE status='done'")}
            connection.close()
            rows = []
            for target in outputs:
                info = inspect_image(target)
                original = mapping[target.resolve()]
                original_info = inspect_image(original)
                rows.append(dict(name=target.name, width=info['width'], height=info['height'],
                    source_name=original.name, dimensions_match=(info['width'],info['height']) ==
                        (original_info['width'],original_info['height']),
                    different_from_original=info['sha256'] != file_digest(original)))
            results[mode] = dict(output_count=len(outputs), bitmap_checks=rows,
                fallback_count=len(list((workspace/'rendered').glob('*.fallback-original.*'))))
        save(evidence/f'outputs{suffix}.json', results)
        print(json.dumps({k:{x:v[x] for x in ('output_count','fallback_count')} for k,v in results.items()}))
        return

    assert args.authorized_live, 'EXPLICIT_LIVE_AUTHORIZATION_REQUIRED'
    workspace = workspaces[args.phase]
    resuming = args.phase == 'batch' and args.authorized_resume_batch and args.run_id == 'corrected'
    result_suffix = suffix + ('-timeout-repair' if resuming else '')
    assert not (evidence/f'{args.phase}{result_suffix}-started.json').exists(), 'NO_AUTOMATIC_RERUN'
    old_result = json.loads((evidence/f'batch{suffix}-result.json').read_text()) if resuming else None
    if resuming:
        assert old_result['completed']==59 and old_result['state']=='paused_provider'
    if args.phase == 'whole' and not args.authorized_whole_after_timeout:
        batch_result = json.loads((evidence/f'batch{suffix}-result.json').read_text())
        assert batch_result.get('completed') == 109 and not batch_result.get('fallback_original'), 'BATCH_NOT_VALIDATED'
    agy.check_automatic_extensions(workspace)
    # An independent QA process holds this lock through translation and render.
    import msvcrt
    lock = (evidence/'qa.lock').open('a+b')
    if lock.tell() == 0:
        lock.write(b'0'); lock.flush()
    lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    save(evidence/f'{args.phase}{result_suffix}-started.json', dict(timestamp=utc(), authorized=True))
    real_runner, provider_class = agy.run_bounded, agy.AGYProvider

    def runner(argv, payload, cwd, timeout, cancelled):
        if payload is None:
            return real_runner(argv, payload, cwd, timeout, cancelled)
        ledger = json.loads(ledger_path.read_text())
        attempts = ledger['attempts']
        exception = (args.phase == 'whole' and args.authorized_whole_after_timeout and len(attempts) == 3
            and ledger.get('blocked') and ledger.get('stopped_reason') == 'TIMEOUT_BACKEND_STATE_UNKNOWN'
            and not ledger.get('whole_after_timeout_exception_used'))
        repair = (resuming and len(attempts) in (4,5) and
            (len(attempts)==4 and attempts[-1].get('validation')=='VALIDATED_93_REGIONS_109_OUTPUTS' or
             len(attempts)==5 and attempts[-1].get('timeout_repair') is True and attempts[-1]['status']=='SUCCESS'))
        assert len(attempts) < 6 and (not ledger.get('blocked') or exception or repair), 'QA_BUDGET_OR_PREVIOUS_FAILURE'
        assert not attempts or attempts[-1].get('finished'), 'QA_GENERATION_ALREADY_ACTIVE'
        pause = 0
        if attempts:
            previous = attempts[-1]
            required = 60 if previous['mode'] != args.phase or previous.get('run_id') != args.run_id or previous['status'] != 'SUCCESS' else random.uniform(5,10)
            deadline = datetime.fromisoformat(previous['finished']).timestamp() + required
            pause = max(0, deadline-time.time())
            while time.time() < deadline:
                if cancelled():
                    raise RuntimeError('QA_CANCELLED_BEFORE_GENERATION')
                time.sleep(min(.2, max(0,deadline-time.time())))
        packet = json.loads(payload)['message']['content']
        packet = json.loads(packet)
        if args.phase == 'whole':
            page_rows = packet['chapter']['pages']
            regions = [r for p in page_rows for r in p['regions']]
            pages, chars = len(page_rows), sum(len(r['original_ocr_text']) for r in regions)
        else:
            regions = packet.get('items', packet.get('regions', []))
            # The live provider's exact JSON contract is checked before Popen.
            assert regions, 'QA_PAYLOAD_CONTRACT'
            pages, chars = len({r['id'].split(':')[1] if ':' in r['id'] else r['id'].split('_r')[0] for r in regions}), sum(len(r['text']) for r in regions)
        if args.phase == 'whole':
            assert len(regions) == 93 and pages == 109 and chars == 536
        else:
            assert len(regions) <= 60 and chars <= 3000
        from providers.agy_process import active_agy_processes
        assert not active_agy_processes(), 'ANOTHER_AGY_PROCESS_EXISTS'
        if repair:
            assert len(manager.journal['regions'])==(44 if len(attempts)==4 else 83), 'VALIDATED_RECEIPTS_CHANGED'
        cli_seconds = float(argv[argv.index('--print-timeout')+1].removesuffix('s'))
        entry = dict(number=len(attempts)+1, mode=args.phase, run_id=args.run_id, model=opts.agy_model,
            started=utc(), finished=None, pages=pages, regions=len(regions), characters=chars,
            timeout=cli_seconds, watchdog_timeout_seconds=timeout, wait_seconds=pause, status='ATTEMPT_STARTED',
            timeout_repair=bool(repair))
        if exception:
            ledger['whole_after_timeout_exception_used'] = True
            entry['explicit_user_exception'] = 'ONE_WHOLE_AFTER_UNKNOWN_TIMEOUT'
        if repair:
            claim=evidence/f'invocation-{entry["number"]:04d}.claim.json'
            with claim.open('x',encoding='utf-8') as stream:
                json.dump(entry,stream);stream.flush();os.fsync(stream.fileno())
        attempts.append(entry);save(ledger_path, ledger)
        start = time.monotonic()
        try:
            code,out,err = real_runner(argv,payload,cwd,timeout,cancelled,
                observer=lambda data:entry.update(transport=data))
            entry.update(status='SUCCESS' if code==0 else 'CLI_EXIT', exit_code=code,
                         stdout_bytes=len(out), stderr_bytes=len(err))
            if code != 0:
                ledger['blocked'] = True
            return code,out,err
        except BaseException as exc:
            entry['status'] = getattr(exc,'code',type(exc).__name__)
            capture = getattr(exc,'_agy_capture',None)
            if capture:
                entry.update(stdout_bytes=len(capture.stdout),stderr_bytes=len(capture.stderr),exit_code=capture.exit_code)
            ledger['blocked'] = True
            raise
        finally:
            entry.update(finished=utc(),elapsed_seconds=time.monotonic()-start)
            save(ledger_path,ledger)

    def factory(*a,**kw):
        kw['runner'] = runner
        return provider_class(*a,**kw)

    try:
        if args.phase == 'batch':
            cache = TranslationCache(workspace/'qa.sqlite3')
            options = replace(opts,source=str(source),output=str(workspace/'rendered'))
            control = JobControl()
            service = TranslationService(options,cache,control)
            service.agy = factory(model=opts.agy_model,timeout=opts.agy_timeout,max_requests=6,
                checkpoint=control.checkpoint,cancelled=lambda:control.cancelled,root=workspace/'agy')
            manager = ProcessingManager(options,cache,control,ocr=engine,service=service,
                chapter_id='276880',diagnostic_root=workspace/'diagnostics',emit=event,
                resume_id=old_result['resume_id'] if resuming else None)
            result = manager.run()
            cache.close()
        else:
            prepared_manifest = verify(read_json(workspace/'chapter-ocr-manifest.json'))
            with patch.object(agy,'AGYProvider',factory):
                job = WholeChapterJob(source,workspace,options=opts,chapter_id='276880',
                    translator=AGYWholeChapterTranslator(opts),ocr=engine,emit=event,input_paths=paths)
                result = job.run(allow_translation=True,confirmed_manifest_hash=prepared_manifest['content_hash'])
        save(evidence/f'{args.phase}{result_suffix}-result.json',result)
        print(json.dumps({k:v for k,v in result.items() if k!='pending_paths'},ensure_ascii=True),flush=True)
    finally:
        lock.close()


if __name__ == '__main__':
    main()
