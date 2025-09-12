from typing import Dict, List, Generator

BRANCH = "│   " 
CONNECTOR = "├── "
END = "└── "
SPACE =  "    "

def make_tree(file_dict: Dict[str, List[str]], indent: str = '') -> Generator[str, None, None]:
    """
    Generates the organization summary (tree structure) recursively

    Args:
        file_dict: Dictionary of the organized folder
        indent: Current indentation level. Defaults to ''.
    
    Yields:
        A line of the tree structure of the folder.
    """
    for folder_name, files in file_dict.items():
        yield indent + folder_name
        
        if files:
            pointers = [CONNECTOR] * (len(files) - 1) + [END]
            for pointer, file in zip(pointers, files):
                yield indent + pointer + file


def make_tree_string(path_name: str, file_dict: Dict[str, List[str]]) -> str:
    """
    Generates a formatted string of the folder tree 
    """
    structure = f"Organized Folder:\n{path_name}\n"
    for line in make_tree(file_dict):
        structure += f" {line}\n"

    return structure