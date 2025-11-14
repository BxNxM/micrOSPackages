# micrOS Application Package Template

```bash
├── micros-app-template
│   ├── README.md
│   ├── app
│   │   ├── LM_app.py
│   │   ├── __init__.py
│   │   └── shared.py
│   └── package.json
```


This folder provides a minimal, clean template for building **micrOS application packages**.  
It is designed to be **copied, renamed, and customized** to create your own micrOS-compatible applications while following the required project structure.

---

## 📦 What This Template Includes

- A working example library package (`template_app/`)
- A basic micrOS Load Module (`LM_app.py`)
- A `package.json` file showing how to map source files to device paths
- A shared utility module demonstrating internal reuse (`shared.py`)
- A project layout that follows micrOS best practices

This template is intentionally lightweight and easy to adapt.

---

## How to use package download

```
pacman download "https://github.com/BxNxM/micrOSPackages/blob/main/micros-app-template"
```

Output:

```
[mip] Installing: https://raw.githubusercontent.com/BxNxM/micrOSPackages/main/micros-app-template {'target': '/lib'}
  ✓ Installed successfully under /lib
  ✓ Unpack LM_app.py
```

### Test app

```
TinyDevBoard $ app help
 load,
 do,

TinyDevBoard $ app load
Load template_app module

TinyDevBoard $ app do
Test execution... with Template Shared function access
```

---
---

## 🚀 How to Create Your Own Application

1. **Copy this template folder**  
   Duplicate the entire `micros-app-template` directory.

2. **Rename the application folder**  
   Example:  
   ```
   app → my_cool_app
   ```

3. **Update `package.json`**  
   - Replace all `app/...` paths with `my_cool_app/...`
   - Create micrOS public handlers:
     ```
     LM_my_cool_app.py
     ```
   - Ensure your version number is correct.

4. **Customize your code**  
   - Add your logic to `my_cool_app/shared.py`
   - Modify `my_cool_app/LM_app.py` to implement your app’s behavior

5. **Native way - Install your app on a micrOS device** 

   ```python
   import mip
   mip.install("github:BxNxM/micrOSPackages/my_cool_app")
   ```

---

## 📁 Required Project Structure

Your renamed app must keep this structure:

```
my_cool_app/
├── package.json
└── my_cool_app/
    ├── __init__.py
    ├── shared.py
    └── LM_app.py
```

After installation with `mip`, micrOS will place your files here:

```
/lib/my_cool_app/*.py
/modules/LM_my_cool_app.py
```

---

## ⚙️ Why `LM_*.py` Matters

micrOS automatically discovers load modules located in `/modules` if their filenames begin with:

```
LM_
```

This naming convention is required so micrOS can load your application and expose its functions (e.g., `load()`, `do()`, `help()`).

---

## ✔️ Summary

- Copy the template  
- Rename the folder and paths  
- Update `package.json`  
- Implement your logic  
- Install via `mip.install()`  

This template is the recommended starting point for creating new micrOS applications.
