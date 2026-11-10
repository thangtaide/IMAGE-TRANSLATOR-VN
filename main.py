from __future__ import annotations

import sys

from core.paths import initialize
from core.storage import configure_logging


def main() -> int:
    initialize()
    configure_logging()
    if '--cache-ui-check' in sys.argv:
        sys.argv.remove('--cache-ui-check')
        from scripts.validate_cache_ui import main as cache_ui_main
        return cache_ui_main()
    if '--acceptance-check' in sys.argv:
        sys.argv.remove('--acceptance-check')
        from scripts.acceptance_readability import main as acceptance_main
        return acceptance_main()
    if '--validate-source-tabs' in sys.argv:
        sys.argv.remove('--validate-source-tabs')
        from scripts.validate_source_tabs import main as validate_source_tabs
        return validate_source_tabs()
    if '--validate-gui-workflow' in sys.argv:
        sys.argv.remove('--validate-gui-workflow')
        from scripts.validate_gui_workflow import main as validate_gui_workflow
        return validate_gui_workflow()
    if '--validate-e2e' in sys.argv:
        sys.argv.remove('--validate-e2e')
        from scripts.validate_e2e import main as validate_e2e_main
        return validate_e2e_main()
    try:
        # Native runtimes must load before Qt's signature/type helpers as well
        # as before Paddle. Models remain lazy and inference stays on workers.
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        from PySide6.QtWidgets import QApplication
        from ui.main_window import MainWindow
    except ImportError as exc:
        message = f'IMAGE TRANSLATOR VN chưa đủ thư viện. Chạy install.bat trước.\n\n{exc}'
        # A native dialog is still available without Qt on Windows.
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, 'Thiếu thư viện', 0x10)
        else:
            print(message, file=sys.stderr)
        return 1
    app = QApplication(sys.argv)
    app.setApplicationName('Image Translator VN')
    app.setOrganizationName('ImageTranslatorVN')
    window = MainWindow()
    window.show()
    if '--smoke-test' in sys.argv:
        from pathlib import Path
        from scripts.gui_smoke_actions import schedule
        index = sys.argv.index('--smoke-report')
        schedule(window, app, Path(sys.argv[index+1]))
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
