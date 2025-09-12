import os
import numpy as np
from typing import List, Dict, Any

from connor.core import *
from connor.core.setup.defaults import MISCELLANEOUS_FOLDER_NAME


def name_category(
    vectorizer: Any, 
    lda_model: Any, 
    content_list: List[str], 
    folder_word_limit: int = 5, 
    delimiter: str = "_"
) -> str:
    """
    Generate a folder name based on the dominant LDA topic.
    Fallback to frequent words if no topic words are found.

    Args:
        vectorizer: Fitted vectorizer.
        lda_model: Trained LDA model.
        content_list: List of file contents from a single group.
        folder_word_limit: Max number of words in the folder name.
        delimiter: Delimiter between words.

    Returns:
        Generated folder name.
    """
    if not content_list:
        return "Untitled"
    
    text_vectorized = vectorizer.transform(content_list)
    topic_distribution = lda_model.transform(text_vectorized)
    dominant_topic_index = np.argmax(topic_distribution.mean(axis=0))

    feature_names = vectorizer.get_feature_names_out()
    topic_words = lda_model.components_[dominant_topic_index]
    top_word_indices = topic_words.argsort()[-folder_word_limit:][::-1]
    top_words = [feature_names[i].capitalize() for i in top_word_indices]

    folder_name = delimiter.join(top_words)
    return folder_name if folder_name else folder_name_fallback(vectorizer, content_list, folder_word_limit, delimiter)


def folder_name_fallback(
    vectorizer: Any, 
    content_list: List[str], 
    folder_word_limit: int = 5, 
    delimiter: str = "_"
) -> str:
    """
    Generate a fallback folder name using the most frequent words.

    Args:
        vectorizer: Fitted vectorizer.
        content_list: List of file contents from a group.
        folder_word_limit: Max number of words in the folder name. Defaults to 5.
        delimiter: Delimiter between words. Defaults to '_'.

    Returns:
        Fallback folder name.
    """
    text_vectorized = vectorizer.transform(content_list)
    feature_names = vectorizer.get_feature_names_out()
    scores = text_vectorized.sum(axis=0).A1
    top_word_indices = scores.argsort()[-folder_word_limit:][::-1]
    top_words = [feature_names[i].capitalize() for i in top_word_indices]
    return delimiter.join(top_words)


def misc_handler(
    misc_files: List[str], 
    exts: Dict[str, str], 
    misc_folder_name: str = MISCELLANEOUS_FOLDER_NAME
) -> Dict[str, Dict[str, List[str]]]:
    """
    Categorize miscellaneous files by their file extension.

    Args:
        misc_files: List of miscellaneous file names.
        exts: Mapping of categories to file extensions.
        misc_folder_name: Name of the miscellaneous folder. Defaults to `MISCELLANEOUS_FOLDER_NAME`

    Returns:
        Dictionary with categorized miscellaneous files.
    """
    misc_dir = {misc_folder_name: {}}
    for misc_file in misc_files:
        file_ext = os.path.splitext(misc_file)[1][1:].lower()
        parent = next((k for k, v in exts.items() if file_ext in v.split()), file_ext)
        misc_dir[misc_folder_name].setdefault(parent, []).append(misc_file)
    return misc_dir


def rename_groups(
    vectorizer: Any, 
    lda_model: Any, 
    folder_dict: Dict[Any, List[str]], 
    files_list: List[List[str]], 
    folder_word_limit: int, 
    misc_files: List[str], 
    exts: Dict[str, str], 
    misc_folder_name: str = MISCELLANEOUS_FOLDER_NAME
) -> Dict[str, List[str]]:
    """
    Rename folders based on content similarity and topic modeling.
    Includes categorized miscellaneous files.

    Args:
        vectorizer: Fitted vectorizer.
        lda_model: Trained LDA model.
        folder_dict: Mapping of group keys to lists (value) of file names.
        files_list: List of pairs (filename, content).
        folder_word_limit: Max number of words in folder names.
        misc_files: List of miscellaneous files.
        exts: Mapping from categories to space-separated file extensions.
        misc_folder_name: Name of the miscellaneous folder. Defaults to `MISCELLANEOUS_FOLDER_NAME`

    Returns:
        Dictionary of renamed folders with their associated files.
    """
    renamed_dict = {}

    for _, similar_files in folder_dict.items():
        content = [files[1] for files in files_list if files[0] in similar_files]
        folder_name = name_category(vectorizer, lda_model, content, folder_word_limit)
        renamed_dict[folder_name] = similar_files

    misc_dict = misc_handler(misc_files, exts, misc_folder_name)
    return {**renamed_dict, **misc_dict}
