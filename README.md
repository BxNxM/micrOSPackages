# ![logo](https://raw.githubusercontent.com/BxNxM/micrOS/master/media/logo_mini.png)micrOS Packages 📦 v0.1


# micrOS Packages Registry and Tools

This repository contains multiple installable micrOS packages and applications.  
Each package lives in its own folder and includes a package.json that is compatible with mip.  
micrOS devices can install these packages from GitHub or from a local mip server.

---

# CLI Tool (tools.py)

The tools.py script provides a unified interface to validate packages, create new packages, update package.json files, and start a local mip package registry server.

## Usage


## Options

### General
- `-h`, `--help`
  Show help message and exit.

### Validation
- `-v [VALIDATE]`, `--validate [VALIDATE]`  
  Validate one package by name.  
  If no name is provided, validate all packages.

### Local mip Server
- `-s`, `--serve`  
  Start the local mip package registry server.

### Package Creation
- `-c`, `--create`  
  Create a new micrOS application package from the template.
	- `--package PACKAGE`  
  Name of the package/application when creating a new one.
	- `--module MODULE`  
  Public Load Module name (LM_*.py) when creating a new application.

### Update package.json
- `-u UPDATE`, `--update UPDATE`  
  Update the package.json file of a package by its `PACKAGE` name.  
  Primarily updates the "urls" section.

---

# Repository Structure

```bash
├── README.md
├── _tools
│   ├── __init__.py
│   ├── app_template
│   │   ├── README.md
│   │   ├── package
│   │   │   ├── LM_app.py
│   │   │   ├── __init__.py
│   │   │   └── shared.py
│   │   └── package.json
│   ├── create_package.py
│   ├── serve_packages.py
│   └── validate.py
└── tools.py
```

### Load Module Naming Convention

micrOS automatically loads modules only if their filenames match:

```
LM_*.py
```

---

# Validating Packages

Validate all packages:

```bash
python3 tools.py --validate
```

Validate one specific package:

```bash
python3 tools.py --validate mypackage
```

The validation process ensures:
- package.json exists
- all files listed inside package.json actually exist
- the package structure is valid for mip installation

---

# Updating package.json

Update the urls section of a package’s package.json:

```bash
python3 tools.py --update mypackage
```


This reads, modifies, and rewrites the package.json file cleanly.

---

# Creating a New micrOS Package

```bash
python3 tools.py --create --package myapplication --module myapp
```


This command:
- creates a new folder
- copies the template structure
- fills in package.json with provided values

---

# Local mip Test Server

Start the local mip package registry server:

```bash
python3 tools.py --serve
```

---

# Installing Packages on a micrOS Device

## From GitHub (REPL)

```python
import mip
mip.install("github:BxNxM/micrOSPackages/blinky_example")
```

## From Shell

```bash
pacman download "https://github.com/BxNxM/micrOSPackages/blob/main/blinky_example"
```

---

# Summary

- Each folder is one micrOS package.
- tools.py manages:
  - validation
  - package creation
  - package.json updating
  - local mip server
- validate.py checks package structure and file references.
- serve\_packages.py will provide a local mip server.
- Load Modules must follow the LM_*.py naming pattern.

git push -u origin main

