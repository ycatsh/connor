from pathlib import Path


branch = "│   " 
connector = "├── "
end = "└── "
space =  "    "

# Generates the organization summary (tree structure) recursively
def tree(directory, indent=''):  
    directory = Path(directory)
    items = list(directory.iterdir())
    pointers = [connector] * (len(items) - 1) + [end]

    for pointer, path in zip(pointers, items):
        yield indent + pointer + path.name

        if path.is_dir():
            new_indent = branch if pointer == connector else space
            yield from tree(path, indent+new_indent)

# Generates a string of the tree with relevant formatting
def make_tree(directory, cli=False):
    if cli:
        structure = f"Organized Folder:\n{directory}\n"
        for struct in tree(directory):
            structure += f" {struct}\n"
    else:
        structure = f"<samp><pre> {directory}\n"
        for struct in tree(directory):
            structure += f" {struct}\n"
        structure += "</pre></samp>"

    return structure