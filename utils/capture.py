import mss
import numpy as np
import cv2

# Global monitor selection (1 = primary monitor by default)
_selected_monitor = 1


def set_monitor(monitor_index):
    """Set which monitor to capture from (1-based index)."""
    global _selected_monitor
    _selected_monitor = monitor_index


def get_monitor():
    """Get current monitor index."""
    return _selected_monitor


def get_all_monitors():
    """Get information about all available monitors.
    Returns list of (index, width, height, description) tuples."""
    with mss.mss() as sct:
        monitors = []
        for i, mon in enumerate(sct.monitors):
            if i == 0:  # Skip the virtual combined monitor
                continue
            monitors.append({
                'index': i,
                'width': mon['width'],
                'height': mon['height'],
                'left': mon['left'],
                'top': mon['top'],
                'description': f"Monitor {i}: {mon['width']}x{mon['height']} at ({mon['left']}, {mon['top']})"
            })
        return monitors


def capture_screen(monitor_index=None):
    """Capture screen from specified monitor (uses global selection if None)."""
    if monitor_index is None:
        monitor_index = _selected_monitor

    with mss.mss() as sct:
        mon = sct.monitors[monitor_index]
        img = np.array(sct.grab(mon))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def screen_resolution_key(monitor_index=None):
    """Get resolution key for specified monitor (uses global selection if None)."""
    if monitor_index is None:
        monitor_index = _selected_monitor

    with mss.mss() as sct:
        mon = sct.monitors[monitor_index]
        w, h = mon["width"], mon["height"]
        return f"{w}x{h}_mon{monitor_index}", (w, h)
