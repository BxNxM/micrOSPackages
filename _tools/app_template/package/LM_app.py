"""
micrOS Application exposed functions
"""

from package import shared


def load():
    return "Load app module"


def do():
    return f"Test app execution... with {shared()}"


def help():
    return "load", "do"
