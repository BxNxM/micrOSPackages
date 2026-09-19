"""Rebuild the device terminal asset: python3 build_terminal.py (requires rjsmin)."""
from pathlib import Path
from rjsmin import jsmin

ROOT = Path(__file__).resolve().parent
source = (ROOT / 'vendor' / 'term.js').read_text()
# Preserve the upstream copyright, permission and attribution header verbatim.
header_end = source.index('*/') + 2
(ROOT / 'package' / 'uwebrepl' / 'term.js').write_text(
    source[:header_end] + '\n' + jsmin(source[header_end:]) + '\n'
)
