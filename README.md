<h1 align="center">
<img src="https://github.com/user-attachments/assets/2987085a-2e8c-4185-9b02-672ba687ca4b" alt="Connor">
</h1>

Connor is a file organizer written in [python](https://www.python.org/). It makes use of the [sentence-transformers](https://sbert.net/) framework for the main organization process and the [PyQt6](https://doc.qt.io/qtforpython-6/) GUI toolkit for the graphical user interface. **It is by no means supposed to substitute for organzing files by hand. It is just a concept**. Connor features a fast and fully local file organizer that uses natural language processing to organize computer files based on their textual content.
<br>

<div align="center">

![releases](https://img.shields.io/github/v/release/ycatsh/connor?color=507591&labelColor=1d1e1f&style=flat)
![issues-open](https://img.shields.io/github/issues/ycatsh/connor?color=507591&labelColor=1d1e1f&style=flat)
![stars](https://img.shields.io/github/stars/ycatsh/connor?color=507591&labelColor=1d1e1f&style=flat)

</div>

## Features
Connor works locally on your computer using a pre-trained NLP model `sentence-transformers/paraphrase-MiniLM-L6-v2` to understand the meaning of the data and calculate the cosine similarity between files. The folders are appropriately named using topic modeling through the Latent Dirichlet Allocation (LDA) technique.

The file names and contents are read, then cosine similarity is used to calculate the similarity between the content of every file with respect to every other file. Based on the condition that the similarity scores between the files are above the provided threshold, the files are grouped in key-value pairs into a dictionary where each category corresponds to a folder. 

Latent Dirichlet Allocation is then used to generate topic names for the contents in each folder, i.e., the categories in the dictionary. Folders are created using the most relevant topic names, and the corresponding files are then moved into their appropriate folders.

For files such as images (image support will be added later), executables, binaries, etc. that cannot be read are organized into a ``_misc`` folder based on their file extensions.

<br>

### File Organization Summary
1. Organize files within a selected folder or manually uploaded files (uploading files is only supported for GUI).
2. Organize text-based files (`.docx`, `.txt`, `.pdf`, etc.) using NLP.
3. Creates a separate folder named "Miscellaneous" for dissimilar or unprocessable files based on extension.
4. Provide a summary (tree structure) of the organization process upon completion.

### Customization Options
1. Similarity Threshold: Allows you to choose a similarity percentage threshold for grouping similar files.
2. Reading Word Limit: You can set a limit on the number of words to read from the file content.
3. Folder Name Word Limit: You can specify the maximum number of words allowed in the created folder names.
4. Default Parameters: You can modify these three parameters and save them for future sessions.

### User Preferences
Command Line Interface: Simple and concise command line interface to quickly organize folders.
Graphical User Interface: Provides a simplistic and straightforward GUI for ease of use with upload files feature.


<br>
<br>


## Installation
There are installation instructions for both GUI and CLI. You can choose the one you want to install. If you're opting for building the application from [source](https://github.com/ycatsh/connor#source) then adding the run file to path is recommended.

**Install Connor via pip:**
1. Make sure you have `python` and `pip` installed and added to path.
2. Run `pip install connor-nlp`  

<br>

**Install the GUI version of Connor (only for windows)**
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
- `-f, --folder-word-limit`: Set the maximum length for folder names. (default: 2)
- `-r, --reading-limit`: Specify the word limit for reading files. (default: 100)
- `-t, --similarity-threshold`: Define the similarity threshold percentage. (default: 50)
- `--show`: Show current settings

**Example:**
```bash
connor settings -f 3 -r 150 -t 60
```

```console
$ connor settings --show
To see how to update: Connor settings [-h]

Current settings:
  folder words limit     2
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
python run.py --gui
```
For CLI:
```bash
python run.py -h
```


<br>
<br>


## License
This project is distributed under MIT License, which can be found in LICENSE in the root dir of the project. I reserve the right to place future versions of this project under a different license.