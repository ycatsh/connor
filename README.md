<h1 align="center">
<img src="https://github.com/user-attachments/assets/2987085a-2e8c-4185-9b02-672ba687ca4b" alt="Connor">
</h1>

Connor is a file organizer written in [python](https://www.python.org/). It makes use of the [sentence-transformers](https://sbert.net/) framework for the main organization process and the [PyQt6](https://doc.qt.io/qtforpython-6/) GUI toolkit for the graphical user interface. It features a fast and fully local file organizer that uses natural language processing to organize computer files based on their textual content.
<br>

<div align="center">

![releases](https://img.shields.io/github/v/release/ycatsh/connor?color=507591&labelColor=1d1e1f&style=flat)
![issues-open](https://img.shields.io/github/issues/ycatsh/connor?color=507591&labelColor=1d1e1f&style=flat)
![commits](https://img.shields.io/github/downloads/ycatsh/connor/latest?color=507591&labelColor=1d1e1f&style=flat)
![downloads](https://img.shields.io/github/stars/ycatsh/connor?color=507591&labelColor=1d1e1f&style=flat)

</div>

## Features
Connor works locally on your computer using a pre-trained NLP model `sentence-transformers/paraphrase-MiniLM-L6-v2` to understand the meaning of the data and calculate the cosine similarity between files. The folders are appropriately named using topic modeling through the Latent Dirichlet Allocation (LDA) technique.

<br>

### File Organization
1. Organize files within a selected folder or manually uploaded files (uploading files is only supported for GUI).
2. Organize text-based files (`.docx`, `.txt`, `.pdf`, etc.) using NLP.
3. Create a separate folder named ‘Miscellaneous’ for dissimilar or unprocessable files based on extension.
4. Provide a summary (tree structure) of the organization process upon completion.

### Customization Options
1. Similarity Threshold: Allows yous to choose a similarity percentage threshold for grouping similar files.
2. Reading Word Limit: You can to set a limit on the number of words read from file content.
3. Folder Name Word Limit: You can specify a maximum number of words allowed in the created folder names.
4. Default Parameters: You can modify these three parameters and save them for future sessions.

### User Preferences
Command Line Interface: Simple and concise command line interface to quickly organize folders.
Graphical User Interface: Provides a simplistic and straightforward GUI for ease of use with upload files feature.


<br>
<br>


## Installation
There are installation instructions for both GUI and CLI. You can choose the one you want to install. If you're opting for building the CLI from source then adding the file to path is recommended.

### Windows
#### CLI (pip)
1. Make sure you have `python` and `pip` installed and added to path.
2. Run `pip install connor-nlp`  

#### EXE (GUI)
1. Go to the [latest release](https://github.com/ycatsh/connor/releases).
3. Follow the steps there.
2. Run the executable.  

<br>

### Linux
#### CLI (pip)
1. Make sure you have `python3` and `pip3` installed.
2. Run `pip3 install connor-nlp`    


<br>
<br>


## Usage

### Command Structure

```bash
connor [command] [options]
```

### Commands
#### `run`
Run the folder organization process.

**Usage:**
```bash
connor run --path <folder_path>
```

**Options:**
- `--path`: Required. Absolute path to the folder that you want to organize.

**Example:**
```bash
connor run --path /path/to/your/folder
```

#### `settings`
Update the default settings for the tool.

**Usage:**
```bash
python main.py settings [options]
```

**Options:**
- `--folder-name-length`: Set the maximum length for folder names. (default: 2)
- `--reading-word-limit`: Specify the word limit for reading files. (default: 100)
- `--similarity-threshold`: Define the similarity threshold percentage. (default: 50)

**Example:**
```bash
python main.py settings --folder-name-length 3 --reading-word-limit 150 --similarity-threshold 60
```

### Help
To view help information for commands and options use the ``-h`` or `--help` flag:  

**Example:**
```bash
connor -h
```

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
python run.py --gui
```
For CLI:
```bash
python run.py -h
```

## License
This project is distributed under MIT License, which can be found in LICENSE in the root dir of the project. I reserve the right to place future versions of this project under a different license.