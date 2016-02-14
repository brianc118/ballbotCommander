import sys
from cx_Freeze import setup, Executable

setup(
    name = "ballbotCommander",
    version = "0.3",
    description = "debugging visualisation tool",
    executables = [Executable("ballbotCommander.py", base = "Win32GUI")])