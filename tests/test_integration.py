"""Real integrations. Never use OCR/MT fixtures in this module."""
from __future__ import annotations

import importlib.util
import os
import socket
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from core.imaging import default_font
from core.models import verify_installation
from core.ocr import PaddleOCREngine
from core.paths import ROOT, TRANSLATION_MODELS
from providers.offline import ArgosTranslationProvider
from providers.online import MyMemoryProvider


class RealOCRTests(unittest.TestCase):
    def run_language(self, code: str, text: str, font: str) -> None:
        if not importlib.util.find_spec('paddleocr') or not importlib.util.find_spec('paddle'):
            self.skipTest('Chưa cài PaddleOCR/PaddlePaddle; không coi OCR thật là PASS')
        engine = PaddleOCREngine()
        try:
            engine.identity(code)
        except Exception as exc:
            self.skipTest(str(exc))
        if not Path(font).is_file():
            self.skipTest('Thiếu font fixture CJK để tạo ảnh OCR thật')
        image = Image.new('RGB', (900, 180), 'white')
        ImageDraw.Draw(image).text((25, 40), text, font=ImageFont.truetype(font, 48), fill='black')
        with patch('socket.socket.connect', side_effect=AssertionError('OCR must not access network')):
            results, _ = engine.recognize(np.array(image), code)
        actual = ''.join(r.text for r in results).replace(' ', '').lower()
        self.assertIn(text.replace(' ', '').lower(), actual)

    def test_english_real(self):
        self.run_language('en', 'Hello world', str(default_font()))

    def test_simplified_chinese_real(self):
        self.run_language('zh', '你好世界', 'C:/Windows/Fonts/msyh.ttc')

    def test_traditional_chinese_real(self):
        self.run_language('zt', '歡迎光臨', 'C:/Windows/Fonts/msjh.ttc')

    def test_korean_real(self):
        self.run_language('ko', '안녕하세요', 'C:/Windows/Fonts/malgun.ttf')


class RealTranslationTests(unittest.TestCase):
    def check_offline(self, source: str, text: str) -> None:
        if not importlib.util.find_spec('ctranslate2') or not importlib.util.find_spec('sentencepiece'):
            self.skipTest('Chưa cài CTranslate2/SentencePiece; chưa kiểm thử dịch Offline thật')
        provider = ArgosTranslationProvider()
        try:
            route = provider.route(source)
        except Exception as exc:
            self.skipTest(str(exc))
        for pair in route:
            verify_installation(provider.packages[pair][0])
        with patch('socket.socket.connect', side_effect=AssertionError('OFFLINE NETWORK VIOLATION')):
            translated = provider.translate(text, source)
        self.assertTrue(translated.strip())
        self.assertNotEqual(translated, text)
        evidence = ROOT / 'logs' / f'real-offline-{source}.txt'
        evidence.write_text(f'{text}\n{translated}\n', encoding='utf-8')

    def test_en_vi_real(self):
        self.check_offline('en', 'Hello, how are you?')

    def test_zh_en_vi_real(self):
        self.check_offline('zh', '你好，你好吗？')

    def test_zt_en_vi_real(self):
        self.check_offline('zt', '你好，歡迎光臨。')

    def test_ko_en_vi_real(self):
        self.check_offline('ko', '안녕하세요. 감사합니다.')

    @unittest.skipUnless(os.environ.get('ITVN_TEST_ONLINE') == '1', 'Online thật opt-in; dùng ITVN_TEST_ONLINE=1 khi có mạng')
    def test_mymemory_live(self):
        provider = MyMemoryProvider()
        try:
            text = provider.translate('Hello world', 'en')
            self.assertTrue(text)
            self.assertNotEqual(text.lower(), 'hello world')
            (ROOT / 'logs' / 'real-online.txt').write_text(text, encoding='utf-8')
        finally:
            provider.close()


class RealGUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not importlib.util.find_spec('PySide6'):
            raise unittest.SkipTest('Thiếu PySide6; chưa xác minh GUI khởi động/không treo')
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_window_opens_and_resizes(self):
        from ui.main_window import MainWindow
        window = MainWindow()
        window.show()
        window.resize(1000, 760)
        self.app.processEvents()
        self.assertTrue(window.isVisible())
        self.assertEqual(window.windowTitle(), 'IMAGE TRANSLATOR VN')
        window.close()

    def test_vietnamese_font_covers_required_glyphs(self):
        from ui.fonts import configure_ui_font, VIETNAMESE_SAMPLE
        from PySide6.QtGui import QRawFont
        report = configure_ui_font()
        self.assertEqual(report['status'], 'PASS', str(report))
        raw = QRawFont.fromFont(self.app.font())
        self.assertTrue(raw.isValid())
        self.assertTrue(all(raw.supportsCharacter(ord(c)) for c in VIETNAMESE_SAMPLE if not c.isspace()))

    def test_real_folder_dialog_integration_mock_selection(self):
        # Qt is real; modal native picker selection is deliberately mocked.
        from ui.main_window import MainWindow
        window = MainWindow()
        with patch('ui.main_window.QFileDialog.getExistingDirectory', return_value=str(ROOT / 'output')):
            window.choose_folder(window.source)
        self.assertEqual(Path(window.source.text()), ROOT / 'output')
        window.close()

    def test_qthread_does_not_block_gui_event_loop(self):
        # Real Qt event loop and QThread; slow job fixture tests UI isolation only.
        from PySide6.QtCore import QTimer
        from ui.workers import ProcessingWorker
        from core.types import Options
        beats = []
        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: beats.append(time.monotonic()))
        timer.start()
        with patch('ui.workers.ProcessingManager') as manager:
            manager.return_value.run.side_effect = lambda _: time.sleep(.25)
            worker = ProcessingWorker(Options())
            worker.start()
            deadline = time.monotonic() + 3
            while worker.isRunning() and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.005)
            self.assertFalse(worker.isRunning())
            self.assertGreater(len(beats), 5)
            worker.wait(1000)
        timer.stop()


if __name__ == '__main__':
    unittest.main()
