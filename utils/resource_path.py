"""Resource path utility for PyInstaller compatibility."""
import os
import sys


def is_executable():
    """Check if running as a PyInstaller executable."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller.

    When running as a PyInstaller bundle, resources are extracted to _MEIPASS.
    In development, resources are in the current directory.

    Args:
        relative_path: Path relative to the application root (e.g., 'maps/Ruins')

    Returns:
        Absolute path to the resource
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Running in development - use current directory
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
