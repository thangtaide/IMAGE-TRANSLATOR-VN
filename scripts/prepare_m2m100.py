"""Install an already converted LOCAL M2M100 package. No downloads or pip calls."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.storage import atomic_json, file_digest
from providers.m2m100 import MODEL_DIRECTORY, validate_package


def install_local(converted: Path, tokenizer: Path, destination: Path = MODEL_DIRECTORY) -> Path:
    if destination.exists():
        validate_package(destination)
        return destination  # Never replace a valid or corrupt existing installation.
    config = json.loads((tokenizer / 'config.json').read_text(encoding='utf-8'))
    if config.get('model_type') != 'm2m_100' or config.get('d_model') != 1024:
        raise ValueError('Cần thư mục tokenizer/config của facebook/m2m100_418M.')
    required = ['model.bin', 'config.json', 'shared_vocabulary.json']
    if any(not (converted / name).is_file() for name in required):
        raise ValueError('Thư mục CTranslate2 thiếu model.bin/config.json/shared_vocabulary.json.')
    files = [p for p in converted.iterdir() if p.is_file()]
    files += [tokenizer / 'sentencepiece.bpe.model', tokenizer / 'vocab.json', tokenizer / 'config.json']
    if any(p.is_symlink() or not p.is_file() for p in files):
        raise ValueError('Chỉ nhập file model cục bộ thường, không dùng symlink.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    required_bytes = sum(p.stat().st_size for p in files) + 100_000_000
    if shutil.disk_usage(destination.parent).free < required_bytes:
        raise OSError('Không đủ dung lượng để sao chép model và vùng dự phòng.')
    stage = Path(tempfile.mkdtemp(prefix='.m2m100-install-', dir=destination.parent))
    # Preserve a failed staging folder for diagnosis; never delete source models.
    (stage / 'model').mkdir()
    for path in converted.iterdir():
        if path.is_file():
            shutil.copy2(path, stage / 'model' / path.name)
    for name in ['sentencepiece.bpe.model', 'vocab.json']:
        shutil.copy2(tokenizer / name, stage / name)
    atomic_json(stage / 'm2m100.json', {
        'format': 'm2m100-ct2-v1', 'model_id': 'facebook/m2m100_418M', 'license': 'MIT',
        'source': 'https://huggingface.co/facebook/m2m100_418M',
        'conversion': 'CTranslate2 local conversion; CPU int8 runtime',
        'original_config': config, 'local_converted_directory': str(converted.resolve()),
    })
    atomic_json(stage / 'integrity.json', {'files': {
        str(p.relative_to(stage)).replace('\\', '/'): file_digest(p)
        for p in stage.rglob('*') if p.is_file()}})
    validate_package(stage)
    from core.runtime import prepare_inference_runtime
    ct2 = prepare_inference_runtime()
    import sentencepiece
    sentencepiece.SentencePieceProcessor(model_file=str(stage / 'sentencepiece.bpe.model'))
    engine = ct2.Translator(str(stage / 'model'), device='cpu', compute_type='int8',
                            inter_threads=1, intra_threads=2)
    engine.unload_model()
    del engine
    if destination.exists():
        raise FileExistsError('Model xuất hiện trong lúc cài; không ghi đè.')
    os.rename(stage, destination)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--converted', type=Path, required=True)
    parser.add_argument('--tokenizer', type=Path, required=True)
    args = parser.parse_args()
    try:
        print('Installed local model:', install_local(args.converted, args.tokenizer))
        return 0
    except Exception as exc:
        print(type(exc).__name__ + ': ' + str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
