@echo off
REM CQViewer GUI wrapper script
REM Requires: tkinter (usually built into Python) and ttkbootstrap (pip install ttkbootstrap)

set SCRIPT_DIR=%~dp0
set PYTHONPATH=%SCRIPT_DIR%src
python -m cqviewer.ui.app %*
