import os

from PyQt6.QtWidgets import (
    QPushButton, QVBoxLayout, QLabel, QSlider, QDialog
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from PyQt6 import QtCore

from connor import data_path


class Settings(QDialog):
    def __init__(self, settings, parent):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(350, 350)
        self.setModal(True)
        self.settings = settings

        # Layouts
        layout = QVBoxLayout()
        title_layout = QVBoxLayout()
        btn_layout = QVBoxLayout()

        # Fonts
        md_font = QFont()
        md_font.setPointSize(14)
        sm_font = QFont()
        sm_font.setPointSize(12)

        title = QLabel("Change Default Values")
        title.setFont(md_font)
        title_layout.addWidget(title)
        layout.addLayout(title_layout)

        layout.addSpacing(20)

        # Initializing sliders and buttons
        self.setting_label1 = QLabel(f"Folder Name Length: {settings['Parameters']['folder_name_length']}")
        self.setting_label1.setFont(sm_font)
        self.setting_input1 = QSlider(Qt.Orientation.Horizontal)
        self.setting_input1.setRange(2, 5)
        self.setting_input1.setValue(int(settings["Parameters"]["folder_name_length"]))
        self.setting_input1.valueChanged.connect(self.setting_input1_changed)
        layout.addWidget(self.setting_label1)
        layout.addWidget(self.setting_input1)

        self.setting_label2 = QLabel(f"Reading Word Limit: {settings['Parameters']['reading_word_limit']}")
        self.setting_label2.setFont(sm_font)
        self.setting_input2 = QSlider(Qt.Orientation.Horizontal)
        self.setting_input2.setRange(100, 1000)
        self.setting_input2.setValue(int(settings["Parameters"]["reading_word_limit"]))
        self.setting_input2.valueChanged.connect(self.setting_input2_changed)
        layout.addWidget(self.setting_label2)
        layout.addWidget(self.setting_input2)

        self.setting_label3 = QLabel(f"Similarity Threshold: {settings['Parameters']['similarity_threshold']}")
        self.setting_label3.setFont(sm_font)
        self.setting_input3 = QSlider(Qt.Orientation.Horizontal)
        self.setting_input3.setRange(0, 100)
        self.setting_input3.setValue(int(settings["Parameters"]["similarity_threshold"]))
        self.setting_input3.valueChanged.connect(self.setting_input3_changed)
        layout.addWidget(self.setting_label3)
        layout.addWidget(self.setting_input3)

        layout.addSpacing(20)

        update_button = QPushButton("Update")
        update_button.setFixedSize(80, 35)
        update_button.setFont(md_font)
        update_button.clicked.connect(self.save_settings)
        btn_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        btn_layout.addWidget(update_button)
        layout.addLayout(btn_layout)

        self.state_label = QLabel("", self)
        layout.addWidget(self.state_label)
        self.setLayout(layout)

    # Saves new default settings in config file
    def save_settings(self):
        self.settings["Parameters"]["folder_name_length"] = str(self.setting_input1.value())
        self.settings["Parameters"]["reading_word_limit"] = str(self.setting_input2.value())
        self.settings["Parameters"]["similarity_threshold"] = str(self.setting_input3.value())

        with open(os.path.join(data_path, "config.ini"), "w") as file:
            self.settings.write(file)

        self.state_label.setText("Default settings have been updated successfully")

    # Updates slider values in main menu
    def setting_input1_changed(self, value):
        self.setting_label1.setText(f"Folder Name Length: {value}")

    def setting_input2_changed(self, value):
        self.setting_label2.setText(f"Reading Word Limit: {value}")

    def setting_input3_changed(self, value):
        self.setting_label3.setText(f"Similarity Threshold: {value}")
