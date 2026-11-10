"""Bounded metadata only. Never retain headers, URLs, text or raw exceptions."""
from datetime import datetime, timezone
import re

STATES = {'NOT_ATTEMPTED', 'ATTEMPT_STARTED', 'RESPONSE_RECEIVED', 'UNKNOWN'}
CODES = {'API_KEY_MISSING', 'FREE_TIER_UNCONFIRMED', 'READY_UNVERIFIED', 'AUTH_REQUIRED',
         'ACCESS_DENIED', 'MODEL_UNAVAILABLE', 'RATE_LIMITED', 'QUOTA_EXCEEDED', 'TIMEOUT',
         'NETWORK_ERROR', 'INVALID_REQUEST', 'INVALID_RESPONSE', 'RESPONSE_BLOCKED',
         'UNEXPECTED_TOOL_USE', 'REQUEST_BUDGET', 'PROVIDER_UNAVAILABLE', 'CANCELLED',
         'NUMERIC_MISMATCH', 'SUCCESS', 'UNKNOWN'}
REASONS = {'PERMISSION_DENIED', 'UNAUTHENTICATED', 'RESOURCE_EXHAUSTED', 'INVALID_ARGUMENT',
           'NOT_FOUND', 'UNAVAILABLE', 'DEADLINE_EXCEEDED', 'INTERNAL',
           'API_KEY_INVALID', 'API_KEY_SERVICE_BLOCKED', 'SERVICE_DISABLED',
           'API_KEY_HTTP_REFERRER_BLOCKED', 'API_KEY_IP_ADDRESS_BLOCKED', 'UNSPECIFIED'}


def clean(info=None):
    info = info if isinstance(info, dict) else {}
    def enum(name, allowed, default):
        value = info.get(name)
        return value if isinstance(value, str) and value in allowed else default
    def identifier(name, pattern):
        value = info.get(name)
        return value if isinstance(value, str) and len(value) <= 64 and re.fullmatch(pattern, value) else None
    def integer(name, low, high):
        value = info.get(name)
        return value if type(value) is int and low <= value <= high else None
    state = enum('request_state', STATES, 'UNKNOWN')
    code = enum('error_code', CODES, 'UNKNOWN')
    category = ('ACCESS' if code in {'AUTH_REQUIRED', 'ACCESS_DENIED', 'MODEL_UNAVAILABLE'} else
                'CONFIGURATION' if code in {'API_KEY_MISSING', 'FREE_TIER_UNCONFIRMED', 'INVALID_REQUEST'} else
                'LIMIT' if code in {'RATE_LIMITED', 'QUOTA_EXCEEDED', 'REQUEST_BUDGET'} else
                'TRANSPORT' if code in {'NETWORK_ERROR', 'TIMEOUT', 'PROVIDER_UNAVAILABLE'} else
                'VALIDATION' if code == 'NUMERIC_MISMATCH' else 'PROTOCOL')
    return dict(provider='Gemini API', model='gemini-2.5-flash',
        timestamp=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        request_state=state, http_attempt_started=None if state == 'UNKNOWN' else state != 'NOT_ATTEMPTED',
        http_response_received=None if state == 'UNKNOWN' else state == 'RESPONSE_RECEIVED',
        http_status=integer('http_status', 100, 599) if state == 'RESPONSE_RECEIVED' else None,
        error_code=code, error_category=category,
        error_reason=enum('error_reason', REASONS, 'UNSPECIFIED'),
        preflight_state=enum('preflight_state', {'API_KEY_MISSING', 'FREE_TIER_UNCONFIRMED', 'READY_UNVERIFIED'}, 'UNKNOWN'),
        request_attempt_id=identifier('request_attempt_id', r'[a-f0-9]{32}'),
        batch_id=identifier('batch_id', r'[a-f0-9]{64}'), job_id=identifier('job_id', r'[a-f0-9]{64}'),
        chapter_id=identifier('chapter_id', r'[0-9]{1,24}'),
        retry_after=integer('retry_after', 0, 9999999), pending_page_count=integer('pending_page_count', 0, 1000000),
        checkpoint_state=enum('checkpoint_state', {'paused_provider', 'cancelled', 'fallback_original', 'error'}, 'UNKNOWN'),
        cache_preservation_state=enum('cache_preservation_state', {'RETAINED'}, 'UNKNOWN'))


def reason_from_error(result):
    """Recognize only explicit enums; no message/metadata values or arbitrary reason."""
    error = result.get('error') if isinstance(result, dict) else None
    if not isinstance(error, dict):
        return 'UNSPECIFIED'
    details = error.get('details', [])
    if isinstance(details, list):
        for detail in details[:16]:
            if isinstance(detail, dict) and detail.get('@type') == 'type.googleapis.com/google.rpc.ErrorInfo':
                value = detail.get('reason')
                if isinstance(value, str) and value in REASONS:
                    return value
    value = error.get('status')
    return value if isinstance(value, str) and value in REASONS else 'UNSPECIFIED'
