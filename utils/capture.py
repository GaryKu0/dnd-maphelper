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
    import os
    
    # Try to get monitor names on Windows
    monitor_names = {}
    if os.name == 'nt':
        try:
            import winreg
            # Query registry for display device names
            reg_path = r"SYSTEM\CurrentControlSet\Enum\DISPLAY"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as display_key:
                i = 0
                while True:
                    try:
                        device_key_name = winreg.EnumKey(display_key, i)
                        device_path = f"{reg_path}\\{device_key_name}"
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, device_path) as device_key:
                            j = 0
                            while True:
                                try:
                                    instance_key_name = winreg.EnumKey(device_key, j)
                                    instance_path = f"{device_path}\\{instance_key_name}"
                                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, instance_path) as instance_key:
                                        try:
                                            device_desc = winreg.QueryValueEx(instance_key, "DeviceDesc")[0]
                                            # Remove driver info prefix (e.g. "@oem123.inf,%desc%;")
                                            if ";" in device_desc:
                                                device_desc = device_desc.split(";")[-1]
                                            monitor_names[len(monitor_names) + 1] = device_desc
                                        except FileNotFoundError:
                                            pass
                                    j += 1
                                except OSError:
                                    break
                        i += 1
                    except OSError:
                        break
        except (ImportError, OSError):
            pass
    
    with mss.mss() as sct:
        monitors = []
        for i, mon in enumerate(sct.monitors):
            if i == 0:  # Skip the virtual combined monitor
                continue
            
            # Use monitor name if available, otherwise fall back to generic description
            if i in monitor_names:
                description = f"Monitor {i}: {monitor_names[i]} ({mon['width']}x{mon['height']})"
            else:
                description = f"Monitor {i}: {mon['width']}x{mon['height']} at ({mon['left']}, {mon['top']})"
            
            monitors.append({
                'index': i,
                'width': mon['width'],
                'height': mon['height'],
                'left': mon['left'],
                'top': mon['top'],
                'description': description
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
