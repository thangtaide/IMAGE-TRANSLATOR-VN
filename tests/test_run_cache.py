"""Cache isolation and cleanup contracts; OCR/providers are counted local fixtures."""
import json
import os
from pathlib import Path
import sqlite3
from unittest.mock import patch

from PIL import Image

from core.imaging import erase_text
from core.pipeline import ProcessingManager,TranslationService,JobControl
from core.resume import ResumeStore
from core.run_cache import RunRegistry
from core.storage import TranslationCache,file_digest
from core.types import Options
from tests.test_core import WorkspaceCase,FakeOCR,FakeProvider


class IsolatedCacheTests(WorkspaceCase):
    def isolated(self, registry=None):
        registry=registry or RunRegistry(self.cache.path)
        return registry,registry.create(registry.plan(self.options()),self.options())

    def execute(self,registry,record,*,control=None,emit=lambda _:None):
        cache=TranslationCache(Path(record['database']));ocr=FakeOCR();provider=FakeProvider()
        options=Options.from_dict(record['options']);control=control or JobControl()
        try:
            with registry.claim(record['run_id']):
                registry.update(record['run_id'],state='running')
                service=TranslationService(options,cache,control,offline=provider)
                manager=ProcessingManager(options,cache,control,emit,ocr,service,
                    resume_id=record.get('journal_id'),input_exclusions=record.get('input_exclusions',()))
                result=manager.run();registry.update(record['run_id'],state=result['state'],journal_id=manager.resume_id)
            return result,ocr.calls,provider.calls
        finally:cache.close()

    def test_normal_cache_hits_but_isolated_run_performs_new_ocr_translation_and_render(self):
        self.image();ocr=FakeOCR();provider=FakeProvider()
        first=self.manager(ocr=ocr,provider=provider).run();self.assertEqual(first['completed'],1)
        second=self.manager(ocr=ocr,provider=provider).run();self.assertEqual(second['skipped'],1)
        self.assertEqual((ocr.calls,provider.calls),(1,1))
        before=list(self.cache.connection.iterdump())
        outputs={p:file_digest(p) for p in self.output.rglob('*.png')}
        journals={p:file_digest(p) for p in ResumeStore(self.cache.path).root.glob('*.json')}
        registry,record=self.isolated()
        with patch('core.pipeline.erase_text',wraps=erase_text) as inpaint:
            result,ocr_calls,mt_calls=self.execute(registry,record)
        self.assertEqual((result['completed'],result['skipped'],ocr_calls,mt_calls,inpaint.call_count),(1,0,1,1,1))
        self.assertEqual(before,list(self.cache.connection.iterdump()))
        self.assertTrue(all(file_digest(p)==h for p,h in {**outputs,**journals}.items()))
        new=next(Path(record['output']).glob('*.png'));self.assertNotIn(new,outputs)

    def test_unchecked_skip_reprocesses_to_new_output_and_retains_old_receipts(self):
        self.image();first=self.manager().run()
        old={p:file_digest(p) for p in self.output.glob('*.png')}
        second=self.manager(options=self.options(skip_success=False)).run()
        self.assertEqual((first['completed'],second['completed'],second['skipped']),(1,1,0))
        self.assertEqual(len(list(self.output.glob('*.png'))),2)
        self.assertTrue(all(file_digest(p)==h for p,h in old.items()))
        self.assertEqual(self.cache.connection.execute('select count(*) from items').fetchone()[0],2)

    def test_new_runs_have_distinct_database_and_output_even_with_same_source(self):
        self.image();registry,a=self.isolated();_,b=self.isolated(registry)
        self.assertNotEqual(a['database'],b['database']);self.assertNotEqual(a['output'],b['output'])
        self.assertEqual(self.execute(registry,a)[1:],(1,1));self.assertEqual(self.execute(registry,b)[1:],(1,1))

    def test_cancel_and_resume_reuses_only_this_runs_checkpoint(self):
        a=self.image('1.png');b=self.image('2.png')
        with Image.open(b) as image:
            image.putpixel((0,0),(80,10,20,190));image.save(b)
        registry,record=self.isolated();control=JobControl()
        def cancel_after_first(event):
            if event.get('stage')=='Hoàn thành':control.cancel()
        result,_,_=self.execute(registry,record,control=control,emit=cancel_after_first)
        self.assertEqual(result['state'],'cancelled')
        record=registry.read(record['run_id']);journal=ResumeStore(Path(record['database'])).read(record['journal_id'])
        done=[p for p in journal['pages'] if p['state']=='done'];self.assertEqual(len(done),1)
        old_hash=file_digest(Path(done[0]['output']))
        result,ocr,_=self.execute(registry,record)
        self.assertEqual((result['completed'],result['skipped'],result['failed'],ocr),(1,1,0,1))
        self.assertEqual(file_digest(Path(done[0]['output'])),old_hash)

    def test_cleanup_backups_only_selected_ocr_and_preserves_other_run_outputs_and_checkpoints(self):
        self.image();registry,a=self.isolated();_,b=self.isolated(registry)
        self.execute(registry,a);self.execute(registry,b)
        other=file_digest(Path(b['database']));journals={p:file_digest(p) for p in ResumeStore(Path(a['database'])).root.glob('*.json')}
        outputs={p:file_digest(p) for p in Path(a['output']).glob('*.png')}
        result=registry.prune(a['run_id'],{'ocr'})
        self.assertEqual(result['deleted_entries'],1)
        with sqlite3.connect(a['database']) as connection:
            self.assertEqual(connection.execute("select count(*) from cache where kind='ocr'").fetchone()[0],0)
            self.assertGreater(connection.execute("select count(*) from cache where kind='translation'").fetchone()[0],0)
            self.assertEqual(connection.execute('select count(*) from items').fetchone()[0],1)
        with sqlite3.connect(Path(result['backup'])/'state.sqlite3') as connection:
            self.assertEqual(connection.execute("select count(*) from cache where kind='ocr'").fetchone()[0],1)
        self.assertEqual(file_digest(Path(b['database'])),other)
        self.assertTrue(all(file_digest(p)==h for p,h in {**journals,**outputs}.items()))

    def test_cleanup_rejects_active_incomplete_and_render_receipts(self):
        self.image();registry,a=self.isolated()
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_PROTECTED'):registry.prune(a['run_id'],{'ocr'})
        self.execute(registry,a)
        with registry.claim(a['run_id']):
            with self.assertRaisesRegex(ValueError,'CACHE_BUSY'):registry.prune(a['run_id'],{'translation'})
        with self.assertRaisesRegex(ValueError,'SCOPE_UNSUPPORTED'):registry.prune(a['run_id'],{'metadata','output-hash'})

    def test_backup_failure_leaves_cache_intact(self):
        self.image();registry,a=self.isolated();self.execute(registry,a)
        before=file_digest(Path(a['database']))
        with patch.object(registry,'_snapshot',side_effect=OSError('fixture backup unavailable')):
            with self.assertRaises(OSError):registry.prune(a['run_id'],{'ocr','translation'})
        self.assertEqual(before,file_digest(Path(a['database'])))

    def test_transaction_rolls_back_all_selected_kinds_on_delete_error(self):
        self.image();registry,a=self.isolated();self.execute(registry,a)
        connection=sqlite3.connect(a['database'])
        try:
            connection.execute("CREATE TRIGGER stop_translation BEFORE DELETE ON cache WHEN OLD.kind='translation' BEGIN SELECT RAISE(ABORT,'fixture denial'); END")
            connection.commit()
        finally:connection.close()
        with self.assertRaises(sqlite3.IntegrityError):registry.prune(a['run_id'],{'ocr','translation'})
        connection=sqlite3.connect(a['database'])
        try:
            self.assertEqual(connection.execute("select count(*) from cache where kind='ocr'").fetchone()[0],1)
            self.assertEqual(connection.execute("select count(*) from cache where kind='translation'").fetchone()[0],1)
        finally:connection.close()

    def test_hardlinked_database_is_not_a_cleanup_target(self):
        self.image();registry,a=self.isolated();self.execute(registry,a)
        os.link(a['database'],self.folder/'retained-hardlink.sqlite3')
        with self.assertRaisesRegex(ValueError,'UNSAFE_PATH'):registry.prune(a['run_id'],{'ocr'})

    def test_untrusted_database_paths_and_run_ids_cannot_be_cleanup_targets(self):
        self.image();registry,a=self.isolated()
        with self.assertRaises(ValueError):registry.prune('../other',{'ocr'})
        path=registry.directory(a['run_id'])/'run.json';data=json.loads(path.read_text(encoding='utf-8'))
        data['database']=str(self.cache.path);path.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'INVALID_RUN'):registry.prune(a['run_id'],{'ocr'})

    def test_existing_output_path_is_never_adopted_or_overwritten(self):
        self.image();registry=RunRegistry(self.cache.path);plan=registry.plan(self.options())
        Path(plan['output']).mkdir(parents=True);marker=Path(plan['output'])/'keep.txt';marker.write_text('original')
        with self.assertRaises(FileExistsError):registry.create(plan,self.options())
        self.assertEqual(marker.read_text(),'original')

    def test_old_output_inside_source_is_not_treated_as_a_new_source_image(self):
        self.image();options=self.options();options.output=str(self.source/'old-results')
        self.manager(options=options).run()
        registry=RunRegistry(self.cache.path);record=registry.create(registry.plan(options),options)
        result,ocr,_=self.execute(registry,record)
        self.assertEqual((result['total'],result['completed'],ocr),(1,1,1))
