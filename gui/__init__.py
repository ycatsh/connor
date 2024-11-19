import sys

from PyQt6.QtWidgets import QApplication

from gui.views import ConnorGUI


def main():
    app = QApplication(sys.argv)
    nlp_file_Organizer = ConnorGUI()
    nlp_file_Organizer.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()