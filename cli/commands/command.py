import configparser
import shutil
import os


from app.processes import (
    get_file_word_list, sim_organize, misc_handler, 
    rename_folders, organize, vectorizer, lda_model
)
from app.tree_builder import make_tree
from app.reader import prep_files
from app import data_path


class ConnorCLI:
    def __init__(self):
        # Loads the default settings from config file
        self.settings = configparser.ConfigParser()
        self.settings.read(os.path.join(data_path, "config.ini"))

        # Load initial parameters from config
        self.folder_name_length = int(self.settings["Parameters"].get("folder_name_length", 3))
        self.reading_word_limit = int(self.settings["Parameters"].get("reading_word_limit", 200))
        self.similarity_threshold = int(self.settings["Parameters"].get("similarity_threshold", 50))

    def update_settings(self, folder_name_length=None, reading_word_limit=None, similarity_threshold=None):
        if folder_name_length is not None:
            self.folder_name_length = folder_name_length
            self.settings["Parameters"]["folder_name_length"] = str(folder_name_length)
        if reading_word_limit is not None:
            self.reading_word_limit = reading_word_limit
            self.settings["Parameters"]["reading_word_limit"] = str(reading_word_limit)
        if similarity_threshold is not None:
            self.similarity_threshold = similarity_threshold
            self.settings["Parameters"]["similarity_threshold"] = str(similarity_threshold)

        # Save updated settings to config file
        with open(os.path.join(data_path, "config.ini"), "w") as configfile:
            self.settings.write(configfile)
        print("Settings updated successfully.")

    def organize_folder(self, folder_path):
        if not os.path.exists(folder_path):
            print(f"Error: The folder '{folder_path}' does not exist.")
            return
        
        terminal_width = shutil.get_terminal_size().columns
        separator = '-' * terminal_width
        print(separator)
        print(f'To customize default settings instead run the command <connor settings -h>\nfolder_name_length: {self.folder_name_length}\nreading_word_limit: {self.reading_word_limit}\nsimilarity_threshold: {self.similarity_threshold}%')
        print(separator)
        print(f"Folder '{folder_path}' is being organized...")
        
        # Preparing files and organizing
        folder_dict = {}
        prep_files(folder_path, select_folder=True)
        self.file_list, misc_list = get_file_word_list(folder_path, self.reading_word_limit)
        folder_dict, misc_list = sim_organize(self.similarity_threshold/100, self.file_list, misc_list)

        # Fitting the model based on the data provided
        data_vectorized = vectorizer.fit_transform(words[1] for words in self.file_list)
        lda_model.fit(data_vectorized)

        # Main Process
        renamed_dict = rename_folders(folder_dict, self.file_list, self.folder_name_length, misc_list)
        print(make_tree(path=folder_path, dict=renamed_dict, is_path_only=False, cli=True))
        print(separator)
        confirm = input(f"The above directory tree explains how the folder will be organized.\nDo you want to continue? [y/n] ")
        if confirm.lower() == 'y' or confirm == '':
            organize(folder_path, renamed_dict, self.reading_word_limit, self.folder_name_length)
            print(f"Folder '{folder_path}' organized successfully.")
            print(separator)
        else:
            print(f"Folder organization aborted. The files in {folder_path} were left untouched.")
            print(separator)