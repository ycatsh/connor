<h1 align="center">
<img src="./.github/logo.png" alt="Connor">
</h1>

Connor is a file organizer written in [Python](https://www.python.org/). It makes use of the [sentence-transformers](https://sbert.net/) framework for the main organization process and the [PyQt6](https://doc.qt.io/qtforpython-6/) GUI toolkit for the graphical user interface. **It is by no means supposed to substitute for organzing files by hand. It is just a concept**. Connor features a fast and fully local file organizer that uses natural language processing to organize computer files based on their textual content.
<br>

<div align="center">

![releases](https://img.shields.io/github/v/release/ycatsh/connor?color=507591&labelColor=1d1e1f&style=flat)
![issues-open](https://img.shields.io/github/issues/ycatsh/connor?color=507591&labelColor=1d1e1f&style=flat)
![stars](https://img.shields.io/github/stars/ycatsh/connor?color=507591&labelColor=1d1e1f&style=flat)

</div>

https://github.com/user-attachments/assets/b0d151c6-9a8b-4710-92e9-d410edc57b84

## Features
Connor runs locally using the `sentence-transformers/paraphrase-MiniLM-L6-v2` model to analyze file content and organize them based on semantic similarity. It uses cosine similarity to group similar files and applies Latent Dirichlet Allocation (LDA) to name folders.  

Unprocessable files (e.g., images, binaries) are sorted into a `_misc` folder based on their extensions.

<br>

### File Organization Summary
1. Organize files in a selected folder (or uploaded via GUI).
2. Organize text-based files (`.docx`, `.txt`, `.pdf`, etc.) using NLP.
3. Creates a separate folder named "Miscellaneous" for dissimilar or unprocessable files based on extension.
4. Provide a summary (tree structure) of the organization process upon completion.

### Customization Options
1. Similarity Threshold: Allows you to choose a similarity percentage threshold for grouping similar files.
2. Reading Word Limit: You can set a limit on the number of words to read from the file content.
3. Folder Name Word Limit: You can specify the maximum number of words allowed in the created folder names.
4. Default Parameters: You can modify these three parameters and save them for future sessions.

### User Preferences
**Command Line Interface**: Quick folder organization.
**Graphical Interface**: Simple GUI with file upload support.


<br>
<br>


## Installation
There are installation instructions for both GUI and CLI. You can choose the one you want to install. If you're opting for building the application from [source](https://github.com/ycatsh/connor#source) then adding the run file to path is recommended.

**Install Connor via pip:**
1. Make sure you have `python` and `pip` installed and added to path.
2. Run `pip install connor-nlp`  

<br>

**Install the GUI version of Connor (executable)**
1. Go to the [latest release](https://github.com/ycatsh/connor/releases).
3. Follow the steps there.
2. Run the executable (`.exe`).  


<br>
<br>


## Usage

### Command Structure

```bash
connor [command] [options]
```

### Commands
#### `run`: Run the folder organization process.

**Usage:**
```bash
connor run <folder_path>
```

**Options:**
- `folder_path`: Required. Absolute path to the folder that you want to organize.

**Example:**
```bash
connor run /path/to/your/folder
```

<br>

#### `settings`: Update the default settings for the tool.

**Usage:**
```bash
connor settings [options]
```

**Options:**
- `-f, --folder-word-limit`: Set the maximum length for folder names. (default: 3)
- `-r, --reading-limit`: Specify the word limit for reading files. (default: 200)
- `-t, --similarity-threshold`: Define the similarity threshold percentage. (default: 50)
- `--show`: Show current settings

**Example:**
```bash
connor settings -f 2 -r 150 -t 60
```

```console
$ connor settings --show
To see how to update: Connor settings [-h]

Current settings:
  folder words limit     3
  reading limit          200
  similarity threshold   50%
```

<br>

#### `--gui`: Run Connor as a full fledged GUI from the terminal.

**Usage:**
```bash
connor --gui
```

<br>

### Help
To view help information for commands and options use the ``-h`` or `--help` flag.  

**Example:**
```console
$ connor -h
usage: Connor [-h] [--gui] {settings,run} ...

Connor: Fast and local NLP file organizer

positional arguments:
  {settings,run}
    settings      Update the settings for the organizer
    run           Run the folder organization process

options:
  -h, --help      show this help message and exit
  --gui           Run the application in GUI mode.
```

<br>
<br>


## Source
#### 1. Clone repository:
```bash
git clone https://github.com/ycatsh/connor.git
cd connor
```  
#### 2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```  
#### 3. Install dependencies:
```bash
pip3 install -r requirements.txt
```
#### 4. Run program:
For GUI:
```bash
python3 run.py --gui
```
For CLI:
```bash
python3 run.py -h
```

#### 5. Install locally (optional):
```bash
pip3 install .
```  
  
**Example:**  
```bash
connor --gui
```
```bash
connor -h
```


<br>
<br>


## License
This project is distributed under MIT License, which can be found in LICENSE in the root dir of the project. I reserve the right to place future versions of this project under a different license.