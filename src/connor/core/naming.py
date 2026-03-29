import os
from typing import List, Dict, Any
from collections import defaultdict

from connor.core.setup.defaults import MISCELLANEOUS_FOLDER_NAME


def name_category(
    vectorizer: Any,
    content_list: List[str],
    folder_word_limit: int = 5,
    delimiter: str = "_",
) -> str:
    """
    Generate a folder name using TF-IDF keyword extraction.

    Args:
        vectorizer: Unused (kept for compatibility).
        lda_model: Unused (kept for compatibility).
        content_list: List of file contents in a cluster.
        folder_word_limit: Maximum number of words in folder name.
        delimiter: Delimiter between words.

    Returns:
        Generated folder name.
    """
    if not content_list:
        return "Untitled"

    X = vectorizer.transform(content_list)

    scores = X.mean(axis=0).A1
    feature_names = vectorizer.get_feature_names_out()

    top_indices = scores.argsort()[-folder_word_limit:][::-1]
    top_words = [feature_names[i].capitalize() for i in top_indices]

    folder_name = delimiter.join(top_words)
    return folder_name if folder_name else "Untitled"


def misc_handler(
    misc_files: List[str],
    exts: Dict[str, str],
    misc_folder_name: str = MISCELLANEOUS_FOLDER_NAME,
) -> Dict[str, Dict[str, List[str]]]:
    """
    Categorize miscellaneous files by their file extension.

    Args:
        misc_files: List of miscellaneous file names.
        exts: Mapping of categories to file extensions.
        misc_folder_name: Name of the miscellaneous folder.

    Returns:
        Dictionary with categorized miscellaneous files.
    """
    misc_dir: Dict[str, Dict[str, List[str]]] = {misc_folder_name: {}}

    for misc_file in misc_files:
        file_ext = os.path.splitext(misc_file)[1][1:].lower()
        parent = next(
            (k for k, v in exts.items() if file_ext in v.split()),
            file_ext,
        )
        misc_dir[misc_folder_name].setdefault(parent, []).append(misc_file)

    return misc_dir


def rename_groups(
    vectorizer: Any,
    folder_dict: Dict[Any, List[str]],
    files_list: List[List[str]],
    folder_word_limit: int,
    misc_files: List[str],
    exts: Dict[str, str],
    misc_folder_name: str = MISCELLANEOUS_FOLDER_NAME,
) -> Dict[str, List[str]]:
    """
    Rename clusters using TF-IDF-based keyword extraction.

    Ensures:
    - Stable folder naming
    - No overwriting due to name collisions

    Args:
        vectorizer: TD-IDF.
        folder_dict: Mapping of clusters to file lists.
        files_list: List of (file_path, content).
        folder_word_limit: Max words in folder names.
        misc_files: List of miscellaneous files.
        exts: Mapping of categories to extensions.
        misc_folder_name: Name of miscellaneous folder.

    Returns:
        Dictionary of folder_name -> list of files.
    """
    renamed_dict: Dict[str, List[str]] = {}
    name_counts: Dict[str, int] = defaultdict(int)

    content_lookup = {file_path: content for file_path, content in files_list}

    for _, similar_files in folder_dict.items():
        content = [
            content_lookup[f]
            for f in similar_files
            if f in content_lookup
        ]

        base_name = name_category(
            vectorizer,
            content,
            folder_word_limit,
        )

        name_counts[base_name] += 1
        if name_counts[base_name] > 1:
            folder_name = f"{base_name}_{name_counts[base_name]}"
        else:
            folder_name = base_name

        renamed_dict[folder_name] = similar_files

    misc_dict = misc_handler(misc_files, exts, misc_folder_name)

    return {**renamed_dict, **misc_dict}