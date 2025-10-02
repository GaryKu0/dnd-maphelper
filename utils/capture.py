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
            import ctypes
            from ctypes import wintypes
            
            # Use Windows Display API to get monitor information
            try:
                user32 = ctypes.windll.user32
                
                # Structure for MONITORINFOEX
                class MONITORINFOEX(ctypes.Structure):
                    _fields_ = [
                        ('cbSize', wintypes.DWORD),
                        ('rcMonitor', wintypes.RECT),
                        ('rcWork', wintypes.RECT),
                        ('dwFlags', wintypes.DWORD),
                        ('szDevice', ctypes.c_wchar * 32)
                    ]
                
                monitor_count = [0]  # Use list to allow modification in callback
                
                def enum_monitor_callback(hmonitor, hdc, lprect, lparam):
                    monitor_info = MONITORINFOEX()
                    monitor_info.cbSize = ctypes.sizeof(MONITORINFOEX)
                    
                    if user32.GetMonitorInfoW(hmonitor, ctypes.byref(monitor_info)):
                        device_name = monitor_info.szDevice
                        
                        # Try to get friendly name from registry
                        try:
                            # Look in multiple registry locations for monitor names
                            registry_paths = [
                                f"SYSTEM\\CurrentControlSet\\Enum\\DISPLAY\\{device_name}",
                                f"SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e96e-e325-11ce-bfc1-08002be10318}}",
                            ]
                            
                            friendly_name = None
                            for reg_path in registry_paths:
                                try:
                                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                                        try:
                                            friendly_name = winreg.QueryValueEx(key, "FriendlyName")[0]
                                            break
                                        except FileNotFoundError:
                                            try:
                                                device_desc = winreg.QueryValueEx(key, "DeviceDesc")[0]
                                                if ";" in device_desc:
                                                    device_desc = device_desc.split(";")[-1]
                                                friendly_name = device_desc
                                                break
                                            except FileNotFoundError:
                                                continue
                                except OSError:
                                    continue
                            
                            if friendly_name:
                                monitor_names[monitor_count[0] + 1] = friendly_name
                            else:
                                monitor_names[monitor_count[0] + 1] = f"Monitor {monitor_count[0] + 1}"
                                
                        except Exception:
                            monitor_names[monitor_count[0] + 1] = f"Monitor {monitor_count[0] + 1}"
                        
                        monitor_count[0] += 1
                    
                    return True
                
                # Define callback type
                MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
                callback = MONITORENUMPROC(enum_monitor_callback)
                
                # Enumerate monitors
                user32.EnumDisplayMonitors(None, None, callback, 0)
                
            except Exception as e:
                # Fallback: Use simple registry enumeration
                try:
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
                                                    friendly_name = winreg.QueryValueEx(instance_key, "FriendlyName")[0]
                                                    monitor_names[len(monitor_names) + 1] = friendly_name
                                                except FileNotFoundError:
                                                    try:
                                                        device_desc = winreg.QueryValueEx(instance_key, "DeviceDesc")[0]
                                                        if ";" in device_desc:
                                                            device_desc = device_desc.split(";")[-1]
                                                        monitor_names[len(monitor_names) + 1] = device_desc
                                                    except FileNotFoundError:
                                                        monitor_names[len(monitor_names) + 1] = f"Monitor {len(monitor_names) + 1}"
                                        except OSError:
                                            pass
                                        j += 1
                            except OSError:
                                break
                            i += 1
                except OSError:
                    pass
                    
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
                print(f"[Debug] Found monitor name for {i}: {monitor_names[i]}")
            else:
                description = f"Monitor {i}: {mon['width']}x{mon['height']} at ({mon['left']}, {mon['top']})"
                print(f"[Debug] No monitor name found for {i}, using generic description")
            
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
