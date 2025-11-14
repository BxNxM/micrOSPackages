"""
micrOS Application exposed functions
    Path: /modules/LM_*.py
"""

from template_app import shared


def load():
    return "Load template_app module"


def do():
    return f"Test execution... with {shared()}"


def help():
    return "load", "do"

