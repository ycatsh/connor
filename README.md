<h1 align="center">
<img src="./.github/logo.png" alt="Connor">
</h1>

Connor is a fast and fully local file classifier and organizer. It is written in [Python](https://www.python.org/) and makes use of the [sentence-transformers](https://sbert.net/) framework for the main organization process. **It is by no means supposed to substitute for organzing files by hand, rather it can be viewed as a tool to accelerate it.**

<br>

<div align="center">

![issues-open](https://img.shields.io/github/issues/ycatsh/connor?color=507591&labelColor=1d1e1f&style=flat)
![stars](https://img.shields.io/github/stars/ycatsh/connor?color=507591&labelColor=1d1e1f&style=flat)

</div>

https://github.com/user-attachments/assets/b0d151c6-9a8b-4710-92e9-d410edc57b84

## Features
Connor runs locally using the `BAAI/bge-base-en-v1.5` model to analyze file content and organize them based on semantic similarity.  

It generates embeddings for each file and clusters them using KMeans. Folder names are created using TF-IDF keyword extraction, producing stable and interpretable labels for each group.  

Unprocessable files (e.g., images, binaries) are sorted into a `_misc` folder based on their extensions.

### Customization Options
2. **Reading Word Limit:** Limit how much of a file is read.
3. **Folder Name Word Limit:** Set max words for folder names.


<br>
<br>


## Installation

#### 1. Clone repository:

```bash
git clone https://github.com/ycatsh/connor.git
cd connor
```  

#### 2. Create and activate virtual environment:

Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```  

Windows:
```bash
python -m venv .venv
.venv/bin/activate.bat
```

#### 3. Install dependencies:
```bash
pip install -r requirements.txt
```

#### 4. Run program:
```bash
python src/connor/main.py -h
```

#### 5. Install locally (optional):
```bash
pip install .
```

**Example:**  
```bash
connor -h
```

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

#### `settings`: Update the default settings for the tool.

<br>
<br>

**Usage:**
```bash
connor settings [options]
```

**Options:**
- `-f, --folder-word-limit`: Set the maximum length for folder names. (default: 3)
- `-r, --reading-limit`: Specify the word limit for reading files. (default: 200)

**Example:**
```console
$ connor settings -f 2 -r 150
Settings updated successfully.
```

```console
$ connor settings
To see how to update: Connor settings [-h]

Current settings:
  folder words limit     2
  reading limit          150
```

<br>

### Help
To view help information for commands and options use the ``-h`` or `--help` flag.  

**Example:**
```console
$ connor -h
usage: connor [-h] {settings,run} ...

Connor: Fast and local NLP file organizer

positional arguments:
  {settings,run}
    settings      View or update settings.
    run           Organize a folder.

options:
  -h, --help      show this help message and exit
```


<br>
<br>


## License
This project is distributed under MIT License, which can be found in LICENSE in the root dir of the project. I reserve the right to place future versions of this project under a different license.