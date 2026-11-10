"""Record real zh->en->vi stages and tokenizer checks for a fixed input corpus.

No reference translations or forced output substitutions are used.
"""
from __future__ import annotations

import json
import sys
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
CORPUS = ['你好，世界！', '欢迎使用图像翻译。', '谢谢你的帮助。', '对不起，我来晚了。', '没关系。',
          '你叫什么名字？', '今天的天气很好。', '我不知道。', '请等一下。', '你没事吧？',
          '我们回家吧。', '现在几点了？', '我想喝水。', '这个多少钱？', '他是我的朋友。',
          '不要碰我！', '发生了什么事？', '我会保护你。', '明天见。', '我饿了。',
          '你为什么在这里？', '不要放弃。', '这是我们的秘密。', '我们还有三分钟。']


def canonical(text):
    return ''.join(unicodedata.normalize('NFKC',text).split())


def main() -> int:
    from providers.offline import ArgosTranslationProvider
    from core.storage import file_digest
    from argostranslate.package import Package
    from scripts.validate_e2e import memory
    folder = ROOT/'output/translation-quality'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
    folder.mkdir(parents=True, exist_ok=False)
    provider = ArgosTranslationProvider()
    before = memory()
    started = time.perf_counter()
    english = provider.translate_batch(CORPUS, 'zh','en')
    vietnamese = provider.translate_batch(english,'en','vi')
    routed = provider.translate_batch(CORPUS,'zh','vi')
    records = []
    for index, (source, mid, target, normal) in enumerate(zip(CORPUS,english,vietnamese,routed)):
        checks = []
        for pair, text in [(('zh','en'),source),(('en','vi'),mid)]:
            translator, tokenizer, prefix = provider._load(pair)
            pieces = provider._encode(tokenizer,text)
            folder_model, meta = provider.packages[pair]
            official = Package(folder_model).tokenizer
            standard_pieces = official.encode(text)
            original_parameters = translator.translate_batch([standard_pieces], beam_size=4, num_hypotheses=4,
                max_batch_size=32, replace_unknowns=True, length_penalty=.2, return_scores=True)
            reference = official.decode(original_parameters[0].hypotheses[0]).strip()
            checks.append({'pair':list(pair), 'model_directory':str(folder_model),'metadata':meta,
                           'tokens':pieces, 'token_count':len(pieces),
                           'decoded_input':provider._decode(tokenizer,pieces).strip(),
                           'normalized_roundtrip_equal':canonical(provider._decode(tokenizer,pieces))==canonical(text),
                           'official_argos_tokenizer_equal':pieces==standard_pieces,
                           'original_argos_decode_parameters_output':reference})
        records.append({'id':index+1,'source_zh':source,'intermediate_en':mid,'final_vi':target,
                        'normal_pivot_vi':normal,'pivot_matches_separate_stages':target==normal,'checks':checks})
    models = []
    for pair in [('zh','en'),('en','vi')]:
        path, meta = provider.packages[pair]
        models.append({'pair':list(pair),'metadata':meta,'directory':str(path),
                       'model_sha256':file_digest(path/'model/model.bin'),
                       'tokenizer_sha256':file_digest(path/'sentencepiece.model'),
                       'installed_bytes':sum(p.stat().st_size for p in path.rglob('*') if p.is_file())})
    report = {'timestamp':datetime.now(timezone.utc).isoformat(), 'mock':False, 'count':len(records),
              'models':models,'seconds_total':time.perf_counter()-started,'memory_before':before,'memory_after':memory(),
              'records':records, 'technical_checks':{
                  'all_stage_routes_identical':all(r['pivot_matches_separate_stages'] for r in records),
                  'all_tokenizers_match_argos':all(c['official_argos_tokenizer_equal'] for r in records for c in r['checks']),
                  'all_token_counts_within_limit':all(c['token_count']<=384 for r in records for c in r['checks'])},
              'sentence_splitting':'Each corpus item is one complete sentence; no sentence splitter or OCR grouping is used.',
              'quality_status':'Requires human reading; successful inference is not semantic PASS'}
    (folder/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    rows = ['# Real translation corpus', '', '| # | Chinese | English intermediate | Vietnamese |', '| --- | --- | --- | --- |']
    rows += [f"| {r['id']} | {r['source_zh']} | {r['intermediate_en']} | {r['final_vi']} |" for r in records]
    (folder/'results.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    print('Quality corpus:',len(records),'Evidence:',folder)
    for r in records[:3]:
        print(json.dumps({k:r[k] for k in ['source_zh','intermediate_en','final_vi']},ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
