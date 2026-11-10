from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.parse import urlparse

from core.paths import OCR_MODELS, TRANSLATION_MODELS
from core.storage import atomic_json, file_digest
from core.types import CancelledError, MissingModelError


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    engine: str
    languages: str
    url: str
    size_mb: int
    license: str

    @property
    def directory(self) -> Path:
        return (OCR_MODELS if self.engine == 'PaddleOCR' else TRANSLATION_MODELS) / self.id


PADDLE = 'https://paddleocr.bj.bcebos.com/'
CATALOG = [
    ModelSpec('det-ch', 'Phát hiện chữ Trung / đa ngôn ngữ', 'PaddleOCR', 'zh, zt', PADDLE+'PP-OCRv4/chinese/ch_PP-OCRv4_det_infer.tar', 5, 'Apache-2.0'),
    ModelSpec('det-en', 'Phát hiện chữ Anh', 'PaddleOCR', 'en', PADDLE+'PP-OCRv3/english/en_PP-OCRv3_det_infer.tar', 4, 'Apache-2.0'),
    ModelSpec('det-ml', 'Phát hiện chữ Hàn', 'PaddleOCR', 'ko', PADDLE+'PP-OCRv3/multilingual/Multilingual_PP-OCRv3_det_infer.tar', 4, 'Apache-2.0'),
    ModelSpec('cls', 'Hướng chữ 0/180 độ', 'PaddleOCR', 'all', PADDLE+'dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar', 3, 'Apache-2.0'),
    ModelSpec('rec-zh', 'Nhận diện Trung giản thể', 'PaddleOCR', 'zh', PADDLE+'PP-OCRv4/chinese/ch_PP-OCRv4_rec_infer.tar', 11, 'Apache-2.0'),
    ModelSpec('rec-zt', 'Nhận diện Trung phồn thể', 'PaddleOCR', 'zt', PADDLE+'PP-OCRv3/multilingual/chinese_cht_PP-OCRv3_rec_infer.tar', 13, 'Apache-2.0'),
    ModelSpec('rec-ko', 'Nhận diện Hàn', 'PaddleOCR', 'ko', PADDLE+'PP-OCRv4/multilingual/korean_PP-OCRv4_rec_infer.tar', 12, 'Apache-2.0'),
    ModelSpec('rec-en', 'Nhận diện Anh', 'PaddleOCR', 'en', PADDLE+'PP-OCRv4/english/en_PP-OCRv4_rec_infer.tar', 11, 'Apache-2.0'),
    *[ModelSpec(f'translate-{s}_{t}-{version}', f'Dịch {s} → {t}', 'Argos / CTranslate2', f'{s} → {t}',
                f'https://argos-net.com/v1/translate-{s}_{t}-{version}.argosmodel', 100, 'MIT / CC0')
      for s, t, version in [('en', 'vi', '1_9'), ('zh', 'en', '1_9'), ('zt', 'en', '1_9'), ('ko', 'en', '1_1')]],
]


def verify_installation(directory: Path) -> None:
    receipt = directory / 'integrity.json'
    if not receipt.is_file():
        raise MissingModelError(f'Model thiếu hoặc chưa được xác minh: {directory.name}')
    try:
        data = json.loads(receipt.read_text(encoding='utf-8'))
        if not data.get('files'):
            raise ValueError('empty receipt')
        for name, expected in data['files'].items():
            path = directory / name
            if not path.resolve().is_relative_to(directory.resolve()) or not path.is_file() or file_digest(path) != expected:
                raise ValueError('hash mismatch')
    except (OSError, ValueError, KeyError) as exc:
        raise MissingModelError(f'Model hỏng hoặc bị thay đổi: {directory.name}. Xóa và tải lại bằng Model Manager.') from exc


def safe_member(name: str) -> PurePosixPath:
    name = name.replace('\\', '/')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or ':' in name or not path.parts:
        raise ValueError('Archive chứa đường dẫn không an toàn')
    return path


def extract_archive(archive: Path, destination: Path, checkpoint: Callable = lambda: None) -> None:
    """Extract only regular files/directories, with bounded uncompressed size."""
    total = 0
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                checkpoint()
                rel = safe_member(info.filename)
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Không chấp nhận symlink trong archive')
                total += info.file_size
                if total > 2_000_000_000:
                    raise ValueError('Model vượt giới hạn giải nén 2 GB')
                target = destination.joinpath(*rel.parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as source, target.open('wb') as output:
                        shutil.copyfileobj(source, output, length=1024*1024)
    else:
        with tarfile.open(archive) as tf:
            for member in tf:
                checkpoint()
                rel = safe_member(member.name)
                if not member.isfile() and not member.isdir():
                    raise ValueError('Không chấp nhận liên kết hoặc thiết bị trong archive')
                total += member.size
                if total > 2_000_000_000:
                    raise ValueError('Model vượt giới hạn giải nén 2 GB')
                target = destination.joinpath(*rel.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with tf.extractfile(member) as source, target.open('wb') as output:
                        shutil.copyfileobj(source, output, length=1024*1024)


class TranslationModelManager:
    catalog = CATALOG

    def download(self, spec: ModelSpec, progress: Callable[[int, int], None], checkpoint: Callable = lambda: None) -> None:
        if spec.directory.exists():
            verify_installation(spec.directory)
            return
        allowed = {'paddleocr.bj.bcebos.com', 'argos-net.com'}
        parsed = urlparse(spec.url)
        if parsed.scheme != 'https' or parsed.hostname not in allowed:
            raise ValueError('Chỉ tải model từ danh mục chính thức qua HTTPS')
        base = spec.directory.parent
        base.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.download-', dir=base))
        try:
            archive = stage / 'archive.download'
            request = urllib.request.Request(spec.url, headers={'User-Agent': 'ImageTranslatorVN/0.1'})
            try:
                with urllib.request.urlopen(request, timeout=25) as response, archive.open('wb') as stream:
                    final = urlparse(response.geturl())
                    if final.scheme != 'https' or final.hostname not in allowed:
                        raise ValueError('Redirect model ra ngoài nguồn cho phép')
                    length = int(response.headers.get('Content-Length', 0))
                    done = 0
                    while True:
                        checkpoint()
                        block = response.read(256*1024)
                        if not block:
                            break
                        done += len(block)
                        if done > 1_000_000_000:
                            raise ValueError('Tải model vượt 1 GB')
                        stream.write(block)
                        progress(done, length)
                    if not done or (length and done != length):
                        raise IOError('Model tải chưa đầy đủ')
            except urllib.error.URLError:
                raise ConnectionError('Không tải được model; kiểm tra kết nối mạng/proxy. Không có model mới được cài.') from None
            self.install_archive(spec, archive, stage, checkpoint)
        finally:
            if stage.resolve().parent == base.resolve():
                shutil.rmtree(stage)

    def install_archive(self, spec: ModelSpec, archive: Path, stage: Path, checkpoint: Callable = lambda: None) -> None:
        content = stage / 'content'
        content.mkdir()
        extract_archive(archive, content, checkpoint)
        expected = 'inference.pdmodel' if spec.engine == 'PaddleOCR' else 'metadata.json'
        roots = list(content.rglob(expected))
        if len(roots) != 1:
            raise ValueError('Archive không có đúng một model tương thích')
        source = roots[0].parent
        if spec.engine == 'PaddleOCR':
            if not (source / 'inference.pdiparams').is_file():
                raise ValueError('Thiếu Paddle inference.pdiparams')
        else:
            meta = json.loads((source / 'metadata.json').read_text(encoding='utf-8'))
            if f"{meta.get('from_code')} → {meta.get('to_code')}" != spec.languages:
                raise ValueError('Cặp ngôn ngữ trong model không khớp danh mục')
            if not (source / 'model/model.bin').is_file() or not (source / 'sentencepiece.model').is_file():
                raise ValueError('Không phải gói Argos SentencePiece/CTranslate2 tương thích')
        checkpoint()
        files = {str(p.relative_to(source)).replace('\\', '/'): file_digest(p) for p in source.rglob('*') if p.is_file()}
        atomic_json(source / 'integrity.json', {'spec': asdict(spec), 'archive_sha256': file_digest(archive), 'files': files})
        if spec.directory.exists():
            raise FileExistsError('Model đã tồn tại; không ghi đè')
        os.replace(source, spec.directory)

    def delete(self, spec: ModelSpec) -> None:
        target = spec.directory.resolve()
        parent = OCR_MODELS.resolve() if spec.engine == 'PaddleOCR' else TRANSLATION_MODELS.resolve()
        if target.parent != parent or target.name != spec.id:
            raise ValueError('Đường dẫn model ngoài phạm vi cho phép')
        if target.exists():
            shutil.rmtree(target)
