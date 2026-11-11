"""Small fixed catalog verified with AGY 1.5.5 `models` and session CLI flags.

Gemini variants encode effort in the ID; the explicit flag must agree. Other
models use their exact catalog ID without an unverified effort override.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelChoice:
    key: str
    label: str
    group: str
    variants: tuple[tuple[str,str], ...]
    version: str


MODELS = (
    ModelChoice('gemini-flash','Gemini 3.8 Flash','GEMINI',tuple(
        (effort,'gemini-3.8-flash-'+effort) for effort in ('low','medium','high')),'3.8 Flash'),
    ModelChoice('claude-sonnet','Claude Sonnet','CLAUDE',(('', 'claude-sonnet-4-6'),),'4.6 Thinking'),
    ModelChoice('claude-opus','Claude Opus','CLAUDE',(('', 'claude-opus-4-6-thinking'),),'4.6 Thinking'),
    ModelChoice('gpt-oss','GPT-OSS','GPT',(('', 'gpt-oss-120b-medium'),),'120B Medium'),
)
MODEL_IDS = frozenset(model for choice in MODELS for _,model in choice.variants)
EFFORTS = {'low','medium','high'}


def selection(model: str, effort: str = '') -> tuple[ModelChoice,str | None]:
    for choice in MODELS:
        for configured,identifier in choice.variants:
            if model == identifier:
                if effort not in ('',configured):
                    raise ValueError('Model và mức suy luận không khớp; chọn lại trong Cài đặt.')
                return choice, configured or None
    raise ValueError('Model AGY chưa được hỗ trợ trong danh sách cố định; chọn rõ model khác trong Cài đặt.')


def identifier(key: str, effort: str) -> str:
    for choice in MODELS:
        if choice.key == key:
            for value,model in choice.variants:
                if value == effort:return model
    raise ValueError('Lựa chọn model/effort không hợp lệ.')


def label(model: str, effort: str = '') -> str:
    try:
        choice,value=selection(model,effort)
        return choice.label+' · '+(value.title() if value else 'Mặc định của model')
    except ValueError:return 'Model đã lưu cần kiểm tra trong Cài đặt'


def bind_run_model(options, saved):
    """Pin only AGY selection; explicit switches to Offline/API keep prior behavior."""
    if options.mode == saved.get('mode') == 'AI Gemini AGY':
        options.agy_model=saved.get('agy_model',options.agy_model)
        options.agy_effort=saved.get('agy_effort','')
    return options
