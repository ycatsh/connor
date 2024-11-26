import configparser
import shutil
import os

from connor import (
    init, data_path,
)
from connor.processes import (
    get_file_word_list, sim_organize, 
    rename_folders, organize
)
from connor.tree_builder import make_tree
from connor.reader import prep_files


class ConnorCLI:
    def __init__(self):
        # Loads the default settings from config file
        self.settings = configparser.ConfigParser()
        self.settings.read(os.path.join(data_path, "config.ini"))

        # Load initial parameters from config
        self.folder_name_length = int(self.settings["Parameters"].get("folder_name_length", 3))
        self.reading_word_limit = int(self.settings["Parameters"].get("reading_word_limit", 200))
        self.similarity_threshold = int(self.settings["Parameters"].get("similarity_threshold", 50))

        # Seperator
        terminal_width = shutil.get_terminal_size().columns
        self.separator = '-' * terminal_width

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

    def show_settings(self):
        print("To see how to update: Connor settings [-h]")
        print("\nCurrent settings:")
        print(f"  {'folder words limit':<22} {self.folder_name_length}")
        print(f"  {'reading limit':<22} {self.reading_word_limit}")
        print(f"  {'similarity threshold':<22} {self.similarity_threshold}%")

    def organize_folder(self, folder_path):
        model, stop_words, lda_model, vectorizer = init()
        if not os.path.exists(folder_path):
            print(f"Error: The folder '{folder_path}' does not exist.")
            return
        
        print(self.separator)
        print(f'To customize default settings instead run the command <connor settings -h>\nfolder_name_length: {self.folder_name_length}\nreading_word_limit: {self.reading_word_limit}\nsimilarity_threshold: {self.similarity_threshold}%')
        print(self.separator)
        print(f"Folder '{folder_path}' is being organized...")
        
        # Preparing files and organizing
        folder_dict = {}
        prep_files(folder_path, select_folder=True)
        self.file_list, misc_list = get_file_word_list(folder_path, self.reading_word_limit, stop_words)
        folder_dict, misc_list = sim_organize(model, self.similarity_threshold / 100, self.file_list, misc_list)

        # Fitting the model based on the data provided
        data_vectorized = vectorizer.fit_transform(words[1] for words in self.file_list)
        lda_model.fit(data_vectorized)

        # Main Process
        renamed_dict = rename_folders(vectorizer, lda_model, folder_dict, self.file_list, 
                                      self.folder_name_length, misc_list)
        print(make_tree(path=folder_path, dict=renamed_dict, is_path_only=False, cli=True))
        print(self.separator)
        
        # Confirm Organization
        try:
            confirm = input(f"The above directory tree explains how the folder will be organized.\nDo you want to continue? [y/n] ")
            if confirm.lower() == 'y' or confirm == '':
                organize(folder_path, renamed_dict, self.reading_word_limit, self.folder_name_length, 
                         vectorizer, lda_model, model, stop_words)
                print(f"Folder '{folder_path}' organized successfully.")
                print(self.separator)
            else:
                print(f"Folder organization aborted. The files in '{folder_path}' were left untouched.")
                print(self.separator)
        except KeyboardInterrupt:
            print(f"\nAbort. The files in '{folder_path}' were left untouched.")