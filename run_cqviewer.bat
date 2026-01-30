@echo off
REM CQViewer CLI wrapper script for air-gapped environments
REM No installation required - runs directly from source

set SCRIPT_DIR=%~dp0
set PYTHONPATH=%SCRIPT_DIR%src
python -m cqviewer.cli %*
