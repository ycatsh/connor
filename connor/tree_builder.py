from pathlib import Path


branch = "│   " 
connector = "├── "
end = "└── "
space =  "    "

# Generates the organization summary (tree structure) recursively
def tree(directory, indent='', is_path=False):
    if is_path:
        directory = Path(directory)
        items = list(directory.iterdir())
        pointers = [connector] * (len(items) - 1) + [end]

        for pointer, path in zip(pointers, items):
            yield indent + pointer + path.name

            if path.is_dir():
                new_indent = branch if pointer == connector else space
                yield from tree(path, indent+new_indent, is_path=True)
    else:
        for folder_name, files in directory.items():
            yield indent + folder_name
            
            if files:
                pointers = ['├── '] * (len(files) - 1) + ['└── ']
                for pointer, file in zip(pointers, files):
                    yield indent + pointer + file

# Generates a string of the tree with relevant formatting
def make_tree(path, dict, is_path_only=False, cli=False):
    if cli:
        structure = f"Organized Folder:\n{path}\n"
        for struct in tree(dict, is_path=is_path_only):
            structure += f" {struct}\n"
    else:
        structure = f"<samp><pre> {path}\n"
        for struct in tree(dict, is_path=is_path_only):
            structure += f" {struct}\n"
        structure += "</pre></samp>"

    return structure