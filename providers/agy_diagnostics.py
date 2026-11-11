"""Bounded observations only. Never decides whether a translation is accepted."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

VERSION = 'agy-safe-protocol-diagnostic-v1'
CLASSES = {'ACTUAL_TOOL_REQUEST', 'TOOL_METADATA_ONLY', 'MALFORMED_RESPONSE',
           'UNKNOWN_PROTOCOL_SHAPE', 'VALID_TRANSLATION_RESPONSE'}
EVENTS = {'result', 'init', 'status', 'step_update', 'message', 'error', 'session',
          'assistant', 'tool_call', 'tool_use', 'permission_request', 'tool_result', 'OTHER'}
TOOL_EVENTS = {'tool_call', 'tool_use', 'permission_request'}  # Existing guard's event contract.
TOOL_KEYS = {'tool_call', 'tool_calls', 'tool_name', 'function_call'}
FIELDS = TOOL_KEYS | {'event', 'type', 'result', 'status', 'response', 'structured_output',
    'output', 'error', 'code', 'message', 'text', 'content', 'translations', 'id', 'num_turns',
    'usage', 'metadata', 'schema', 'input_schema', 'output_schema', 'properties', 'required',
    'additionalProperties', 'items', 'description', 'arguments', 'input', 'function', 'name',
    'tools', 'tool_declarations', 'parameters', 'minLength', 'maxLength', 'minItems', 'maxItems'}
TYPES = {'object', 'array', 'string', 'boolean', 'integer', 'number', 'null'}
CODES = {'NONE', 'INVALID_RESPONSE', 'PROVIDER_UNAVAILABLE', 'QUOTA_EXCEEDED', 'RATE_LIMITED',
         'AUTH_REQUIRED', 'TIMEOUT', 'CANCELLED', 'REQUEST_LIMIT', 'INVALID_REQUEST', 'OTHER_ERROR',
         'NETWORK_ERROR', 'RESPONSE_BLOCKED','MODEL_UNAVAILABLE'}
REASONS = {'TOOL_INDICATOR', 'JSON_PARSE', 'INVALID_EVENT', 'RESULT_COUNT', 'AGENT_TURNS',
           'RESPONSE_STRING', 'SCHEMA', 'COUNT', 'FIELDS', 'ITEM', 'MISSING_ID', 'NONE', 'TRANSPORT'}
REASON_MAP = {'Unexpected tool use': 'TOOL_INDICATOR', 'Invalid event': 'INVALID_EVENT',
    'Missing or duplicate result': 'RESULT_COUNT', 'Unexpected agent turns': 'AGENT_TURNS',
    'Missing response string': 'RESPONSE_STRING', 'Schema mismatch': 'SCHEMA',
    'Count mismatch': 'COUNT', 'Unexpected fields': 'FIELDS', 'Invalid item': 'ITEM',
    'Missing region': 'MISSING_ID', 'JSON_PARSE': 'JSON_PARSE'}


def kind(value):
    if value is None: return 'null'
    if isinstance(value, bool): return 'boolean'
    if isinstance(value, dict): return 'object'
    if isinstance(value, list): return 'array'
    if isinstance(value, str): return 'string'
    if isinstance(value, int): return 'integer'
    return 'number'


def declaration(value, depth=0):
    """Recognize only a small JSON-Schema type declaration, NOT an AGY tools schema.

    This vocabulary is already used by output_schema. Arbitrary 'metadata/tools'
    fields or unfamiliar declarations are not sufficient evidence of metadata only.
    """
    allowed = {'type', 'properties', 'required', 'additionalProperties', 'items',
               'description', 'minLength', 'maxLength', 'minItems', 'maxItems'}
    if (depth > 8 or not isinstance(value, dict) or len(value) > 12 or
            set(value) - allowed or not isinstance(value.get('type'),str) or value.get('type') not in TYPES):
        return False
    props = value.get('properties', {})
    if not isinstance(props, dict) or len(props) > 64:
        return False
    if any(not declaration(v, depth+1) for v in props.values()):
        return False
    if 'items' in value and not declaration(value['items'], depth+1):
        return False
    if 'required' in value and (not isinstance(value['required'], list) or
                               any(not isinstance(k, str) for k in value['required'])):
        return False
    if 'additionalProperties' in value and not isinstance(value['additionalProperties'], bool):
        return False
    return True


def observe(stdout, stderr, exit_code, decoder, accepted, code='NONE', reason='NONE'):
    """Never retain input values, error messages, unknown keys, text or stderr."""
    data = dict(version=VERSION, timestamp=datetime.now(timezone.utc).isoformat(),
        stdout_bytes=len(stdout), stderr_bytes=len(stderr), exit_code=exit_code,
        ndjson_lines=len(stdout.splitlines()), classification='UNKNOWN_PROTOCOL_SHAPE',
        parser_error_code=code, parser_reason=REASON_MAP.get(reason, reason),
        guard_decision='ACCEPT' if accepted else 'REJECT', pending_preserved=not accepted,
        retry=False, translation_cached=False, events=[], tool_indicators=[],
        scan_truncated=False, unknown_event_count=0, malformed_lines=0)
    events, hits, schema = [], [], []
    nodes = 0
    if len(stdout) > 1_000_000:
        data['scan_truncated'] = True
    else:
        for index, line in enumerate(stdout.splitlines()):
            if index >= 128:
                data['scan_truncated'] = True
                break
            if not line.strip():
                continue
            try:
                event = decoder(line.decode('utf-8'))
            except Exception:
                data['malformed_lines'] += 1
                continue
            events.append(event)
            label = event.get('event', event.get('type')) if isinstance(event, dict) else None
            safe_label = label if isinstance(label, str) and label in EVENTS else 'OTHER'
            if safe_label == 'OTHER': data['unknown_event_count'] += 1
            data['events'].append(dict(index=index, event_type=safe_label, value_type=kind(event)))
            if isinstance(event, dict) and isinstance(event.get('event'),str) and event.get('event') in TOOL_EVENTS:
                # Request tag alone is not proof of a full invocation schema.
                # Require an explicit named action with an argument/input object.
                # These are manual internal contracts, not claims about captured AGY.
                name = event.get('tool_name', event.get('name'))
                explicit = isinstance(name,str) and bool(name.strip()) and (
                    isinstance(event.get('arguments'),dict) or isinstance(event.get('input'),dict))
                hits.append(dict(event_index=index, event_type=safe_label, path='$.event',
                                 value_type='string', evidence='EXPLICIT_REQUEST_EVENT' if explicit
                                 else 'AMBIGUOUS_TOOL_FIELD'))
            def walk(value, path='$', depth=0, in_declaration=False):
                nonlocal nodes
                nodes += 1
                if nodes > 4096 or depth > 24:
                    data['scan_truncated'] = True
                    return
                if len(schema) < 512:
                    schema.append((path, kind(value)))
                if isinstance(value, dict):
                    is_declaration = in_declaration or declaration(value)
                    for key, child in value.items():
                        if nodes > 4096: break
                        child_path = (path + ('.'+key if key in FIELDS else '[*]'))[:160]
                        if key in TOOL_KEYS and bool(child) and len(hits) < 32:
                            hits.append(dict(event_index=index, event_type=safe_label, path=child_path,
                                value_type=kind(child), evidence='TYPE_DECLARATION' if is_declaration
                                else 'AMBIGUOUS_TOOL_FIELD'))
                        walk(child, child_path, depth+1, is_declaration)
                elif isinstance(value, list):
                    if len(value) > 64: data['scan_truncated'] = True
                    for n, child in enumerate(value[:64]):
                        if nodes > 4096: break
                        walk(child, (path+f'[{n}]')[:160], depth+1, in_declaration)
            walk(event)
    data['schema_fingerprint'] = hashlib.sha256(json.dumps(schema, separators=(',', ':')).encode()).hexdigest()
    data['tool_indicators'] = hits[:32]
    if any(h['evidence']=='EXPLICIT_REQUEST_EVENT' for h in hits):
        data['classification'] = 'ACTUAL_TOOL_REQUEST'
    elif hits:
        data['classification'] = ('TOOL_METADATA_ONLY' if not data['scan_truncated'] and
            all(h['evidence']=='TYPE_DECLARATION' for h in hits) else 'UNKNOWN_PROTOCOL_SHAPE')
    elif accepted:
        # Legacy permits auxiliary events; observation never adds an event allowlist.
        data['classification'] = 'VALID_TRANSLATION_RESPONSE'
    elif data['malformed_lines'] or any(not isinstance(e, dict) for e in events):
        data['classification'] = 'MALFORMED_RESPONSE'
    elif data['parser_error_code']=='INVALID_RESPONSE' and any(
            isinstance(e, dict) and e.get('event')=='result' for e in events):
        data['classification'] = 'MALFORMED_RESPONSE'
    return sanitize(data)


def sanitize(value):
    """Second boundary at the log writer. Reject raw/untrusted metadata fields."""
    if not isinstance(value, dict): value = {}
    out = {'version': VERSION}
    from providers.agy_models import MODEL_IDS
    if isinstance(value.get('model'),str) and value['model'] in MODEL_IDS:out['model']=value['model']
    if isinstance(value.get('effort'),str) and value['effort'] in ('low','medium','high','default'):out['effort']=value['effort']
    enums = {'classification': CLASSES, 'parser_error_code': CODES, 'parser_reason': REASONS,
             'guard_decision': {'ACCEPT', 'REJECT', 'STOP', 'CANCELLED'}}
    for key, choices in enums.items():
        item = value.get(key)
        out[key] = item if isinstance(item, str) and item in choices else (
            'UNKNOWN_PROTOCOL_SHAPE' if key=='classification' else 'OTHER_ERROR' if key=='parser_error_code'
            else 'NONE' if key=='parser_reason' else 'STOP')
    for key in ('stdout_bytes', 'stderr_bytes', 'ndjson_lines', 'unknown_event_count', 'malformed_lines',
                'page_count', 'region_count', 'source_characters', 'request_number'):
        item=value.get(key)
        if type(item) is int and 0 <= item <= 1_000_000_000: out[key]=item
    code=value.get('exit_code')
    out['exit_code']=code if type(code) is int and -2**31 <= code < 2**32 else None
    for key in ('scan_truncated', 'pending_preserved', 'retry', 'translation_cached', 'stream_limit_exceeded',
                'observation_failed'):
        out[key]=value.get(key) is True
    for key in ('schema_fingerprint', 'batch_id', 'model_identity_hash'):
        item=value.get(key)
        if isinstance(item,str) and re.fullmatch('[a-f0-9]{64}',item): out[key]=item
    stamp=value.get('timestamp')
    if isinstance(stamp,str) and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?\+00:00',stamp):
        out['timestamp']=stamp
    ver=value.get('cli_version')
    if isinstance(ver,str) and re.fullmatch(r'\d{1,3}\.\d{1,3}\.\d{1,3}',ver): out['cli_version']=ver
    for key, limit in [('events',128),('tool_indicators',32)]:
        out[key]=[]
        items=value.get(key,[])
        for item in items[:limit] if isinstance(items,list) else []:
            if not isinstance(item,dict): continue
            entry={}
            index=item.get('event_index',item.get('index'))
            if type(index) is int and 0 <= index < 128: entry['event_index']=index
            entry['event_type']=item.get('event_type') if isinstance(item.get('event_type'),str) and item['event_type'] in EVENTS else 'OTHER'
            entry['value_type']=item.get('value_type') if isinstance(item.get('value_type'),str) and item['value_type'] in TYPES else 'null'
            if key=='tool_indicators':
                path=item.get('path')
                tokens=re.findall(r'\.([A-Za-z_][A-Za-z_0-9]*)',path) if isinstance(path,str) else []
                safe = (isinstance(path,str) and len(path)<=160 and path.startswith('$') and
                    re.fullmatch(r'\$(?:\.[A-Za-z_][A-Za-z_0-9]*|\[(?:\*|[0-9]{1,2})\])*',path) and
                    all(t in FIELDS for t in tokens))
                entry['path']=path if safe else '$[*]'
                evidence=item.get('evidence')
                entry['evidence']=evidence if isinstance(evidence,str) and evidence in {'EXPLICIT_REQUEST_EVENT','TYPE_DECLARATION',
                    'AMBIGUOUS_TOOL_FIELD'} else 'AMBIGUOUS_TOOL_FIELD'
            out[key].append(entry)
    return out


def transport(code, stdout_bytes=0, stderr_bytes=0, ndjson_lines=0, exit_code=None, limited=False):
    return sanitize(dict(timestamp=datetime.now(timezone.utc).isoformat(),
        parser_error_code=code, parser_reason='TRANSPORT', classification='UNKNOWN_PROTOCOL_SHAPE',
        guard_decision='CANCELLED' if code=='CANCELLED' else 'STOP', pending_preserved=True,
        stdout_bytes=stdout_bytes, stderr_bytes=stderr_bytes, ndjson_lines=ndjson_lines,
        exit_code=exit_code, stream_limit_exceeded=limited))
