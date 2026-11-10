"""Local configuration checks only: no client, key validation or network I/O."""
from dataclasses import dataclass

from providers.gemini_api import MODE, key_available


@dataclass(frozen=True)
class Preflight:
    code: str
    ready: bool

    def event(self):
        return dict(code=self.code, provider=MODE, phase='local_preflight',
                    request_sent=False, request_scope='next_action')


def check_configuration(options):
    if options.mode != MODE:
        return Preflight('READY_UNVERIFIED', True)
    if not key_available():
        return Preflight('API_KEY_MISSING', False)
    if not options.gemini_api_free_tier_confirmed:
        return Preflight('FREE_TIER_UNCONFIRMED', False)
    return Preflight('READY_UNVERIFIED', True)
