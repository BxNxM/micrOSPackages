"""
micrOS Application exposed functions
  Unpackaging moves this module under /modules/ in the micrOS filesystem.
"""

from package import shared


def load():
    return "Load app module"


def do():
    return f"Test app execution... with {shared()}"


def help():
    return "load", "do"
