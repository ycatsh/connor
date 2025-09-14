import string
from pathlib import Path
from typing import Set

from connor.core.reader import read_files


def preprocess(text: str, stop_words: Set[str]) -> str:
    """
    Pre-process text by removing punctuation, ignoring stop words and small numbers.

    Args:
        text: Input text string.
        stop_words: Set of stop words to ignore.

    Returns:
        Preprocessed text string.
    """
    text = text.translate(str.maketrans('', '', string.punctuation))
    preprocessed = []
    for word in text.split():
        if word.lower() not in stop_words:
            try:
                num_word = int(word)
                if num_word > 100: # Ignores small numbers in file names so important things like YYYY are still included
                    preprocessed.append(word)
            except ValueError:
                preprocessed.append(word)
    return ' '.join(preprocessed)


def get_files_list(folder_to_organize: Path, word_limit: int, stop_words):
    """
    Get list of files with processed content and list of miscellaneous files.

    Args:
        folder_to_organize: Path to folder.
        word_limit: Maximum number of words to extract.
        stop_words: Set of stop words to ignore.

    Returns:
        Tuple containing:
            List of tuples (filename, processed content)
            List of miscellaneous filenames
    """
    text_files_list, misc_files_list = read_files(folder_to_organize, word_limit)
    text_files_list = [(file, preprocess(content, stop_words)) for file, content in text_files_list if content]
    return text_files_list, misc_files_list