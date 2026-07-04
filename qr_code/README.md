# QR Code

Standalone QR Code generation for CPython and MicroPython using only built-in
language features. It supports UTF-8 byte mode, error-correction level L, and
QR versions 1 through 10.

```python
from qr_code import print_qr

print_qr("https://github.com/BxNxM/micrOS")
```

Run the source file directly to see a QR Code in a terminal:

```bash
python3 qr_code/package/qr_code.py
```
