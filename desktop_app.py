import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from src.desktop_window import DashboardWindow


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("Smart Mood Detection")
    try:
        window = DashboardWindow()
    except Exception as exc:
        QMessageBox.critical(None, "Startup error", str(exc))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
