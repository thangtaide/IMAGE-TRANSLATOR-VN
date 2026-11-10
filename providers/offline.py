from __future__ import annotations

import json
import gc
from pathlib import Path

from core.paths import TRANSLATION_MODELS
from core.storage import digest
from core.types import MissingModelError
from providers.base import OfflineTranslationProvider


class CTranslate2TranslationProvider(OfflineTranslationProvider):
    """Run installed Argos SentencePiece/CT2 packages without network-capable SBD.

    Argos packages contain CT2 model/model.bin + sentencepiece.model + metadata.json.
    Input regions are already short OCR paragraphs. No Stanza/Spacy auto-download.
    """
    engine_name = "CTranslate2"

    def __init__(self, root: Path = TRANSLATION_MODELS):
        self.root = root
        self.packages: dict[tuple[str, str], tuple[Path, dict]] = {}
        self.loaded: dict[str, tuple] = {}
        if root.exists():
            for path in root.glob("*/metadata.json"):
                try:
                    meta = json.loads(path.read_text(encoding="utf-8"))
                    if (path.parent / "model/model.bin").is_file() and (path.parent / "sentencepiece.model").is_file():
                        self.packages[(meta["from_code"], meta["to_code"])] = (path.parent, meta)
                except (OSError, ValueError, KeyError):
                    continue

    @property
    def identity(self) -> str:
        receipts = []
        for path, meta in self.packages.values():
            receipt = path / "integrity.json"
            receipts.append([meta, receipt.read_text(encoding="utf-8") if receipt.exists() else "unverified"])
        return self.engine_name + ":ct2-int8-v1:" + digest(receipts)

    def route(self, source: str, target: str = "vi") -> list[tuple[str, str]]:
        if source == target:
            return []
        if (source, target) in self.packages:
            return [(source, target)]
        if (source, "en") in self.packages and ("en", target) in self.packages:
            return [(source, "en"), ("en", target)]
        raise MissingModelError(f"Thiếu model {source} → {target}. Cài đủ model trực tiếp hoặc {source} → en và en → {target} trong Quản lý mô hình AI.")

    def _load(self, pair: tuple[str, str]) -> tuple:
        path, meta = self.packages[pair]
        key = str(path)
        if key not in self.loaded:
            from core.models import verify_installation
            verify_installation(path)
            if len(self.loaded) >= 2:
                oldest = next(iter(self.loaded))
                del self.loaded[oldest]
                gc.collect()
            from core.runtime import prepare_inference_runtime
            ctranslate2 = prepare_inference_runtime()
            tokenizer = self._make_tokenizer(path / 'sentencepiece.model')
            translator = ctranslate2.Translator(str(path / "model"), device="cpu", compute_type="int8", inter_threads=1, intra_threads=2)
            self.loaded[key] = translator, tokenizer, meta.get("target_prefix", "")
        else:
            cached = self.loaded.pop(key)
            self.loaded[key] = cached
        return self.loaded[key]

    def _make_tokenizer(self, path: Path):
        import sentencepiece
        return sentencepiece.SentencePieceProcessor(model_file=str(path))

    def _encode(self, tokenizer, text: str) -> list[str]:
        return tokenizer.encode(text, out_type=str)

    def _decode(self, tokenizer, tokens: list[str]) -> str:
        # Argos vocab can contain target tokens absent from SentencePiece vocab.
        # Follow Argos detokenization instead of mapping unknown target pieces to UNK.
        return ''.join(tokens).replace('▁', ' ')

    def translate_batch(self, texts: list[str], source: str, target: str = "vi") -> list[str]:
        results = list(texts)
        for pair in self.route(source, target):
            translator, tokenizer, prefix = self._load(pair)
            tokens = [self._encode(tokenizer, t) for t in results]
            if any(len(t) > 384 for t in tokens):
                raise ValueError("Đoạn OCR quá dài cho model Offline (384 token); chia nhỏ vùng chữ.")
            kwargs = {"target_prefix": [[prefix] for _ in texts]} if prefix else {}
            batches = translator.translate_batch(tokens, beam_size=4, max_batch_size=8,
                                                 max_decoding_length=768, replace_unknowns=True, length_penalty=.2, **kwargs)
            results = [self._decode(tokenizer, b.hypotheses[0][1:] if prefix else b.hypotheses[0]).strip() for b in batches]
            if any(not t for t in results):
                raise RuntimeError("Model Offline trả bản dịch rỗng")
            if any(len(b.hypotheses[0]) >= 768 for b in batches):
                raise RuntimeError("Model chạm giới hạn giải mã; không xuất bản dịch có thể bị cắt.")
        return results

    def translate(self, text: str, source: str, target: str = "vi") -> str:
        return self.translate_batch([text], source, target)[0]


class ArgosTranslationProvider(CTranslate2TranslationProvider):
    """Argos package provider using its bundled CT2 model and SentencePiece.

    Deliberately avoids argostranslate.translate automatic sentence model loading.
    Model manager validates the official Argos package layout and metadata.
    """
    engine_name = "Argos"

    def _make_tokenizer(self, path: Path):
        from argostranslate.tokenizer import SentencePieceTokenizer
        return SentencePieceTokenizer(path)

    def _encode(self, tokenizer, text: str) -> list[str]:
        return tokenizer.encode(text)

    def _decode(self, tokenizer, tokens: list[str]) -> str:
        return tokenizer.decode(tokens)


def create_offline_provider(name: str):
    if name == 'M2M100':
        from providers.m2m100 import M2M100TranslationProvider
        return M2M100TranslationProvider()
    if name == 'Argos':
        return ArgosTranslationProvider()
    if name == 'CTranslate2':
        return CTranslate2TranslationProvider()
    raise ValueError('Provider Offline không được hỗ trợ: ' + name)
