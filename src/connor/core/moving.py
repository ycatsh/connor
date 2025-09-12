import os
import shutil
from typing import Dict, Union, List

from connor.core.setup.defaults import MISCELLANEOUS_FOLDER_NAME


def move_file(file_name, source_path, destination_path):
    """
    Move a file from source to destination
    """
    source_file = os.path.join(source_path, file_name)
    destination_file = os.path.join(destination_path, file_name)

    if os.path.exists(source_file):
        shutil.move(source_file, destination_file)


def organize(path: str, renamed_dict: Dict[str, Union[List[str], Dict]]) -> None:
    """
    Organize files into folders based on a renamed folder dictionary.
    Handles nested folders and miscellaneous files.

    Args:
        path: Path to the root folder.
        renamed_dict: Dictionary mapping folder names to lists of files or subfolders.
    """
    for folder, folder_content in renamed_dict.items():
        folder_path = os.path.join(path, folder)

        if not os.path.exists(folder_path):
            os.mkdir(folder_path)
        
        if isinstance(folder_content, dict):
            organize(folder_path, folder_content)

        # For misc folder
        if isinstance(folder_content, dict) and folder == MISCELLANEOUS_FOLDER_NAME:
            for sub_folder, file_names in folder_content.items():
                for file_name in file_names:
                    move_file(path, file_name, os.path.join(folder_path, sub_folder))

        if isinstance(folder_content, list):
            for file_name in folder_content:
                move_file(file_name, path, folder_path)
