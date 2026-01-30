#!/bin/bash
# CQViewer CLI wrapper script for air-gapped environments
# No installation required - runs directly from source

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHONPATH="$SCRIPT_DIR/src" python -m cqviewer.cli "$@"
