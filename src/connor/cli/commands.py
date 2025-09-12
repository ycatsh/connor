import configparser
import shutil
from pathlib import Path
from typing import Optional

from connor.core import *
from connor.core.organize import (
    start_run, confirm_run
)


class ConnorCLI:
    def __init__(self):
        """Initialize with settings from config file."""
        self.config_path = get_config_file()

        self.settings = configparser.ConfigParser()
        self.settings.read(self.config_path)

        self.folder_word_limit = int(self.settings["Parameters"].get("folder_word_limit", 3))
        self.reading_word_limit = int(self.settings["Parameters"].get("reading_word_limit", 200))
        self.similarity_threshold = int(self.settings["Parameters"].get("similarity_threshold", 50))
        self.exts = self.settings["Extension_Map"]

        terminal_width = shutil.get_terminal_size().columns
        self.separator = '-' * terminal_width

        self.model, self.stop_words, self.lda_model, self.vectorizer = initialize_models()

    def update_settings(
        self,
        folder_word_limit: Optional[int] = None,
        reading_word_limit: Optional[int] = None,
        similarity_threshold: Optional[int] = None
    ) -> None:
        """
        Update configuration settings and save to the config file.

        Args:
            folder_word_limit: Maximum words per folder name.
            reading_word_limit: Maximum words to read per file.
            similarity_threshold: Similarity threshold for grouping files.
        """
        if folder_word_limit is not None:
            self.folder_word_limit = folder_word_limit
            self.settings["Parameters"]["folder_word_limit"] = str(folder_word_limit)
        if reading_word_limit is not None:
            self.reading_word_limit = reading_word_limit
            self.settings["Parameters"]["reading_word_limit"] = str(reading_word_limit)
        if similarity_threshold is not None:
            self.similarity_threshold = similarity_threshold
            self.settings["Parameters"]["similarity_threshold"] = str(similarity_threshold)

        # Save updated settings to config file
        with open(self.config_path, "w") as configfile:
            self.settings.write(configfile)
        print("Settings updated successfully.")

    def show_settings(self):
        """
        Display the current configuration settings.
        """
        print("To see how to update: Connor settings [-h]")
        print("\nCurrent settings:")
        print(f"  {'folder words limit':<22} {self.folder_word_limit}")
        print(f"  {'reading limit':<22} {self.reading_word_limit}")
        print(f"  {'similarity threshold':<22} {self.similarity_threshold}%")

    def organize_folder(self, folder_to_organize: str) -> None:
        """
        Frontend level. Just calls the various functions.
        """
        folder_to_organize = Path(folder_to_organize)

        if not folder_to_organize.exists():
            print(f"Error: The folder '{folder_to_organize}' does not exist.")
            return
        
        print(self.separator)
        print(f'To customize default settings instead run the command <connor settings -h>\nfolder_word_limit: {self.folder_word_limit}\nreading_word_limit: {self.reading_word_limit}\nsimilarity_threshold: {self.similarity_threshold}%')
        print(self.separator)
        print(f"Folder '{folder_to_organize}' is being organized...")
        
        # Show organization
        renamed_dict, tree = start_run(
            folder_to_organize=folder_to_organize, 
            reading_word_limit=self.reading_word_limit,
            similarity_threshold=self.similarity_threshold,
            folder_word_limit=self.folder_word_limit,
            exts=self.exts,
            model=self.model,
            vectorizer=self.vectorizer,
            lda_model=self.lda_model,
            stop_words=self.stop_words
        )
        print(tree)
        print(self.separator)

        # Confirm Organization
        try:
            confirm = input(f"The above directory tree explains how the folder will be organized.\nDo you want to continue? [y/n] ")

            if confirm.lower() == 'y' or confirm == '':
                confirm_run(
                    folder_to_organize=folder_to_organize,
                    renamed_dict=renamed_dict
                )
                print(f"Folder '{folder_to_organize}' organized successfully.")
                print(self.separator)

            else:
                print(f"Folder organization aborted. The files in '{folder_to_organize}' were left untouched.")
                print(self.separator)

        except KeyboardInterrupt:
            print(f"\nAbort. The files in '{folder_to_organize}' were left untouched.")