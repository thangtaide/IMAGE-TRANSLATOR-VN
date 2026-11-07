"""Local M2M100/CT2 inference; never imports a network-enabled model loader.

The package must be converted beforehand. Argos packages are not interchangeable
with M2M100: source language prefix and EOS are mandatory for the latter.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from core.models import verify_installation
from core.paths import TRANSLATION_MODELS
from core.storage import digest
from core.types import MissingModelError
from providers.base import OfflineTranslationProvider

MODEL_DIRECTORY = TRANSLATION_MODELS / 'm2m100_418m_ct2'
REQUIRED_FILES = ('m2m100.json', 'sentencepiece.bpe.model', 'model/model.bin',
                  'model/config.json', 'model/shared_vocabulary.json')
LANGUAGES = {'zh': 'zh', 'zt': 'zh', 'en': 'en', 'ko': 'ko', 'vi': 'vi'}


def validate_package(directory: Path) -> dict:
    if not all((directory / name).is_file() for name in REQUIRED_FILES):
        raise MissingModelError('Chưa có model M2M100 418M đã chuyển đổi và xác minh. '
                                'Model này được cài riêng; Offline không tự tải. '
                                'Bạn vẫn có thể chọn Argos đã cài.')
    verify_installation(directory)
    receipt = json.loads((directory / 'integrity.json').read_text(encoding='utf-8'))
    if not set(REQUIRED_FILES).issubset(receipt['files']):
        raise MissingModelError('Receipt M2M100 không bao phủ đủ model/tokenizer.')
    meta = json.loads((directory / 'm2m100.json').read_text(encoding='utf-8'))
    if (meta.get('model_id') != 'facebook/m2m100_418M' or meta.get('license') != 'MIT'
            or meta.get('format') != 'm2m100-ct2-v1'):
        raise MissingModelError('Gói không phải M2M100 418M/CT2 MIT được hỗ trợ.')
    vocab = json.loads((directory / 'model/shared_vocabulary.json').read_text(encoding='utf-8'))
    if not isinstance(vocab, list) or not {'__zh__', '__vi__', '</s>'}.issubset(vocab):
        raise MissingModelError('Vocabulary M2M100 thiếu language token hoặc EOS.')
    return meta


class M2M100TranslationProvider(OfflineTranslationProvider):
    engine_name = 'M2M100'

    def __init__(self, directory: Path = MODEL_DIRECTORY):
        self.directory = directory
        self.loaded = None
        self._meta = None
        self._lock = threading.RLock()

    def _verify(self) -> dict:
        if self._meta is None:
            self._meta = validate_package(self.directory)
        return self._meta

    @property
    def identity(self) -> str:
        receipt = self.directory / 'integrity.json'
        return 'M2M100:ct2-cpu-int8-v1:' + digest(
            [str(self.directory), receipt.read_text(encoding='utf-8') if receipt.is_file() else 'missing'])

    def route(self, source: str, target: str = 'vi') -> list[tuple[str, str]]:
        if source not in LANGUAGES or target not in LANGUAGES:
            raise ValueError('M2M100 hiện hỗ trợ zh/zt/ko/en → vi trong ứng dụng.')
        self._verify()
        return [] if source == target else [(source, target)]

    @property
    def packages(self) -> dict:
        meta = self._verify()
        return {(source, 'vi'): (self.directory, meta) for source in ['zh', 'zt', 'ko', 'en']}

    def _load(self) -> tuple:
        if self.loaded is None:
            self._verify()
            from core.runtime import prepare_inference_runtime
            import sentencepiece
            ct2 = prepare_inference_runtime()
            tokenizer = sentencepiece.SentencePieceProcessor(
                model_file=str(self.directory / 'sentencepiece.bpe.model'))
            translator = ct2.Translator(str(self.directory / 'model'), device='cpu',
                                       compute_type='int8', inter_threads=1, intra_threads=2)
            self.loaded = translator, tokenizer
        return self.loaded

    def translate_batch(self, texts: list[str], source: str, target: str = 'vi') -> list[str]:
        with self._lock:
            self.route(source, target)
            if not texts or source == target:
                return list(texts)
            if any(not text.strip() for text in texts):
                raise ValueError('Không dịch vùng văn bản rỗng.')
            translator, tokenizer = self._load()
            # Equivalent token strings to M2M100Tokenizer: lang + pieces + EOS.
            inputs = [[f'__{LANGUAGES[source]}__', *tokenizer.encode(text, out_type=str), '</s>']
                      for text in texts]
            if any(len(tokens) > 512 for tokens in inputs):
                raise ValueError('Vùng OCR vượt 512 token M2M100; không cắt nội dung.')
            prefix = f'__{LANGUAGES[target]}__'
            batches = translator.translate_batch(inputs, target_prefix=[[prefix] for _ in texts],
                beam_size=4, max_batch_size=4, max_input_length=512, max_decoding_length=768,
                length_penalty=1.0)
            if len(batches) != len(texts):
                raise RuntimeError('M2M100 trả thiếu kết quả dịch.')
            output = []
            for batch in batches:
                if not batch.hypotheses:
                    raise RuntimeError('M2M100 không trả hypothesis.')
                tokens = batch.hypotheses[0]
                if not tokens or tokens[0] != prefix or len(tokens) >= 768:
                    raise RuntimeError('M2M100 sai language prefix hoặc chạm giới hạn giải mã.')
                pieces = tokens[1:]
                if any(re.fullmatch(r'__[a-z]+__', token) for token in pieces):
                    raise RuntimeError('M2M100 sinh language token giữa nội dung.')
                pieces = [p for p in pieces if p not in {'<s>', '</s>', '<pad>'}]
                if '<unk>' in pieces:
                    raise RuntimeError('M2M100 sinh token không xác định; không âm thầm bỏ chữ.')
                text = tokenizer.decode(pieces).strip()
                if not text:
                    raise RuntimeError('M2M100 trả bản dịch rỗng.')
                output.append(text)
            return output

    def translate(self, text: str, source: str, target: str = 'vi') -> str:
        return self.translate_batch([text], source, target)[0]
