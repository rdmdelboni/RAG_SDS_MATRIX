"""Window management and positioning for the application.

Handles:
- Responsive window sizing based on screen dimensions
- Window state preservation (position, size)
- Maximize prevention
- Multi-monitor support
- DPI-aware scaling
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WindowState:
    """Represents the saved window state."""

    x: int
    y: int
    width: int
    height: int
    is_maximized: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "is_maximized": self.is_maximized,
        }

    @staticmethod
    def from_dict(data: dict) -> WindowState:
        """Create from dictionary."""
        return WindowState(
            x=data.get("x", 0),
            y=data.get("y", 0),
            width=data.get("width", 900),
            height=data.get("height", 600),
            is_maximized=data.get("is_maximized", False),
        )


class WindowManager:
    """Manages window sizing, positioning, and state persistence."""

    def __init__(self, window, settings=None):
        """Initialize window manager.

        Args:
            window: Tkinter window instance (ctk.CTk)
            settings: Application settings (uses default if None)
        """
        self.window = window
        self.settings = settings or get_settings()
        self.state_file = Path(self.settings.paths.data_dir) / ".window_state.json"
        self.is_initializing = True
        self.state_was_restored = False

    def initialize(self) -> None:
        """Initialize window positioning and sizing.

        Call this after window creation to set initial size and position.
        """
        try:
            # First try to restore previous state
            if self._restore_saved_state():
                logger.info("Restored window state from saved session")
                self.is_initializing = False
                self.state_was_restored = True
                return

            # Otherwise use defaults
            self._apply_default_sizing()
            self.is_initializing = False
            logger.info("Applied default window sizing")

        except Exception as e:
            logger.error(f"Error initializing window: {e}")
            self._apply_default_sizing()
            self.is_initializing = False

    def _restore_saved_state(self) -> bool:
        """Try to restore window state from previous session.

        Returns:
            True if restoration was successful
        """
        try:
            if not self.state_file.exists():
                return False

            with open(self.state_file, "r") as f:
                data = json.load(f)

            state = WindowState.from_dict(data)

            # Validate state is reasonable (not off-screen, minimum size)
            if not self._is_valid_state(state):
                logger.warning("Saved window state is invalid, using defaults")
                return False

            # Apply saved state
            self.window.geometry(f"{state.width}x{state.height}+{state.x}+{state.y}")
            logger.debug(f"Restored window state: {state.width}x{state.height}+{state.x}+{state.y}")

            return True

        except Exception as e:
            logger.warning(f"Failed to restore window state: {e}")
            return False

    def _apply_default_sizing(self) -> None:
        """Apply default window sizing based on screen dimensions."""
        try:
            self.window.update_idletasks()

            # Get screen dimensions
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()

            # Detect multi-monitor and constrain to single monitor
            if screen_width > 3000:  # Likely multi-monitor setup
                screen_width = 1920  # Default to common single monitor width
            if screen_height > 2000:
                screen_height = 1080

            # Calculate responsive size: 85% of screen
            # This gives good workspace while leaving room for taskbar/other windows
            default_width = int(screen_width * 0.85)
            default_height = int(screen_height * 0.85)

            # Apply minimum size constraint
            window_width = max(default_width, self.settings.ui.min_width)
            window_height = max(default_height, self.settings.ui.min_height)

            # Apply maximum size constraint (don't go larger than screen)
            window_width = min(window_width, screen_width)
            window_height = min(window_height, screen_height)

            # Center on screen
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2

            # Ensure position is not negative and at least 20px from top
            x = max(0, x)
            y = max(20, y)

            # Set window geometry
            self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            logger.debug(f"Applied default sizing: {window_width}x{window_height}+{x}+{y}")

        except Exception as e:
            logger.error(f"Error applying default sizing: {e}")

    def _is_valid_state(self, state: WindowState) -> bool:
        """Check if a window state is valid (on-screen, minimum size).

        Args:
            state: Window state to validate

        Returns:
            True if state is valid
        """
        try:
            self.window.update_idletasks()

            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()

            # Constrain to single monitor for validation
            if screen_width > 3000:
                screen_width = 1920
            if screen_height > 2000:
                screen_height = 1080

            # Check minimum size
            if state.width < self.settings.ui.min_width or state.height < self.settings.ui.min_height:
                return False

            # Check position is reasonable (allowing some off-screen)
            # If window is mostly off-screen, it's invalid
            if state.x > screen_width - 100 or state.y > screen_height - 100:
                return False

            # Check window isn't impossibly large
            if state.width > screen_width * 1.5 or state.height > screen_height * 1.5:
                return False

            return True

        except Exception:
            return False

    def save_state(self) -> None:
        """Save current window state for next session."""
        if self.is_initializing:
            return  # Don't save during initialization

        try:
            self.window.update_idletasks()

            # Get current geometry
            geometry = self.window.geometry()
            # Format: WIDTHxHEIGHT+X+Y
            parts = geometry.replace("+", "x").split("x")
            width = int(parts[0])
            height = int(parts[1])
            x = int(parts[2])
            y = int(parts[3])

            # Get current state
            state = self.window.state()
            is_maximized = state == "zoomed"

            # Create state object
            window_state = WindowState(
                x=x,
                y=y,
                width=width,
                height=height,
                is_maximized=is_maximized,
            )

            # Save to file
            with open(self.state_file, "w") as f:
                json.dump(window_state.to_dict(), f, indent=2)

            logger.debug(f"Saved window state: {window_state}")

        except Exception as e:
            logger.error(f"Failed to save window state: {e}")

    def handle_window_configure(self, event=None) -> None:
        """Handle window configuration changes (resize, move, maximize).

        This prevents maximized state and maintains responsiveness.

        Args:
            event: Tkinter event (optional)
        """
        if self.is_initializing:
            return

        try:
            state = self.window.state()

            # Prevent maximize
            if state == "zoomed":
                logger.debug("Window maximized - restoring to normal")
                self.window.state("normal")
                self.window.after(100, self._apply_default_sizing)
                return

            # Save state on resize/move
            self.window.after(500, self.save_state)

        except Exception as e:
            logger.error(f"Error handling window configure: {e}")

    def handle_window_close(self) -> None:
        """Handle window close event - save state before closing."""
        try:
            self.save_state()
            self.window.destroy()
        except Exception as e:
            logger.error(f"Error closing window: {e}")
            self.window.destroy()

    def get_current_state(self) -> WindowState:
        """Get current window state.

        Returns:
            Current window state
        """
        try:
            self.window.update_idletasks()

            geometry = self.window.geometry()
            parts = geometry.replace("+", "x").split("x")
            width = int(parts[0])
            height = int(parts[1])
            x = int(parts[2])
            y = int(parts[3])

            state = self.window.state()
            is_maximized = state == "zoomed"

            return WindowState(
                x=x,
                y=y,
                width=width,
                height=height,
                is_maximized=is_maximized,
            )

        except Exception as e:
            logger.error(f"Error getting window state: {e}")
            return WindowState(0, 0, self.settings.ui.window_width, self.settings.ui.window_height)


def create_window_manager(window, settings=None) -> WindowManager:
    """Factory function to create and initialize a window manager.

    Args:
        window: Tkinter window instance
        settings: Application settings (optional)

    Returns:
        Initialized WindowManager instance
    """
    manager = WindowManager(window, settings)
    manager.initialize()
    return manager
