#!/bin/bash
# CQViewer GUI wrapper script
# Requires: tkinter (usually built into Python) and ttkbootstrap (pip install ttkbootstrap)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHONPATH="$SCRIPT_DIR/src" python -m cqviewer.ui.app "$@"
