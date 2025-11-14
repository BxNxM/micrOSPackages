# micrOSPackages (alpha)

This repository contains multiple **micrOS installable packages**, each in its own folder.  
Every package includes a `package.json` for `mip` so micrOS devices can install them from GitHub or a local server.

```
micrOSPackages/
├── package_one/
│   └── package.json
├── package_two/
│   └── package.json
├── serve_packages.py
└── validate_packages.py
```

---

## 📦 Package Structure

Each package directory must include:

- `package.json` – defines source → device file mappings  
- Python files inside the package folder  
- Optional **Load Module** installed under `/modules/LM_*.py` on the device

**Important:**  
micrOS only auto-loads modules if they follow this naming convention:

```
/modules/LM_*.py
```

---

## 🔧 Validate Packages Locally

Use the validation script to verify package structure and source file paths:

```bash
python3 validate_packages.py
```

This ensures all files listed in every `package.json` exist and are installable.

---

## 🌐 Local mip Server

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

## 🚀 Installing on micrOS Device

From GitHub:

```python
import mip
mip.install("github:BxNxM/micrOSPackages/template_app")
```

This places:

- library files under `/lib/<package_name>/`
- load modules under `/modules/LM_<name>.py`

---

## ✔️ Summary

- Each folder = one micrOS package  
- `validate_packages.py` checks correctness  
- `serve_packages.py` provides a local test server  
- Load modules must be named `LM_*.py` for micrOS to auto-load them  

This repository serves as a clean, minimal template for building reusable micrOS applications.


git push -u origin main
