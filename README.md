# ![logo](https://raw.githubusercontent.com/BxNxM/micrOS/master/media/logo_mini.png)micrOS Packages 📦 v0.1


# micrOS Packages — Toolkit & Repository
Version 0.1

This repository contains multiple installable micrOS packages and applications.  
Each package lives in its own folder and includes a package.json that is compatible with mip.  
micrOS devices can install these packages from GitHub or (later) from a local mip server.

---

# CLI Tool (tools.py)

The tools.py script provides a unified interface to validate packages, create new packages, update package.json files, and start a local mip server.

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
  Start the local mip server (work in progress / TODO).

### Package Creation
- `-c`, `--create`  
  Create a new micrOS application package from the template.

### Update package.json (New Feature)
- `-u UPDATE`, `--update UPDATE`  
  Update the package.json file of a package by its package name.  
  Primarily updates the "urls" section.

### Additional Metadata Flags
- `--package PACKAGE`  
  Name of the package/application when creating a new one.
- `--module MODULE`  
  Public Load Module name (LM_*.py) when creating a new application.

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
├── micros-app-template
│   ├── README.md
│   ├── app
│   │   ├── LM_app.py
│   │   ├── __init__.py
│   │   └── shared.py
│   └── package.json
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

# Updating package.json (New Feature)

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

# Local mip Test Server (Work In Progress)

Start the local mip server:

```bash
python3 tools.py --serve
```

> Under development

---

# Installing Packages on a micrOS Device

## From GitHub (REPL)

```python
import mip
mip.install("github:BxNxM/micrOSPackages/micros-app-template")
```

## From Shell

```bash
pacman download "https://github.com/BxNxM/micrOSPackages/blob/main/micros-app-template"
```

---

# Summary

- Each folder is one micrOS package.
- tools.py manages:
  - validation
  - package creation
  - package.json updating
  - local mip server (WIP)
- validate.py checks package structure and file references.
- servei\_packages.py will provide a local mip server.
- Load Modules must follow the LM_*.py naming pattern.
- micros-app-template is the recommended template for creating new micrOS application packages.


git push -u origin main

