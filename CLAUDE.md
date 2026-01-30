# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project is a Python-based tool for inspecting and exporting data from CQ (chronicle queue).
It takes the cq4 data file and also cq4t metadata file to display the stored objects in a user-friendly manner.
It allows users to search for specific fields or values within these objects, filter results based on various criteria, and export the data to CSV format for further analysis.
This project has a simple User Interface (UI) that displays 50-100 lines of data by default, with pagination support for navigating through larger datasets.

Essential Features:

1. Search
   - Search by field name (e.g., find all objects with `customerId`)
   - Search by field value
   - Search within specific object types/classes
   
2. CSV Export
   - Flatten nested objects into columns
   - Handle collections/arrays (maybe comma-separated in single cell)
   - Let user select which fields to export
   - Handle null values gracefully

3. Filtering
   - Filter by object type/class name
   - Filter by field existence (e.g., show only objects that have field X)
   - Filter by field value ranges

4. Default Display: 50-100 lines with pagination

Make sure you introduce as few as external dependencies as possible while implementing these features.
Add automated tests to verify functionality.

## Environment Setup

```bash
# Standard installation
source .venv/bin/activate
pip install -e .

# Air-gapped / no-pip usage (run directly from source)
./run_cqviewer.sh info data.cq4
# or
PYTHONPATH=src python -m cqviewer.cli info data.cq4
```

## Python Version

Python 3.10+ (tested with 3.10.8 and 3.13)
