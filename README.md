# ![logo](https://raw.githubusercontent.com/BxNxM/micrOS/master/media/logo_mini.png)micrOS Packages 📦 v0.1

This repository contains multiple **micrOS installable packages and applications**, each in its own folder.  
Every package includes a `package.json` for `mip` so micrOS devices can install them from GitHub (NOT YET: or a local server.)

```
micrOSPackages/
├── package_one/
│   └── package.json
├── package_two/
│   └── package.json
├── serve_packages.py
└── validate.py
```

---

## 📦 Package Structure

```
├── micros-app-template
│   ├── README.md
│   ├── app
│   │   ├── LM_app.py
│   │   ├── __init__.py
│   │   └── shared.py
│   └── package.json
```

**Important:**  
micrOS only auto-loads modules if they follow this naming convention:

```
LM_*.py
```

---

## 🚀 Installing on micrOS Device

### From GitHub:


#### REPL

```python
import mip
mip.install("github:BxNxM/micrOSPackages/micros-app-template")
```

#### Shell

```bash
pacman download "https://github.com/BxNxM/micrOSPackages/blob/main/micros-app-template"
```

---

## 🔧 Validate Packages Locally

Use the validation script to verify package structure and source file paths:

```bash
python3 validate.py
```

This ensures all files listed in every `package.json` exist and are installable.

---

## 🌐 Local mip Server (not works yet)

Use the local test server to install packages onto a device without GitHub:

```bash
python3 serve_packages.py
```

The script prints ready-to-use mip commands such as:

```python
import mip
mip.install("http://<your-ip>:8000/template_app")
```

---

## ✔️ Summary

- Each folder = one micrOS package  
- `validate.py` checks correctness of package structure
- `serve_packages.py` provides a local test server  
- Load modules must be named `LM_*.py` for micrOS to auto-load them  

This [micros-app-template](https://github.com/BxNxM/micrOSPackages/tree/main/micros-app-template) example serves as a clean, minimal template for building reusable micrOS applications.


git push -u origin main

