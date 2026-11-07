from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

import numpy as np

from core.imaging import SUPPORTED, TextRenderer, atomic_save, default_font, erase_text, open_image
from core.ocr import PaddleOCREngine
from core.paths import ROOT
from core.storage import TranslationCache, digest, file_digest
from core.types import CancelledError, MissingModelError, OCRResult, Options
from providers.offline import create_offline_provider
from providers.online import LibreTranslateProvider, MyMemoryProvider, ProviderError

LOGGER = logging.getLogger(__name__)


def natural_key(path: Path) -> list:
    return [(1, int(part)) if part.isdigit() else (0, part.casefold()) for part in re.split(r'(\d+)', str(path))]


def scan_images(source: Path, recursive: bool, output: Path | None = None) -> list[Path]:
    if not source.is_dir():
        raise FileNotFoundError('Thư mục ảnh nguồn không tồn tại')
    output = output.resolve() if output else None
    iterator = source.rglob('*') if recursive else source.iterdir()
    return sorted([path for path in iterator if path.is_file() and not path.is_symlink() and
                   path.suffix.lower() in SUPPORTED and not (output and path.resolve().is_relative_to(output))], key=natural_key)


class JobControl:
    def __init__(self):
        self.condition = threading.Condition()
        self.paused = False
        self.cancelled = False

    def pause(self) -> None:
        with self.condition:
            self.paused = True

    def resume(self) -> None:
        with self.condition:
            self.paused = False
            self.condition.notify_all()

    def cancel(self) -> None:
        with self.condition:
            self.cancelled = True
            self.condition.notify_all()

    def checkpoint(self) -> None:
        with self.condition:
            while self.paused and not self.cancelled:
                self.condition.wait(.2)
            if self.cancelled:
                raise CancelledError('Đã hủy tại checkpoint an toàn')


class TranslationService:
    def __init__(self, options: Options, cache: TranslationCache, control: JobControl,
                 offline=None, online=None):
        self.options, self.cache, self.control = options, cache, control
        self.offline = offline
        self.online = online

    def _offline(self):
        if self.offline is None:
            self.offline = create_offline_provider(self.options.offline_provider)
        return self.offline

    def _online(self):
        if self.online is None:
            self.online = (MyMemoryProvider(checkpoint=self.control.checkpoint) if self.options.online_provider == 'MyMemory'
                           else LibreTranslateProvider(self.options.endpoint, checkpoint=self.control.checkpoint))
        return self.online

    def identity(self) -> str:
        parts = ['literal-numbers-v1', self.options.mode, self.options.allow_online_fallback, self.options.glossary]
        if self.options.mode != 'Online':
            parts.append(self._offline().identity)
        if self.options.mode == 'Online' or (self.options.mode == 'Auto Fallback' and self.options.allow_online_fallback):
            parts.append(self._online().identity)
        return digest(parts)

    def _chunks(self, text: str) -> list[str]:
        # Bound anonymous API query length while retaining every character.
        chunks, current = [], ''
        for char in text:
            if len((current + char).encode('utf-8')) > 450:
                chunks.append(current)
                current = ''
            current += char
        if current:
            chunks.append(current)
        return chunks

    def _translate_using(self, provider, text: str, language: str, context: str) -> str:
        key = digest([text, language, 'vi', provider.identity, self.options.glossary, context, 'glossary-v3-literal-numbers'])
        cached = self.cache.get('translation', key)
        if cached is not None:
            return cached
        # Names retain explicit glossary markers. Numbers stay in their sentence
        # context: untranslated synthetic markers confuse the installed MT models.
        substitutions = []
        protected = text
        for term, replacement in sorted(self.options.glossary.items(), key=lambda pair: len(pair[0]), reverse=True):
            if term and term in protected:
                marker = 'ZXQ' + chr(65 + len(substitutions)//26) + chr(65 + len(substitutions)%26) + 'QXZ'
                protected = protected.replace(term, marker)
                substitutions.append((marker, replacement))
        number_pattern = r'\d+(?:[.,:/%+−-]\d+)*%?'
        expected_numbers = re.findall(number_pattern, protected)
        self.control.checkpoint()
        if provider.online and isinstance(provider, MyMemoryProvider):
            translated = ' '.join(provider.translate(chunk, language) for chunk in self._chunks(protected))
        else:
            translated = provider.translate(protected, language)
        if not translated or not translated.strip():
            raise ProviderError('Provider trả bản dịch rỗng')
        if re.findall(number_pattern, translated) != expected_numbers:
            raise ProviderError('Provider làm mất, đổi hoặc thêm số; không xuất ảnh này.')
        for marker, replacement in substitutions:
            pattern = re.compile(re.escape(marker), flags=re.IGNORECASE)
            if not pattern.search(translated):
                raise ProviderError('Provider làm thay đổi tên riêng/số được bảo vệ; không xuất ảnh này. Hãy thử provider khác.')
            translated = pattern.sub(lambda _: replacement, translated)
        if re.search(r'ZX[QN][A-Z]{2}[QN]XZ', translated, flags=re.I):
            raise ProviderError('Không khôi phục được ký hiệu bảo vệ')
        self.cache.put('translation', key, translated)
        return translated

    def translate(self, text: str, language: str, context: str) -> str:
        if self.options.mode == 'Online':
            return self._translate_using(self._online(), text, language, context)
        try:
            return self._translate_using(self._offline(), text, language, context)
        except (MissingModelError, ProviderError, RuntimeError, ValueError, ImportError):
            if self.options.mode != 'Auto Fallback' or not self.options.allow_online_fallback:
                raise
            self.control.checkpoint()
            return self._translate_using(self._online(), text, language, context)

    def close(self) -> None:
        if self.online is not None and hasattr(self.online, 'close'):
            self.online.close()


class ProcessingManager:
    """One image/model inference at a time; Qt-free and CLI/test friendly."""
    def __init__(self, options: Options, cache: TranslationCache | None = None,
                 control: JobControl | None = None, emit: Callable[[dict], None] = lambda _: None,
                 ocr=None, service=None):
        self.options = options
        self.cache = cache or TranslationCache()
        self.owns_cache = cache is None
        self.control = control or JobControl()
        self.emit = emit
        self.ocr = ocr or PaddleOCREngine()
        self.service = service or TranslationService(options, self.cache, self.control)
        self.source = Path(options.source).resolve()
        self.output = Path(options.output).resolve()
        self.job_id = ''
        self.started = 0.0
        self.counts = {'completed': 0, 'failed': 0, 'skipped': 0}

    def validate(self) -> None:
        if not self.source.is_dir():
            raise FileNotFoundError('Chọn thư mục nguồn tồn tại')
        if self.output == self.source or self.source.is_relative_to(self.output):
            raise ValueError('Thư mục xuất phải tách khỏi ảnh nguồn và không được là thư mục cha của nguồn')
        if not self.output.is_relative_to(ROOT.resolve()) or self.output == ROOT.resolve():
            raise ValueError(f'Mọi kết quả phải nằm trong thư mục con của {ROOT}')
        for reserved in ('models', 'config', 'cache', 'logs', 'ui', 'core', 'providers', 'scripts', 'tests', '.venv', 'assets'):
            if self.output.is_relative_to((ROOT / reserved).resolve()):
                raise ValueError('Thư mục xuất trùng khu vực mã nguồn/model/cache của ứng dụng')
        if self.options.mode not in ('Online', 'Offline', 'Auto Fallback'):
            raise ValueError('Chế độ dịch không hợp lệ')
        if self.options.language not in ('zh', 'zt', 'ko', 'en', 'auto'):
            raise ValueError('Ngôn ngữ OCR không hợp lệ')
        if not (4 <= self.options.font_min <= self.options.font_max <= 200):
            raise ValueError('Cỡ chữ không hợp lệ')
        self.output.mkdir(parents=True, exist_ok=True)

    def destination(self, path: Path) -> Path:
        relative = path.relative_to(self.source)
        suffix = path.suffix.lower() if self.options.output_format == 'original' else '.' + self.options.output_format
        stem = path.stem if self.options.output_format == 'original' else path.name
        if not self.options.preserve_structure:
            stem += '__' + digest(str(relative))[:8]
        # Include job identity: different providers/configs never clobber earlier work.
        name = stem + '.vi-' + self.job_id[:8] + suffix
        destination = self.output / (relative.parent if self.options.preserve_structure else Path()) / name
        if destination.resolve() == path.resolve() or not destination.resolve().is_relative_to(self.output):
            raise ValueError('Đường dẫn đầu ra không an toàn')
        return destination

    def event(self, path: Path | None, stage: str, percent: int, index: int, total: int, **extra) -> None:
        elapsed = time.monotonic() - self.started
        finished = sum(self.counts.values())
        eta = (elapsed / finished * (total-finished)) if finished else None
        self.emit({'file': str(path) if path else '', 'stage': stage, 'percent': percent,
                   'index': index, 'total': total, 'elapsed': elapsed, 'eta': eta,
                   **self.counts, **extra})

    def run(self, only: list[str] | None = None) -> dict:
        self.started = time.monotonic()
        files = []
        errors = []
        state = 'interrupted'
        try:
            self.validate()
            files = scan_images(self.source, self.options.recursive, self.output)
            if only is not None:
                requested = set(only)
                files = [p for p in files if str(p) in requested]
            if not files:
                raise ValueError('Thư mục không có ảnh được hỗ trợ hoặc không còn ảnh cần thử lại')
            self.emit({'type': 'files', 'files': [str(p) for p in files]})
            # Validate model presence before decoding/erasing images.
            ocr_identity = self.ocr.identity(self.options.language)
            service_identity = self.service.identity()
            relevant = self.options.to_dict()
            relevant['imaging_revision'] = 'adaptive-mask-v2'
            relevant['text_region_revision'] = 'preserve-symbol-regions-v1'
            relevant.pop('skip_success', None)
            font_path = Path(self.options.font) if self.options.font else default_font()
            relevant['font_sha256'] = file_digest(font_path)
            if self.options.erase_mode == 'custom' and self.options.mask_path:
                relevant['mask_sha256'] = file_digest(Path(self.options.mask_path))
            self.job_id = digest([relevant, ocr_identity, service_identity, 'pipeline-v3'])
            self.cache.job(self.job_id, self.options, 'running')
            renderer = TextRenderer(self.options)
            for index, path in enumerate(files):
                self.control.checkpoint()
                destination = self.destination(path)
                try:
                    original_hash = file_digest(path)
                    fingerprint = digest([original_hash, relevant, ocr_identity, service_identity])
                    previous = self.cache.item(self.job_id, str(path))
                    if self.options.skip_success and previous and previous['status'] == 'done' and previous['fingerprint'] == fingerprint:
                        if destination.is_file():
                            old = self.cache.get('output-hash', str(destination))
                            if old == file_digest(destination):
                                self.counts['skipped'] += 1
                                self.event(path, 'Bỏ qua', 100, index+1, len(files), output=str(destination))
                                continue
                    # Never overwrite a user-created/modified result with no matching receipt.
                    if destination.exists():
                        known = self.cache.get('output-hash', str(destination))
                        if known != file_digest(destination):
                            raise FileExistsError('File kết quả đã có và không khớp checkpoint; chọn thư mục xuất khác')
                    self.cache.checkpoint(self.job_id, str(path), 'working', fingerprint=fingerprint)
                    self.event(path, 'OCR', 5, index+1, len(files))
                    image = open_image(path)
                    ocr_key = digest([original_hash, ocr_identity, self.options.language, self.options.confidence,
                                      self.options.tile_size, self.options.reading_direction])
                    ocr_data = self.cache.get('ocr', ocr_key)
                    if ocr_data is None:
                        regions, warnings = self.ocr.recognize(np.array(image.convert('RGB')), self.options.language,
                            self.options.confidence, self.options.tile_size, self.options.reading_direction, self.control.checkpoint)
                        self.cache.put('ocr', ocr_key, {'regions': [asdict(r) for r in regions], 'warnings': warnings})
                    else:
                        regions = [OCRResult(**r) for r in ocr_data['regions']]
                        warnings = list(ocr_data['warnings'])
                    # Numerals and punctuation have no language to translate.
                    # Keep their source pixels intact, including false positives
                    # such as a digit detected on a drawing or decorative mark.
                    preserved_regions = [r for r in regions if not any(c.isalpha() for c in r.text)]
                    regions = [r for r in regions if any(c.isalpha() for c in r.text)]
                    if preserved_regions:
                        warnings.append(f'Giữ nguyên {len(preserved_regions)} vùng chỉ có số/ký hiệu; không xóa/chèn lại.')
                    self.control.checkpoint()
                    self.event(path, 'Dịch', 30, index+1, len(files), language=', '.join(sorted({r.language for r in regions})))
                    context = digest([r.text for r in regions])
                    translations = []
                    for n, region in enumerate(regions):
                        self.control.checkpoint()
                        translations.append(self.service.translate(region.text, region.language, context))
                        self.event(path, 'Dịch', 30+int(30*(n+1)/max(1, len(regions))), index+1, len(files))
                    if not regions:
                        warnings.append('Không có vùng chữ cần dịch; giữ nguyên nội dung ảnh.')
                    self.control.checkpoint()
                    self.event(path, 'Xóa chữ', 65, index+1, len(files))
                    erased = erase_text(image, regions, self.options)
                    self.control.checkpoint()
                    self.event(path, 'Chèn chữ', 80, index+1, len(files))
                    rendered = renderer.render(erased, regions, translations)
                    self.control.checkpoint()
                    self.event(path, 'Đang lưu', 95, index+1, len(files))
                    if file_digest(path) != original_hash:
                        raise IOError('Ảnh nguồn thay đổi trong khi xử lý; không ghi kết quả')
                    warnings += atomic_save(rendered, destination, self.options.quality)
                    self.cache.put('output-hash', str(destination), file_digest(destination))
                    self.cache.put('metadata', fingerprint, {'source': str(path), 'output': str(destination),
                        'size': list(image.size), 'regions': [asdict(r) for r in regions],
                        'preserved_regions': [asdict(r) for r in preserved_regions],
                        'translations': translations, 'warnings': warnings})
                    self.cache.checkpoint(self.job_id, str(path), 'done', str(destination), fingerprint, '\n'.join(warnings))
                    self.counts['completed'] += 1
                    self.event(path, 'Hoàn thành', 100, index+1, len(files), output=str(destination), detail='\n'.join(warnings))
                except CancelledError:
                    self.cache.checkpoint(self.job_id, str(path), 'cancelled')
                    raise
                except Exception as exc:
                    self.counts['failed'] += 1
                    errors.append(str(path))
                    detail = str(exc) or type(exc).__name__
                    LOGGER.exception('file=%s stage=processing error=%s', path.name, type(exc).__name__)
                    self.cache.checkpoint(self.job_id, str(path), 'error', detail=detail)
                    self.event(path, 'Lỗi', 100, index+1, len(files), detail=detail)
            state = 'done' if not errors else 'errors'
        except CancelledError:
            state = 'cancelled'
        except Exception as exc:
            LOGGER.exception('Batch initialization failed: %s', type(exc).__name__)
            self.emit({'type': 'fatal', 'detail': str(exc) or type(exc).__name__})
            state = 'error'
        finally:
            if self.job_id:
                self.cache.job(self.job_id, self.options, state)
            self.service.close()
            result = {'type': 'finished', 'state': state, 'errors': errors, **self.counts, 'total': len(files)}
            self.emit(result)
            if self.owns_cache:
                self.cache.close()
        return result
