"""Punarth AI desktop application.

    pip install -r requirements.txt
    python main.py
"""
import sys

from core import db, seed


def main():
    if "--payment-server" in sys.argv:          # used by the packaged .exe
        from payment_server.server import main as run_server
        run_server()
        return
    db.init_db()
    seed.seed_if_empty()

    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from core import payments_client
    from ui import theme
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Punarth AI")
    app.setStyle("Fusion")
    f = QFont("Segoe UI")
    f.setPointSize(10)
    app.setFont(f)
    app.setStyleSheet(theme.APP_QSS)
    win = MainWindow()
    win.show()
    # Start the local payment server in the background for demos (no-op if already running).
    from ui.widgets import run_async
    run_async(payments_client.ensure_server_running)
    code = app.exec()
    payments_client.stop_server()
    sys.exit(code)


if __name__ == "__main__":
    main()
