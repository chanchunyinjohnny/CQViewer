#!/usr/bin/env bash
# pack.sh — Create a clean zip of CQViewer for deployment.
# Usage: ./pack.sh [output_name]
#   output_name: optional zip filename (default: CQViewer_YYYYMMDD_HHMMSS.zip)
#
# Includes only source code and essential project files.
# Excludes tests, .claude, .git, .github, .idea, proprietary, caches, etc.
# Output goes to dist/ directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="${1:-CQViewer_${TIMESTAMP}.zip}"
OUTPUT="dist/$FILENAME"

mkdir -p dist
rm -f "$OUTPUT"

zip -r "$OUTPUT" \
    src/ \
    run_cli.py \
    run_ui.py \
    README.md \
    requirements.txt \
    pyproject.toml \
    -x '**/__pycache__/*' \
    -x '**/.DS_Store' \
    -x '**/*.egg-info/*'

echo ""
echo "Created: $OUTPUT"
echo "Size:    $(du -h "$OUTPUT" | cut -f1)"
echo ""
echo "Contents:"
zipinfo -1 "$OUTPUT" | head -30
TOTAL=$(zipinfo -1 "$OUTPUT" | wc -l | tr -d ' ')
if [ "$TOTAL" -gt 30 ]; then
    echo "... ($TOTAL files total)"
fi
