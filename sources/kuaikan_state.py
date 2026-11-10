"""Decode the data-only Nuxt IIFE format observed in supplied Kuaikan captures.

This is a bounded literal/alias reader, NOT JavaScript evaluation. Calls, operators,
property reads and arbitrary statements are rejected. Only the observed constant
array/object property assignments and one literal return object are accepted.
Never log/serialize the whole state: it can include public comments/user metadata.
"""
from __future__ import annotations

import json
import re

from sources.contracts import StructureChanged

TOKEN = re.compile(r'\s+|"(?:\\.|[^"\\])*"|[A-Za-z_$][A-Za-z0-9_$]*|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|[{}\[\]().,:;=!]')
IDENT = re.compile(r'[A-Za-z_$][A-Za-z0-9_$]*\Z')


class DataReader:
    def __init__(self, tokens: list[str], position=0, env=None):
        self.tokens, self.position = tokens, position
        self.env = env or {}
        self.items = 0

    def take(self, expected=None):
        if self.position >= len(self.tokens):
            raise StructureChanged('Nuxt data bị cắt; không đoán dữ liệu thiếu.')
        value = self.tokens[self.position]
        if expected is not None and value != expected:
            raise StructureChanged('Nuxt data khác grammar literal đã xác minh; không chạy JavaScript.')
        self.position += 1
        return value

    def peek(self):
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def value(self, depth=0):
        self.items += 1
        if depth > 80 or self.items > 150_000:
            raise StructureChanged('Nuxt data vượt giới hạn cấu trúc.')
        token = self.take()
        if token == '{':
            result = {}
            while self.peek() != '}':
                key = self.take()
                if key.startswith('"'):
                    key = json.loads(key)
                elif not IDENT.fullmatch(key):
                    raise StructureChanged('Nuxt object key không hợp lệ.')
                if key in ('__proto__', 'constructor', 'prototype') or key in result:
                    raise StructureChanged('Nuxt object chứa key không an toàn/trùng.')
                self.take(':')
                result[key] = self.value(depth + 1)
                if self.peek() != ',':
                    break
                self.take(',')
            self.take('}')
            return result
        if token == '[':
            result = []
            while self.peek() != ']':
                result.append(self.value(depth + 1))
                if self.peek() != ',':
                    break
                self.take(',')
            self.take(']')
            return result
        if token.startswith('"'):
            return json.loads(token)
        if token in ('null', 'undefined'):
            return None
        if token in ('true', 'false'):
            return token == 'true'
        if token == 'void':
            self.take('0')
            return None
        if token == '!':
            value = self.take()
            if value not in ('0', '1'):
                raise StructureChanged('Nuxt boolean không hợp lệ.')
            return value == '0'
        if token == 'Array':
            # Observed devalue marker for a small sparse array, not an arbitrary call.
            self.take('(')
            length = self.take()
            self.take(')')
            if not re.fullmatch(r'[0-9]{1,4}', length) or int(length) > 1000:
                raise StructureChanged('Nuxt sparse array vượt giới hạn.')
            return [None] * int(length)
        if re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', token):
            return json.loads(token)
        if token in self.env:
            return self.env[token]
        raise StructureChanged('Nuxt data chứa biểu thức chưa hỗ trợ; không thực thi hoặc suy đoán.')


def decode_state(script: str) -> dict:
    if len(script) > 2_000_000:
        raise StructureChanged('Nuxt data quá lớn.')
    tokens = []
    offset = 0
    while offset < len(script):
        match = TOKEN.match(script, offset)
        if not match:
            raise StructureChanged('Nuxt script chứa cú pháp ngoài tập literal được phép.')
        offset = match.end()
        token = match[0]
        if not token.isspace():
            tokens.append(token)
        if len(tokens) > 300_000:
            raise StructureChanged('Nuxt data vượt giới hạn token.')
    reader = DataReader(tokens)
    for token in ('window', '.', '__NUXT__', '=', '(', 'function', '('):
        reader.take(token)
    parameters = []
    while reader.peek() != ')':
        name = reader.take()
        if not IDENT.fullmatch(name) or name in parameters:
            raise StructureChanged('Nuxt alias không hợp lệ.')
        parameters.append(name)
        if reader.peek() != ',':
            break
        reader.take(',')
    reader.take(')')
    reader.take('{')
    start = reader.position
    nesting = 1
    cursor = start
    while cursor < len(tokens) and nesting:
        if tokens[cursor] == '{':
            nesting += 1
        elif tokens[cursor] == '}':
            nesting -= 1
        cursor += 1
    if nesting:
        raise StructureChanged('Nuxt function bị cắt.')
    end = cursor - 1
    arguments = DataReader(tokens, cursor)
    arguments.take('(')
    values = []
    while arguments.peek() != ')':
        values.append(arguments.value())
        if arguments.peek() != ',':
            break
        arguments.take(',')
    for token in (')', ')'):
        arguments.take(token)
    if arguments.peek() == ';':
        arguments.take(';')
    if arguments.peek() is not None or len(values) != len(parameters):
        raise StructureChanged('Nuxt wrapper/alias count không khớp.')
    reader.env = dict(zip(parameters, values))
    while reader.peek() != 'return':
        target = reader.env.get(reader.take())
        if reader.peek() == '.':
            reader.take('.')
            key = reader.take()
            if not isinstance(target, dict) or not IDENT.fullmatch(key) or key in ('__proto__', 'constructor', 'prototype'):
                raise StructureChanged('Nuxt assignment không được phép.')
        else:
            reader.take('[')
            key = reader.value()
            reader.take(']')
            if not isinstance(target, list) or type(key) is not int or not 0 <= key <= 1000:
                raise StructureChanged('Nuxt array assignment không được phép.')
            while len(target) <= key:
                target.append(None)
        reader.take('=')
        value = reader.value()
        reader.take(';')
        target[key] = value
    reader.take('return')
    result = reader.value()
    if reader.peek() == ';':
        reader.take(';')
    if reader.position != end or not isinstance(result, dict):
        raise StructureChanged('Nuxt return khác cấu trúc dữ liệu đã xác minh.')
    return result


def page_payload(document) -> dict | None:
    scripts = [''.join(child for child in node.children if isinstance(child, str))
               for node in document.nodes if node.tag == 'script' and not node.attrs.get('src')]
    matches = [script.strip() for script in scripts if script.lstrip().startswith('window.__NUXT__=')]
    if not matches:
        return None
    if len(matches) != 1:
        raise StructureChanged('Có nhiều Nuxt payload; không chọn tùy ý.')
    root = decode_state(matches[0])
    data = root.get('data')
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise StructureChanged('Nuxt thiếu data page đã xác minh.')
    response = data[0].get('res')
    payload = response.get('data') if isinstance(response, dict) else None
    if not isinstance(payload, dict):
        raise StructureChanged('Nuxt thiếu res.data page đã xác minh.')
    # The caller receives only page metadata, never account/store/comment state.
    return {key: payload[key] for key in ('topic_info', 'comic_info') if key in payload}
