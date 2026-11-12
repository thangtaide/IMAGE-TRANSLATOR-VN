"""Local configuration checks only: no client, key validation or network I/O."""
from dataclasses import dataclass

from providers.gemini_api import MODE, key_available


@dataclass(frozen=True)
class Preflight:
    code: str
    ready: bool
    provider: str = MODE

    def event(self):
        return dict(code=self.code, provider=self.provider, phase='local_preflight',
                    request_sent=False, request_scope='next_action')


def check_configuration(options):
    if options.mode in ('AI Gemini AGY','AI Gemini AGY Whole Chapter') and options.ai_provider == 'groq':
        from providers.groq_api import key_available as groq_key_available
        ready=groq_key_available()
        return Preflight('READY_UNVERIFIED' if ready else 'API_KEY_MISSING',ready,'GroqCloud')
    if options.mode != MODE:
        return Preflight('READY_UNVERIFIED', True)
    if not key_available():
        return Preflight('API_KEY_MISSING', False)
    if not options.gemini_api_free_tier_confirmed:
        return Preflight('FREE_TIER_UNCONFIRMED', False)
    return Preflight('READY_UNVERIFIED', True)
