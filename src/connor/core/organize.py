from typing import Tuple, Dict, Any, List

from connor.core.prepare import get_files_list
from connor.core.naming import rename_groups
from connor.core.tree_builder import make_tree_string
from connor.core.reader import prep_files
from connor.core.group import group_files_into_dict
from connor.core.moving import organize


def start_run(
    folder_to_organize: str,
    reading_word_limit: int,
    folder_word_limit: int,
    exts: List[str],
    model: Any,
    stop_words: set[str],
    vectorizer: Any,
) -> Tuple[Dict[str, List[str]], str]:
    """
    Start the folder organization workflow.
        1. Flatten folder.
        2. Read files and create groups as a dict.
        3. Fit vectorizer.
        4. Rename file groups.
        5. Return renamed dict and tree string.

    Args:
        folder_to_organize: Path to the folder to organize.
        reading_word_limit: Max words to read from each file.
        folder_word_limit: Max words to use for folder naming.
        exts: List of allowed file extensions.
        model: Clustering/model object for grouping.
        stop_words: Set of stop words to ignore.
        vectorizer: TD-IDF.

    Returns:
        Tuple containing:
            Renamed folder dictionary
            Formatted folder tree string
    """
    folder_dict = {}
    prep_files(folder_to_organize)

    # Make file groups
    files_list, misc_list = get_files_list(folder_to_organize, reading_word_limit, stop_words)
    folder_dict = group_files_into_dict(model, files_list)

    # Fit vectorizer
    all_texts = [content for _, content in files_list if content]
    vectorizer.fit(all_texts)

    # Name each file group
    renamed_dict = rename_groups(
        vectorizer,
        folder_dict, 
        files_list, 
        folder_word_limit, 
        misc_list,
        exts
    )

    return renamed_dict, make_tree_string(
        path_name=folder_to_organize, 
        file_dict=renamed_dict
    )


def confirm_run(folder_to_organize: str, renamed_dict: Dict[str, List[str]]) -> None:
    """
    Execute the folder organization by moving files.
    """
    organize(folder_to_organize, renamed_dict)
