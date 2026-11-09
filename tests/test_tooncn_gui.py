"""Offscreen controls, fake local controller only; no personal Chrome access."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core.paths import ROOT
from core.types import Options


class ToonCNGuiTests(unittest.TestCase):
    def test_connection_off_by_default_and_switch_stays_usable_during_job(self):
        from PySide6.QtWidgets import QApplication
        from ui.comic_sources import ComicSourcesPanel
        from sources.tooncn_connection import ToonCNConnection,active_lease
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='tooncn-gui-test-') as folder:
            root=Path(folder);controller=ToonCNConnection(root/'runtime')
            with patch('sources.tooncn_connection.connection',return_value=controller):
                panel=ComicSourcesPanel(Options(),settings_path=root/'settings.json',database=root/'qa.sqlite3',fixed_kind=2)
                panel.show();app.processEvents()
                self.assertFalse(panel.tooncn_connect.isChecked());self.assertFalse(controller.root.exists())
                panel.tooncn_connect.click();self.assertIsNotNone(active_lease(controller.root))
                panel.set_busy(True);self.assertTrue(panel.tooncn_connect.isEnabled())
                panel.tooncn_connect.click();self.assertIsNone(active_lease(controller.root))
                panel.set_busy(False);panel.close();app.processEvents()
