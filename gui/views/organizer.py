import configparser
import os
import shutil

from PyQt6.QtWidgets import (
    QMainWindow, QPushButton, QLineEdit, QTextEdit, QVBoxLayout,
    QHBoxLayout, QWidget, QStackedWidget, QFileDialog, QLabel,
    QSlider, QSizePolicy, QCheckBox, QMessageBox, QGridLayout
)
from PyQt6.QtGui import QFont, QIcon, QAction, QFontDatabase
from PyQt6.QtCore import Qt, QFile, QTextStream, QIODevice
from PyQt6 import QtCore

from connor.processes import (
    get_file_word_list, rename_folders, sim_organize, organize
)
from connor import (
    init, data_path, static_path, tmp_path, font_path
)
from connor.tree_builder import make_tree
from connor.reader import prep_files
from gui.views.settings import Settings
from gui.views.about import About


class ConnorGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)

        # Loads models
        self.model, self.stop_words, self.lda_model, self.vectorizer = init()

        # Loads the default settings from config file
        self.settings = configparser.ConfigParser()
        self.settings.read(os.path.join(data_path, "config.ini"))

        self.folder_name_length = int(self.settings["Parameters"].get("folder_name_length", 3))
        self.reading_word_limit = int(self.settings["Parameters"].get("reading_word_limit", 200))
        self.similarity_threshold = int(self.settings["Parameters"].get("similarity_threshold", 50))
        
        self.init_ui()

    def init_ui(self):
        self.setGeometry(550, 250, 850, 600)
        self.setWindowTitle("Smart File Organizer")
        self.load_stylesheet("style.css")

        # Window
        self.stacked_widget = QStackedWidget(self)
        self.central_layout = QVBoxLayout(self.central_widget)
        self.central_layout.addWidget(self.stacked_widget)

        # Menubar
        self.view_action = None
        menu_bar = self.menuBar()
        self.setup_menu_bar(menu_bar)

        # Default organization variables
        self.copy_files = False
        self.directories = []
        self.file_list = []
        self.misc_list = []
        self.num_files = 0
        self.tmp_folder = os.path.join(tmp_path, "Organized_Files")

        # Screens 
        self.screen1 = QWidget()
        self.screen2 = QWidget()
        self.screen3 = QWidget()
        self.screen4 = QWidget()
        self.screen5 = QWidget()

        self.stacked_widget.addWidget(self.screen1)
        self.stacked_widget.addWidget(self.screen2)
        self.stacked_widget.addWidget(self.screen3)
        self.stacked_widget.addWidget(self.screen4)
        self.stacked_widget.addWidget(self.screen5)

        self.create_screen1()
        self.create_screen2()
        self.create_screen3()
        self.create_screen4()
        self.create_screen5()

        self.current_screen = 0
        self.stacked_widget.setCurrentIndex(self.current_screen)

        # Fonts
        custom_font = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont(os.path.join(font_path, "Coder's Crux.ttf")))[0]
        self.update_custom_fonts(custom_font)

    # Loads styling for the application
    def load_stylesheet(self, file_name):
        css_file = os.path.join(static_path, file_name)
        file = QFile(css_file)
        if file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
            stream = QTextStream(file)
            self.setStyleSheet(stream.readAll())

    # Create Menu Bar
    def setup_menu_bar(self, menu_bar):
        menus = {
            "File": {"Exit": self.close},
            "Edit": {"Settings": self.show_settings},
            "View": {"Menu Bar": self.toggle_menubar},
            "Help": {"About": self.show_about},
        }

        for menu_name, menu_items in menus.items():
            menu = menu_bar.addMenu(menu_name)
            for item_name, item_action in menu_items.items():
                action = QAction(item_name, self)
                action.triggered.connect(item_action)
                menu.addAction(action)
                
                if item_name == "Menu Bar":
                    self.view_action = action
    
    # Alt key toggles menubar 
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Alt:
            self.view_action.setChecked(not self.view_action.isChecked())
            self.toggle_menubar()

    def toggle_menubar(self):
        if self.menuBar().isVisible():
            self.menuBar().hide()
        else:
            self.menuBar().show()

    # Updates font
    def update_font(self, widget, font, size=12):
        upd_font = QFont(font)
        upd_font.setPointSize(size)
        widget.setFont(upd_font)

    # Updates elements iwth custom font
    def update_custom_fonts(self, custom_font):
        for button in self.findChildren(QPushButton):
            self.update_font(button, custom_font, 24)

        for slider in self.findChildren(QLabel):
            self.update_font(slider, custom_font, 24)

        for text in self.findChildren(QTextEdit):
            self.update_font(text, "Monospace", 14)

    # Settings pop-up (Allows the user to change default params)
    def show_settings(self):
        settings = Settings(self.settings, self)
        settings.exec()

    # Tutorial pop-up (Shows General app instructions)
    def show_about(self):
        about = About(self)
        about.exec()

    # Allows user to go back to the previous screen
    def return_button(self, prev_screen, parent=None):
        return_button = QPushButton("Return", parent)
        return_button.setGeometry(720, 5, 100, 30)
        return_button.clicked.connect(lambda _, screen=prev_screen: self.stacked_widget.setCurrentWidget(screen))
        return return_button

    # Update move/copy files checkbox
    def copy_files_checkbox_state(self):
        checkbox = self.sender()
        if checkbox.isChecked():
            self.copy_files = True
        else:
            self.copy_files = False
    
    # Main Menu Screen
    def create_screen1(self):
        layout = QVBoxLayout()
        self.screen1.setLayout(layout) 

        button_layout = QHBoxLayout()

        # Select folder button
        select_folder_button = QPushButton("SELECT FOLDER", parent=self.screen1)
        select_folder_button.setFixedSize(200, 60)

        # Upload and organize files button
        upload_files_button = QPushButton("UPLOAD FILES", parent=self.screen1)
        upload_files_button.setFixedSize(200, 60)

        select_folder_button.clicked.connect(self.show_screen2)
        upload_files_button.clicked.connect(self.show_screen3)

        button_layout.addWidget(select_folder_button)
        button_layout.addWidget(upload_files_button)

        # Parameter Sliders 
        slider1_layout = QHBoxLayout()
        self.slider1_label = QLabel(f"Max Folder Name Length: <span style='color:#75a7ad;'>{self.folder_name_length} words</span>")
        slider1 = QSlider(Qt.Orientation.Horizontal)
        slider1.setFixedWidth(200)
        slider1.setRange(2, 5)
        slider1.setValue(self.folder_name_length)
        slider1.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        slider1.valueChanged.connect(self.slider1_changed)
        slider1_layout.addWidget(self.slider1_label)
        slider1_layout.addWidget(slider1)

        slider2_layout = QHBoxLayout()
        self.slider2_label = QLabel(f"Word Limit For Reading File: <span style='color:#75a7ad;'>{self.reading_word_limit} words</span>")
        slider2 = QSlider(Qt.Orientation.Horizontal)
        slider2.setRange(100, 1000)
        slider2.setFixedWidth(200)
        slider2.setValue(self.reading_word_limit)
        slider2.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        slider2.valueChanged.connect(self.slider2_changed)
        slider2_layout.addWidget(self.slider2_label)
        slider2_layout.addWidget(slider2)
 
        slider3_layout = QHBoxLayout()
        self.slider3_label = QLabel(f"Similarity Threshold Percent: <span style='color:#75a7ad;'>{self.similarity_threshold} %</span>")
        slider3 = QSlider(Qt.Orientation.Horizontal)
        slider3.setFixedWidth(200)
        slider3.setRange(0, 100)
        slider3.setValue(self.similarity_threshold)
        slider3.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        slider3.valueChanged.connect(self.slider3_changed)
        slider3_layout.addWidget(self.slider3_label)
        slider3_layout.addWidget(slider3)  

        layout.addLayout(button_layout)
        layout.addLayout(slider1_layout)
        layout.addLayout(slider2_layout)
        layout.addLayout(slider3_layout)

    # Select Folder Screen
    def create_screen2(self):
        layout = QVBoxLayout()
        top_section = QVBoxLayout()
        inp_layout = QHBoxLayout()
        bot_section = QVBoxLayout()
        self.screen2.setLayout(layout)

        # Select Folder button
        select_button = QPushButton(parent=self.screen2)
        select_button.setIcon(QIcon(os.path.join(static_path, "icons/folder.png")))
        select_button.setIconSize(QtCore.QSize(100, 100))
        select_button.setFixedSize(50, 50)

        # Folder input field
        self.folder_path_input = QLineEdit()
        self.folder_path_input.setPlaceholderText("Enter Folder Path")
        self.folder_path_input.setFixedHeight(50)
        self.update_font(self.folder_path_input, "Monospace", 14)

        # Organize button
        organize_button = QPushButton("ORGANIZE SELECTED FOLDER", parent=self.screen2)
        organize_button.setFixedSize(820, 50)

        inp_layout.addWidget(select_button)
        inp_layout.addWidget(self.folder_path_input)
        top_section.addLayout(inp_layout)

        # selected folder label
        self.select_folder_label = QLabel(f"Your Selected Folder Before Organization:", parent=self.screen2)
        self.select_folder_label.setFixedSize(600, 30)

        # Box for displaying selected folder
        self.select_folder_tab = QTextEdit(parent=self.screen2)
        self.select_folder_tab.setReadOnly(True)
        self.select_folder_tab.setFixedWidth(820)
        self.select_folder_tab.setFixedHeight(200)

        bot_section.addWidget(self.select_folder_label)
        bot_section.addWidget(self.select_folder_tab)
        bot_section.addWidget(organize_button)

        organize_button.clicked.connect(self.organize_selected_folder)
        select_button.clicked.connect(self.select_folder)

        layout.addLayout(top_section)
        layout.addLayout(bot_section)
        
        # Return to previous screen button
        self.return_button(self.screen1, self.screen2)

    # Upload Files Screen
    def create_screen3(self):
        layout = QHBoxLayout()
        left_section = QVBoxLayout()
        right_section = QVBoxLayout()
        util_layout = QHBoxLayout()
        self.screen3.setLayout(layout)

        # Upload button
        upload_button = QPushButton(" UPLOAD", parent=self.screen3)
        upload_button.setIcon(QIcon(os.path.join(static_path, "icons/upload.png")))
        upload_button.setIconSize(QtCore.QSize(100, 100))
        upload_button.setFixedSize(300, 150)

        # Organize button
        organize_button = QPushButton("ORGANIZE", parent=self.screen3)
        organize_button.setFixedSize(300, 50)

        # copy files instead of move when user uploads files checkbox
        checkbox2 = QCheckBox("Copy Uploaded Files", parent=self.screen3)
        checkbox2.setFixedSize(200, 25)
    
        left_section.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_section.addWidget(upload_button)
        left_section.addWidget(organize_button)
        left_section.addWidget(checkbox2)

        # Uploaded files label
        self.uploaded_num_files = QLabel(f"Your Uploaded Files: <span style='color:#75a7ad;'>{self.num_files}</span>", parent=self.screen3)
        self.uploaded_num_files.setFixedSize(400, 30)

        # Box for displaying uploaded files
        self.uploaded_files_tab = QTextEdit(parent=self.screen3)
        self.uploaded_files_tab.setReadOnly(True)
        self.uploaded_files_tab.setFixedWidth(450)
        self.uploaded_files_tab.setFixedHeight(450)
        right_section.addSpacing(50) 

        # Loads the already uploaded files
        self.refresh_files()

        # Refresh all the uploaded files button
        refresh_button = QPushButton(" REFRESH", parent=self.screen3)
        refresh_button.setIcon(QIcon(os.path.join(static_path, "icons/refresh.png")))
        refresh_button.setIconSize(QtCore.QSize(30, 30))
        refresh_button.setFixedSize(222, 35)

        # Clear all the uploaded files button
        clear_button = QPushButton(" CLEAR", parent=self.screen3)
        clear_button.setIcon(QIcon(os.path.join(static_path, "icons/clear.png")))
        clear_button.setIconSize(QtCore.QSize(30, 30))
        clear_button.setFixedSize(222, 35)

        util_layout.addWidget(refresh_button)
        util_layout.addWidget(clear_button)
        
        right_section.addWidget(self.uploaded_num_files)
        right_section.addWidget(self.uploaded_files_tab)
        right_section.addLayout(util_layout)

        checkbox2.stateChanged.connect(self.copy_files_checkbox_state)
        upload_button.clicked.connect(self.upload_files)
        organize_button.clicked.connect(self.organize_uploaded_files)
        clear_button.clicked.connect(self.clear_files)
        refresh_button.clicked.connect(self.refresh_files)

        layout.addLayout(left_section)
        layout.addLayout(right_section)

        # Return to previous screen button
        self.return_button(self.screen1, self.screen3)

    # Organized Folder Summary Screen (if user selects a folder)
    def create_screen4(self):
        layout = QVBoxLayout()
        self.screen4.setLayout(layout)

        self.output_title = QLabel("Folder Successfully organized:")
        self.output_title.setFixedSize(400, 30)

        # Organization summary text box
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)

        layout.addWidget(self.output_title)
        layout.addWidget(self.output_text)
        
        # Return to previous screen button
        self.return_button(self.screen2, self.screen4)

    # Organized Folder Summary Screen (if user uploads files)
    def create_screen5(self):
        layout = QVBoxLayout()
        self.screen5.setLayout(layout)

        self.output_title = QLabel("Organized Folder Structure:")
        self.output_title.setFixedSize(400, 30)

        # Organization summary text box
        self.output_text2 = QTextEdit()
        self.output_text2.setReadOnly(True)

        # Send organized files (if uploaded) to computer
        send_to_comp_button = QPushButton("SEND TO COMPUTER", parent=self.screen5)
        send_to_comp_button.setFixedSize(250, 50)
        send_to_comp_button.clicked.connect(self.send_to_computer)

        layout.addWidget(self.output_title)
        layout.addWidget(self.output_text2)
        layout.addWidget(send_to_comp_button)
        
        # Return to previous screen button
        self.return_button(self.screen3, self.screen5)

    # Allows user to choose a folder instead of pasting its path
    def select_folder(self):
        selected_folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if selected_folder.strip():
            self.folder_path_input.setText(selected_folder)
            self.select_folder_tab.setHtml(make_tree(path=selected_folder, dict=selected_folder, is_path_only=True, cli=False))

    # Organizes the selected folder
    def organize_selected_folder(self):
        # Initializing the file names and content, and grouping them into a dictionary
        folder_path = os.path.relpath(self.folder_path_input.text(), os.getcwd())
        prep_files(folder_path, select_folder=True)
        self.file_list, self.misc_list = get_file_word_list(folder_path, self.reading_word_limit, self.stop_words)
        folder_dict, self.misc_list = sim_organize(self.model, self.similarity_threshold/100, self.file_list, self.misc_list)
        
        # Fitting the model based on the data provided
        data_vectorized = self.vectorizer.fit_transform(words[1] for words in self.file_list)
        self.lda_model.fit(data_vectorized)

        # Final organization process
        renamed_dict = rename_folders(self.vectorizer, self.lda_model, folder_dict, 
                                      self.file_list, self.folder_name_length, self.misc_list)
        organize(folder_path, renamed_dict, self.reading_word_limit, self.folder_name_length,
                 self.vectorizer, self.lda_model, self.model, self.stop_words)
        self.output_text.setHtml(make_tree(path=folder_path, dict=folder_path, is_path_only=True, cli=False))

        # Switch to summary screen
        self.show_screen4()

    # Handles uploading the files
    def upload_files(self):
        # Initializing the file names and content, and grouping them into a dictionary
        self.directories, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "All Files (*)")
        prep_files(self.directories, select_folder=False, copy_files=self.copy_files)
        self.refresh_files()

    # Organizes the uploaded files
    def organize_uploaded_files(self):
        # Initializing the file names and content, and grouping them into a dictionary
        self.file_list, self.misc_list = get_file_word_list(self.tmp_folder, self.reading_word_limit, self.stop_words)
        folder_dict, self.misc_list = sim_organize(self.model, self.similarity_threshold/100, self.file_list, self.misc_list)

        # Fitting the model based on the data provided
        data_vectorized = self.vectorizer.fit_transform(words[1] for words in self.file_list)
        self.lda_model.fit(data_vectorized)

        # Final organization process
        renamed_dict = rename_folders(self.vectorizer, self.lda_model, folder_dict, 
                                      self.file_list, self.folder_name_length, self.misc_list)
        organize(self.tmp_folder, renamed_dict, self.reading_word_limit, self.folder_name_length,
                 self.vectorizer, self.lda_model, self.model, self.stop_words)
        self.output_text2.setHtml(make_tree(path=self.tmp_folder, dict=self.tmp_folder, is_path_only=True, cli=False))

        # Switch to summary screen
        self.show_screen5()

    # Allows the user to send the organized files (from uploads) to computer
    def send_to_computer(self):
        send_folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        root_folder = self.tmp_folder
        
        if send_folder.strip():
            for file in os.listdir(root_folder):
                shutil.move(os.path.join(root_folder, file), os.path.join(send_folder, file))
            shutil.rmtree(root_folder)
            
            # Success message pop-up
            pop_up = self.create_pop_up(title="Sucess", content=f"The uploaded files have been organized and sent to the specified folder:\n{send_folder}", icon=QMessageBox.Icon.Information, options=False)
            if pop_up == QMessageBox.StandardButton.Yes:
                self.reset_params()
                self.show_screen1()
        else:
            # Error message pop-up
            pop_up = self.create_pop_up(title="Confirmation", content="If you do not wish to send these files to your computer? then please click 'Yes' to delete them or 'No' to cancel.\n\n The previously uploaded files and the temporary organized folder will be deleted from uploads if you continue with 'Yes' (this does not delete the actual files if you chose to copy instead of move)", icon=QMessageBox.Icon.Question)
            if pop_up == QMessageBox.StandardButton.Yes:
                # Deletes previously organized folder (if ignored by the user)
                shutil.rmtree(root_folder)
                self.reset_params()
                self.show_screen1()
    
    def create_pop_up(self, title, content, icon, options=True):
        pop_up = QMessageBox()
        pop_up.setWindowTitle(title)
        pop_up.setText(content)
        pop_up.setIcon(icon)
        pop_up.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No if options else QMessageBox.StandardButton.Yes)

        return pop_up.exec()

    def clear_files(self):
        shutil.rmtree(self.tmp_folder)
        self.reset_params()

    # Refreshes the uploaded files display on screen 3
    def refresh_files(self):
        self.reset_params()
        if os.path.exists(self.tmp_folder):
            self.num_files = 0
            for file in os.listdir(self.tmp_folder):
                self.num_files += 1
                self.uploaded_files_tab.append(f"<samp>{os.path.basename(file)}<br></samp>")
            self.uploaded_num_files.setText(f"Your Uploaded Files: <span style='color:#75a7ad;'>{self.num_files}</span>")

    # Resets the uploaded files label and text box appropriately
    def reset_params(self):
        self.uploaded_files_tab.setText("")
        self.directories = []
        self.file_list = []
        self.misc_list = []
        self.num_files = 0
        self.uploaded_num_files.setText(f"Your Uploaded Files: <span style='color:#75a7ad;'>{self.num_files}</span>")
    
    # Show/Switch to respective screens
    def show_screen1(self):
        self.current_screen = 0
        self.stacked_widget.setCurrentIndex(self.current_screen)

    def show_screen2(self):
        self.current_screen = 1
        self.stacked_widget.setCurrentIndex(self.current_screen)

    def show_screen3(self):
        self.current_screen = 2
        self.stacked_widget.setCurrentIndex(self.current_screen)

    def show_screen4(self):
        self.current_screen = 3
        self.stacked_widget.setCurrentIndex(self.current_screen)

    def show_screen5(self):
        self.current_screen = 4
        self.stacked_widget.setCurrentIndex(self.current_screen)
    
    # Updates slider values in main menu
    def slider1_changed(self, value):
        self.folder_name_length = value
        self.slider1_label.setText(f"Max Folder Name Length: <span style='color:#75a7ad;'>{value} words</span>")

    def slider2_changed(self, value):
        self.reading_word_limit = value
        self.slider2_label.setText(f"Word Limit For Reading File: <span style='color:#75a7ad;'>{value} words</span>")

    def slider3_changed(self, value):
        self.similarity_threshold = value
        self.slider3_label.setText(f"Similarity Threshold Percent: <span style='color:#75a7ad;'>{value} %</span>")
