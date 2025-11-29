# EditableTable Component Guide

## Overview

The `EditableTable` is an enhanced table widget inspired by the tkintertable project, providing rich interactivity for viewing and editing tabular data.

## Features

### Core Functionality
- **Row Selection**: Single or multiple row selection with visual highlighting
- **Cell Editing**: Double-click or press Enter to edit cell values
- **Keyboard Navigation**: Arrow keys, Tab, Enter, and Escape for efficient navigation
- **Column Sorting**: Click column headers to sort data (ascending/descending)
- **Context Menu**: Right-click for copy/paste operations
- **Callbacks**: Hooks for cell edits, row selection, and double-click events

### Visual Features
- Alternating row colors for better readability
- Highlighted selected rows
- Professional dark theme matching CustomTkinter
- Scrollable canvas for large datasets
- Resizable columns

## Basic Usage

```python
from src.ui.components import EditableTable

# Create table with headers and data
headers = ["Name", "Age", "Email", "Status"]
rows = [
    ["Alice", 30, "alice@example.com", "Active"],
    ["Bob", 25, "bob@example.com", "Pending"],
    ["Charlie", 35, "charlie@example.com", "Active"],
]

table = EditableTable(
    parent_frame,
    headers=headers,
    rows=rows,
    editable=True,
    on_cell_edit=handle_cell_edit,
    on_row_select=handle_row_select,
    on_row_double_click=handle_row_double_click
)
table.pack(fill="both", expand=True, padx=10, pady=10)
```

## Parameters

### Required
- `master`: Parent widget

### Optional
- `headers`: List of column header names
- `rows`: List of row data (each row is a list of values)
- `fg_color`: Background color (default: "#0f172a")
- `text_color`: Text color (default: "#e2e8f0")
- `header_color`: Header background color (default: "#1e293b")
- `accent_color`: Accent color for borders (default: "#4fd1c5")
- `selected_color`: Selected row background (default: "#334155")
- `font`: Regular text font (default: ("JetBrains Mono", 11))
- `header_font`: Header font (default: ("JetBrains Mono", 11, "bold"))
- `row_height`: Height of each row in pixels (default: 30)
- `min_col_width`: Minimum column width (default: 80)
- `editable`: Enable/disable cell editing (default: True)
- `on_cell_edit`: Callback when cell is edited: `(row_idx, col_idx, new_value) -> None`
- `on_row_select`: Callback when row is selected: `(row_idx) -> None`
- `on_row_double_click`: Callback when row is double-clicked: `(row_idx) -> None`

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Arrow Keys** | Navigate between cells |
| **Enter** | Start editing selected cell |
| **Escape** | Cancel cell editing |
| **Tab** | Move to next cell |
| **Shift+Tab** | Move to previous cell |
| **Ctrl+C** | Copy selected cell |
| **Ctrl+V** | Paste into selected cell |

## Mouse Interactions

| Action | Result |
|--------|--------|
| **Click Row** | Select row |
| **Double-Click Cell** | Start editing cell |
| **Click Header** | Sort by column (toggle asc/desc) |
| **Right-Click** | Show context menu |

## Methods

### Data Management
```python
# Clear all rows
table.clear()

# Update table with new data
table.update_data(new_rows)

# Get all current data
data = table.get_data()

# Get selected row indices
selected = table.get_selected_rows()
```

### Selection
```python
# Select specific row
table.select_row(row_index)

# Clear selection
table.clear_selection()

# Get selected rows
indices = table.get_selected_rows()
```

## Callback Examples

### Cell Edit Callback
```python
def handle_cell_edit(row_idx: int, col_idx: int, new_value: Any):
    """Called when user edits a cell."""
    print(f"Cell [{row_idx}, {col_idx}] changed to: {new_value}")
    
    # Update database or perform validation
    if validate_value(new_value):
        update_database(row_idx, col_idx, new_value)
    else:
        show_error("Invalid value")
```

### Row Selection Callback
```python
def handle_row_select(row_idx: int):
    """Called when user selects a row."""
    print(f"Row {row_idx} selected")
    
    # Display details in another panel
    show_details(table.get_data()[row_idx])
```

### Row Double-Click Callback
```python
def handle_row_double_click(row_idx: int):
    """Called when user double-clicks a row."""
    print(f"Row {row_idx} double-clicked")
    
    # Open edit dialog
    open_edit_dialog(table.get_data()[row_idx])
```

## Integration Example

Here's a complete example showing integration with a database:

```python
import customtkinter as ctk
from src.ui.components import EditableTable
from src.database.duckdb_manager import DuckDBManager

class DataViewer(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        
        self.db = DuckDBManager()
        
        # Create table
        self.table = EditableTable(
            self,
            headers=["ID", "Name", "Value", "Status"],
            editable=True,
            on_cell_edit=self._on_cell_edit,
            on_row_double_click=self._on_row_double_click
        )
        self.table.pack(fill="both", expand=True)
        
        # Load data
        self.refresh_data()
    
    def refresh_data(self):
        """Load data from database."""
        rows = self.db.fetch_results("SELECT id, name, value, status FROM items")
        self.table.update_data(rows)
    
    def _on_cell_edit(self, row_idx: int, col_idx: int, new_value: Any):
        """Save cell edit to database."""
        data = self.table.get_data()[row_idx]
        item_id = data[0]  # First column is ID
        
        # Map column index to field name
        fields = ["id", "name", "value", "status"]
        field = fields[col_idx]
        
        # Update database
        self.db.execute(
            f"UPDATE items SET {field} = ? WHERE id = ?",
            (new_value, item_id)
        )
        print(f"Updated {field} for item {item_id}")
    
    def _on_row_double_click(self, row_idx: int):
        """Open detail view for row."""
        data = self.table.get_data()[row_idx]
        print(f"Opening detail view for: {data}")
```

## Styling

You can customize the appearance:

```python
table = EditableTable(
    master,
    fg_color="#1a1a2e",           # Dark blue background
    text_color="#eee",             # Light text
    header_color="#16213e",        # Darker header
    accent_color="#0f4c75",        # Blue accent
    selected_color="#3282b8",      # Bright blue selection
    font=("Arial", 10),
    header_font=("Arial", 10, "bold"),
    row_height=35
)
```

## Performance Tips

1. **Large Datasets**: The table uses a canvas with scrolling, so it handles large datasets efficiently
2. **Batch Updates**: Use `update_data()` instead of adding rows one by one
3. **Disable Editing**: Set `editable=False` for read-only tables to improve performance
4. **Selective Callbacks**: Only add callbacks you actually need

## Troubleshooting

### Issue: Cell editing not working
- Check that `editable=True` is set
- Verify callbacks are not raising exceptions
- Ensure data types are serializable

### Issue: Slow performance with many rows
- Consider pagination for very large datasets
- Use `update_data()` instead of repeated `insert_row()` calls
- Profile callback functions for performance issues

### Issue: Colors not applying correctly
- The table uses a mix of tkinter Frame and CustomTkinter widgets
- Some styling is handled via `type: ignore` comments for cross-compatibility
- If colors don't apply, check the theme settings

## Comparison with Other Tables

| Feature | EditableTable | AdvancedTable | SimpleTable |
|---------|---------------|---------------|-------------|
| Cell Editing | ✅ Double-click | ❌ | ❌ |
| Row Selection | ✅ With highlight | ⚠️ Basic | ❌ |
| Sorting | ✅ Click header | ⚠️ Limited | ❌ |
| Keyboard Nav | ✅ Full | ❌ | ❌ |
| Context Menu | ✅ | ❌ | ❌ |
| Best For | Interactive data entry | Read-only display with search | Simple lists |

## Credits

Inspired by the [tkintertable](https://github.com/dmnfarrell/tkintertable) project, adapted for CustomTkinter and modern Python practices.
