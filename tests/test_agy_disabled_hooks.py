"""Local config fixtures only; never starts AGY or accesses an account."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.agy import check_automatic_extensions
from providers.online import OnlineProviderError


class DisabledHooksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / '.gemini/config'
        self.config.mkdir(parents=True)
        self.env = patch.dict(os.environ, USERPROFILE=str(self.root))
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def write(self, value):
        (self.config / 'hooks.json').write_text(json.dumps(value), encoding='utf-8')

    def definition(self, **changes):
        return dict(enabled=False, Stop=[dict(type='command', command='fixture-never-executed')], **changes)

    def blocked(self):
        with self.assertRaises(OnlineProviderError) as caught:
            check_automatic_extensions(self.root)
        self.assertEqual(caught.exception.code, 'AGY_AUTOMATIC_EXTENSIONS')

    def test_explicit_disabled_keeps_handlers_and_file_unchanged(self):
        self.write({'status': self.definition()})
        before = (self.config / 'hooks.json').read_bytes()
        check_automatic_extensions(self.root)
        self.assertEqual(before, (self.config / 'hooks.json').read_bytes())

    def test_default_enabled_active_and_wrong_types_block(self):
        for value in [None, True, 'false', 0, [], {}]:
            with self.subTest(value=value):
                definition = self.definition()
                if value is None:
                    definition.pop('enabled')
                else:
                    definition['enabled'] = value
                self.write({'status': definition})
                self.blocked()

    def test_disabled_sibling_cannot_hide_active_hook(self):
        self.write({'hooks': self.definition(), 'another': {'Stop': []}})
        self.blocked()

    def test_unknown_schema_and_wrong_handler_types_block(self):
        for definition in [dict(enabled=False, UnknownEvent=[]),
                           dict(enabled=False, Stop=[{'command': 42}]),
                           dict(enabled=False, PreToolUse=[{'matcher': '*', 'hooks': 'invalid'}]),
                           dict(enabled=False, Stop=[{'command': 'fixture', 'timeout': True}])]:
            self.write({'status': definition})
            self.blocked()

    def test_mcp_remains_blocked_even_when_hooks_disabled(self):
        self.write({'status': self.definition()})
        (self.config / 'mcp_config.json').write_text('{"mcpServers":{"fixture":{}}}', encoding='utf-8')
        self.blocked()

    def test_workspace_hooks_and_plugin_store_fail_closed(self):
        workspace = self.root / '.agents'
        workspace.mkdir()
        (workspace / 'hooks.json').write_text('{"active":{"enabled":true}}', encoding='utf-8')
        self.blocked()
        (workspace / 'hooks.json').write_text('{}', encoding='utf-8')
        plugins = self.root / '.gemini/antigravity-cli/plugins'
        plugins.mkdir(parents=True)
        (plugins / 'unreviewed.json').write_text('{}', encoding='utf-8')
        self.blocked()

    def test_duplicate_keys_and_non_object_block(self):
        for text in ['{"status":{"enabled":false,"enabled":true}}', '[]', '{invalid']:
            (self.config / 'hooks.json').write_text(text, encoding='utf-8')
            self.blocked()


if __name__ == '__main__':
    unittest.main()
