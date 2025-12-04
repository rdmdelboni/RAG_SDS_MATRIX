#!/usr/bin/env python
"""Remove old _create_*_tab methods from app.py after UI refactoring."""

from pathlib import Path

APP_FILE = Path("src/ui/app.py")

# Line ranges to delete (these are the old tab creation methods)
# We keep the actual handler methods as they're still needed during transition
SECTIONS_TO_DELETE = [
    # (start_line, end_line, description)
    (229, 773, "_create_rag_tab through _create_placeholder_tab and blank line"),
    (1151, 1357, "# === Regex Lab tab === through # === Automation tab ==="),
    (1358, 1493, "_create_automation_tab and handlers through # === Automation actions ==="),
]

def get_lines(file_path):
    """Read file and return list of lines."""
    with open(file_path, 'r') as f:
        return f.readlines()

def delete_sections(lines, sections):
    """Delete specified line ranges (1-indexed)."""
    # Convert to 0-indexed and sort in reverse to avoid index shifting
    deletions = [(start-1, end) for start, end, _ in sorted(sections, reverse=True)]

    for start, end in deletions:
        del lines[start:end]
        print(f"Deleted lines {start+1}-{end}")

    return lines

def main():
    print("=" * 70)
    print("CLEANUP: Removing old _create_*_tab methods")
    print("=" * 70)

    if not APP_FILE.exists():
        print(f"Error: {APP_FILE} not found")
        return False

    # Read file
    lines = get_lines(APP_FILE)
    print(f"Read {len(lines)} lines from {APP_FILE}")

    # Show what will be deleted
    print("\nSections to delete:")
    for start, end, desc in SECTIONS_TO_DELETE:
        print(f"  Lines {start}-{end}: {desc}")

    # Delete sections
    print("\nDeleting sections...")
    new_lines = delete_sections(lines, SECTIONS_TO_DELETE)

    # Write back
    with open(APP_FILE, 'w') as f:
        f.writelines(new_lines)

    print(f"\nWrote {len(new_lines)} lines back to {APP_FILE}")
    print(f"Removed ~{sum(end-start for start,end,_ in SECTIONS_TO_DELETE)} lines")

    print("\n" + "=" * 70)
    print("✓ Cleanup complete")
    print("=" * 70)
    print("\nNote: Handler methods are preserved for transition period.")
    print("These will be integrated into tab classes during Phase A (Implement Handlers)")

    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
