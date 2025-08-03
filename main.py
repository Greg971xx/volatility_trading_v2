import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
from core.tws_connector import check_ibkr_connection
from ui.main_window import MainWindow
from PyQt6.QtCore import QObject, pyqtSignal


class EmittingStream(QObject):
    text_written = pyqtSignal(str)

    def write(self, text):
        if text.strip():
            self.text_written.emit(str(text))

    def flush(self):  # obligatoire pour certains appels système
        pass


def check_or_prompt_offline_mode():
    connected = check_ibkr_connection()
    if not connected:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Connexion TWS impossible")
        msg.setText("La connexion à TWS a échoué.\n\nSouhaitez-vous passer en mode hors ligne ?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        choice = msg.exec()

        if choice == QMessageBox.StandardButton.Yes:
            return "offline"
        else:
            return "quit"
    return "online"

def main():
    app = QApplication(sys.argv)

    mode = check_or_prompt_offline_mode()

    if mode == "quit":
        sys.exit(0)
    elif mode == "offline":
        offline_mode = True
    else:
        offline_mode = False

    window = MainWindow(offline_mode=offline_mode)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()


