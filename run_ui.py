#!/usr/bin/env python3
"""
CQViewer UI - Web-based user interface for Chronicle Queue files.

Uses only company-approved dependencies:
- streamlit: Modern web UI framework
- pandas: Data manipulation

Usage:
    python run_ui.py

Or with specific port:
    python run_ui.py -- --server.port 8501
"""

import sys
import os
import subprocess
from pathlib import Path

# Auto-launch with streamlit if run directly with python
if __name__ == "__main__":
    # Check if already running under streamlit by looking for its runtime
    try:
        from streamlit.runtime import exists
        is_streamlit = exists()
    except ImportError:
        is_streamlit = False

    if not is_streamlit:
        # Use current Python's streamlit module
        args = [sys.executable, "-m", "streamlit", "run", __file__, "--server.address=localhost"]

        # Pass any additional args after --
        if "--" in sys.argv:
            idx = sys.argv.index("--")
            args.extend(sys.argv[idx + 1:])

        sys.exit(subprocess.call(args))

# Add src to path for direct execution
sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st
import pandas as pd

from cqviewer.services.message_service import MessageService
from cqviewer.services.search_service import SearchService
from cqviewer.services.filter_service import FilterService
from cqviewer.services.export_service import ExportService


# Page configuration
st.set_page_config(
    page_title="CQViewer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_resource
def get_services():
    """Get cached service instances."""
    return {
        "message": MessageService(),
        "search": SearchService(),
        "filter": FilterService(),
        "export": ExportService()
    }


def load_data(path: str, include_metadata: bool = False):
    """Load data from file or folder."""
    services = get_services()
    msg_service = services["message"]

    p = Path(path)

    schema_loaded = False

    if p.is_dir():
        # Load schema from directory if available
        java_files = list(p.rglob("*.java")) + list(p.rglob("*.class"))
        if java_files:
            try:
                msg_service.load_schema_directory(str(p))
                schema_loaded = True
            except Exception:
                pass

        # Find .cq4 files
        cq4_files = list(p.glob("*.cq4"))
        if not cq4_files:
            return None, "No .cq4 files found in folder"
        file_path = str(cq4_files[0])
    else:
        file_path = str(p)

    try:
        info = msg_service.load_file(file_path, include_metadata=include_metadata)
        messages = msg_service.get_all_messages()
        types = msg_service.get_unique_types()
        fields = msg_service.get_all_field_names()

        return {
            "info": info,
            "messages": messages,
            "types": types,
            "fields": fields,
            "schema_loaded": schema_loaded
        }, None
    except Exception as e:
        return None, str(e)


def messages_to_dataframe(messages, columns=None):
    """Convert messages to pandas DataFrame."""
    if not messages:
        return pd.DataFrame()

    rows = []
    for msg in messages:
        row = {
            "Index": msg.index,
            "Type": msg.type_hint or "unknown",
            "Offset": msg.offset
        }
        for name, field in msg.fields.items():
            if columns is None or name in columns:
                row[name] = field.format_value()  # No truncation
        rows.append(row)

    return pd.DataFrame(rows)


def main():
    st.title("📊 CQViewer")
    st.markdown("Chronicle Queue (.cq4) File Viewer")

    # Initialize session state
    if "selected_path" not in st.session_state:
        st.session_state.selected_path = ""
    if "browser_path" not in st.session_state:
        st.session_state.browser_path = str(Path.home())

    # Sidebar for configuration
    with st.sidebar:
        st.header("📁 Load Data")

        # File browser
        current_path = Path(st.session_state.browser_path)

        # Quick navigation
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏠 Home", use_container_width=True):
                st.session_state.browser_path = str(Path.home())
                st.rerun()
        with col2:
            if st.button("🖥️ Desktop", use_container_width=True):
                st.session_state.browser_path = str(Path.home() / "Desktop")
                st.rerun()

        # Manual path input
        manual_path = st.text_input(
            "Or enter path",
            placeholder="Paste folder or .cq4 file path",
            key="manual_path_input"
        )
        if manual_path:
            if st.button("Go / Select", use_container_width=True):
                p = Path(manual_path)
                if p.exists():
                    if p.is_file() and p.suffix == '.cq4':
                        # Directly select the file
                        st.session_state.selected_path = str(p)
                        st.rerun()
                    elif p.is_dir():
                        # Navigate to folder
                        st.session_state.browser_path = str(p)
                        st.rerun()
                    else:
                        st.error("Not a folder or .cq4 file")
                else:
                    st.error("Path not found")

        st.caption(f"Current: {current_path}")

        # List directory contents
        try:
            items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            folders = [p for p in items if p.is_dir() and not p.name.startswith('.')]
            cq4_files = [p for p in items if p.suffix == '.cq4']
        except PermissionError:
            st.error("Permission denied")
            folders, cq4_files = [], []

        # Folder navigation
        folder_options = ["── Select folder ──"] + [f"📁 {f.name}" for f in folders]
        selected_folder = st.selectbox("Folders", folder_options, key="folder_nav")

        if selected_folder != "── Select folder ──":
            folder_name = selected_folder.replace("📁 ", "")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Open", use_container_width=True):
                    st.session_state.browser_path = str(current_path / folder_name)
                    st.rerun()
            with col2:
                if st.button("✓ Use Folder", use_container_width=True):
                    st.session_state.selected_path = str(current_path / folder_name)
                    st.rerun()

        # File selection
        if cq4_files:
            file_options = ["── Select .cq4 file ──"] + [f"📄 {f.name}" for f in cq4_files]
            selected_file = st.selectbox(".cq4 Files", file_options, key="file_nav")

            if selected_file != "── Select .cq4 file ──":
                file_name = selected_file.replace("📄 ", "")
                if st.button("✓ Use File", use_container_width=True):
                    st.session_state.selected_path = str(current_path / file_name)
                    st.rerun()

        st.divider()

        # Selected path display
        path = st.session_state.selected_path
        if path:
            st.success(f"Selected: {Path(path).name}")

        include_metadata = st.checkbox("Include metadata messages", value=False)

        load_button = st.button("Load", type="primary", use_container_width=True, disabled=not path)

        st.divider()

        # Session state for loaded data
        if "data" not in st.session_state:
            st.session_state.data = None
            st.session_state.error = None

    # Load data when button clicked
    if load_button and path:
        with st.spinner("Loading..."):
            data, error = load_data(path, include_metadata)
            st.session_state.data = data
            st.session_state.error = error

    # Show error if any
    if st.session_state.error:
        st.error(f"Error: {st.session_state.error}")
        return

    # Show data if loaded
    if st.session_state.data is None:
        st.info("👆 Enter a path in the sidebar and click Load to view Chronicle Queue data")
        return

    data = st.session_state.data
    info = data["info"]
    messages = data["messages"]
    types = data["types"]
    fields = data["fields"]

    # Info panel
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Messages", info.message_count)
    with col2:
        st.metric("File Size", info.file_size_str)
    with col3:
        st.metric("Message Types", len(types))
    with col4:
        st.metric("Schema", "✓ Loaded" if data["schema_loaded"] else "Not loaded")

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Messages", "🔍 Search", "📊 Types & Fields", "💾 Export"])

    with tab1:
        st.subheader("Message List")

        # Filters
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            type_filter = st.selectbox(
                "Filter by Type",
                options=["All"] + types,
                index=0
            )
        with col2:
            field_filter = st.selectbox(
                "Filter by Field Exists",
                options=["All"] + fields,
                index=0
            )
        with col3:
            page_size = st.selectbox("Page Size", [25, 50, 100, 200], index=1)

        # Apply filters
        filtered = messages
        services = get_services()

        if type_filter != "All":
            filtered = services["filter"].filter_by_type(filtered, type_filter)

        if field_filter != "All":
            filtered = services["filter"].filter_by_field_exists(filtered, field_filter)

        # Pagination
        total = len(filtered)
        total_pages = (total + page_size - 1) // page_size
        page = st.number_input("Page", min_value=1, max_value=max(1, total_pages), value=1)

        start = (page - 1) * page_size
        end = min(start + page_size, total)
        page_messages = filtered[start:end]

        st.caption(f"Showing {start + 1}-{end} of {total} messages")

        # Display as dataframe
        if page_messages:
            df = messages_to_dataframe(page_messages)

            # Select columns to display (all columns by default)
            available_cols = list(df.columns)
            selected_cols = st.multiselect(
                "Columns to display",
                options=available_cols,
                default=available_cols
            )

            if selected_cols:
                st.dataframe(
                    df[selected_cols],
                    use_container_width=True,
                    hide_index=True
                )

                # Cell value viewer
                st.subheader("Cell Value Viewer")
                col1, col2 = st.columns([1, 1])
                with col1:
                    row_idx = st.number_input(
                        "Row number",
                        min_value=0,
                        max_value=max(0, len(df) - 1),
                        value=0,
                        key="cell_viewer_row"
                    )
                with col2:
                    cell_column = st.selectbox(
                        "Column",
                        options=selected_cols,
                        key="cell_viewer_col"
                    )

                cell_value = df.iloc[row_idx].get(cell_column, "")
                st.text_area(
                    f"Full value of '{cell_column}' (Row {row_idx})",
                    value=str(cell_value),
                    height=150,
                    key="cell_value_display"
                )

        # Message detail view
        st.subheader("Message Detail")
        msg_index = st.number_input(
            "Enter message index to view details",
            min_value=0,
            max_value=max(0, len(messages) - 1),
            value=0
        )

        if st.button("View Message"):
            msg = services["message"].get_message(msg_index)
            if msg:
                st.json({
                    "index": msg.index,
                    "offset": msg.offset,
                    "type": msg.type_hint,
                    "fields": {name: field.format_value() for name, field in msg.fields.items()}
                })
            else:
                st.warning(f"Message {msg_index} not found")

    with tab2:
        st.subheader("Search")

        search_query = st.text_input("Search query", placeholder="Enter search term...")

        col1, col2 = st.columns(2)
        with col1:
            search_type = st.radio(
                "Search in",
                ["All", "Field Names", "Field Values", "Message Types"],
                horizontal=True
            )
        with col2:
            max_results = st.slider("Max results", 10, 200, 50)

        if search_query:
            with st.spinner("Searching..."):
                if search_type == "Field Names":
                    results = services["search"].search_by_field_name(messages, search_query)
                elif search_type == "Field Values":
                    results = services["search"].search_by_field_value(messages, search_query)
                elif search_type == "Message Types":
                    results = services["search"].search_by_type(messages, search_query)
                else:
                    results = services["search"].search_combined(messages, search_query)

            st.success(f"Found {len(results)} matches")

            if results:
                df = messages_to_dataframe(results[:max_results])
                st.dataframe(df, use_container_width=True, hide_index=True)

                if len(results) > max_results:
                    st.caption(f"Showing first {max_results} of {len(results)} results")

    with tab3:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Message Types")
            type_data = []
            for t in types:
                count = sum(1 for m in messages if m.type_hint == t)
                type_data.append({"Type": t, "Count": count})
            st.dataframe(pd.DataFrame(type_data), use_container_width=True, hide_index=True)

        with col2:
            st.subheader("Unique Fields")
            field_data = [{"Field": f} for f in fields]
            st.dataframe(pd.DataFrame(field_data), use_container_width=True, hide_index=True)

    with tab4:
        st.subheader("Export to CSV")

        # Filter options
        export_type = st.selectbox(
            "Filter by Type (optional)",
            options=["All"] + types,
            index=0,
            key="export_type"
        )

        # Field selection
        st.write("Select fields to export:")
        export_fields = st.multiselect(
            "Fields",
            options=fields,
            default=fields[:10] if len(fields) > 10 else fields
        )

        # Options
        col1, col2, col3 = st.columns(3)
        with col1:
            include_index = st.checkbox("Include Index", value=True)
        with col2:
            include_type_col = st.checkbox("Include Type", value=True)
        with col3:
            include_offset = st.checkbox("Include Offset", value=False)

        if st.button("Generate CSV", type="primary"):
            export_messages = messages
            if export_type != "All":
                export_messages = services["filter"].filter_by_type(export_messages, export_type)

            if not export_messages:
                st.warning("No messages to export")
            else:
                # Build dataframe for export
                rows = []
                for msg in export_messages:
                    row = {}
                    if include_index:
                        row["Index"] = msg.index
                    if include_type_col:
                        row["Type"] = msg.type_hint or ""
                    if include_offset:
                        row["Offset"] = msg.offset
                    for field_name in export_fields:
                        field = msg.get_field(field_name)
                        row[field_name] = field.format_value() if field else ""
                    rows.append(row)

                export_df = pd.DataFrame(rows)
                csv = export_df.to_csv(index=False)

                st.download_button(
                    label=f"Download CSV ({len(export_messages)} messages)",
                    data=csv,
                    file_name="cqviewer_export.csv",
                    mime="text/csv",
                    type="primary"
                )

                # Preview
                st.subheader("Preview (first 10 rows)")
                st.dataframe(export_df.head(10), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()