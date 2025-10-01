"""Map Helper - Main Entry Point"""
import os
import sys
import time
import threading
import keyboard
import atexit
from contextlib import contextmanager

from utils.config import Config
from utils.capture import capture_screen, screen_resolution_key, get_all_monitors, set_monitor
from utils.settings import get_settings
from utils.resource_path import resource_path
from ui.overlay_manager import OverlayManager
from ui.dialogs import (
    show_main_menu,
    show_settings_dialog,
    show_map_confirmation,
    show_title_overlay,
    show_monitor_selection,
)
from core.detection import RealtimeDetector
from ui.system_tray import SystemTrayManager
import matcher

MAPS_ROOT = resource_path("maps")

app_settings = get_settings()
config_lock = threading.Lock()
config_store = Config("config.json")

overlay = None
detector = None
tray_manager = None

shutdown_event = threading.Event()
input_block_event = threading.Event()

map_showing = False
current_roi = None
current_monitor_info = None

# Single instance handling
LOCK_FILE = "maphelper.lock"
lock_file_handle = None


def acquire_single_instance_lock():
    """Acquire single instance lock. Returns True if successful, False if another instance is running."""
    global lock_file_handle
    
    try:
        # Try to create/open the lock file exclusively
        if os.name == 'nt':  # Windows
            import msvcrt
            lock_file_handle = open(LOCK_FILE, 'w')
            msvcrt.locking(lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:  # Unix-like systems
            import fcntl
            lock_file_handle = open(LOCK_FILE, 'w')
            fcntl.flock(lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        # Write PID to lock file
        lock_file_handle.write(str(os.getpid()))
        lock_file_handle.flush()
        
        # Register cleanup function
        atexit.register(release_single_instance_lock)
        
        return True
        
    except (IOError, OSError):
        # Lock file is already locked by another instance
        if lock_file_handle:
            try:
                lock_file_handle.close()
            except:
                pass
        return False


def release_single_instance_lock():
    """Release the single instance lock."""
    global lock_file_handle
    
    if lock_file_handle:
        try:
            if os.name == 'nt':  # Windows
                import msvcrt
                msvcrt.locking(lock_file_handle.fileno(), msvcrt.LK_UNLCK, 1)
            lock_file_handle.close()
        except:
            pass
        lock_file_handle = None
    
    # Remove lock file
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except:
        pass


def get_available_maps():
    """Return a list of available map folders."""
    if not os.path.isdir(MAPS_ROOT):
        return []
    return [name for name in sorted(os.listdir(MAPS_ROOT))
            if os.path.isdir(os.path.join(MAPS_ROOT, name))]


def get_monitor_info(monitor_index, monitors=None):
    """Return monitor info dict for the provided index."""
    monitors = monitors or get_all_monitors()
    for mon in monitors:
        if mon['index'] == monitor_index:
            return mon
    return monitors[0] if monitors else None


@contextmanager
def block_user_input():
    """Temporarily block input handling while modal dialogs are shown."""
    input_block_event.set()
    try:
        try:
            keyboard.block_key("m")
        except Exception:
            pass
        yield
    finally:
        try:
            keyboard.unblock_key("m")
        except Exception:
            pass
        for _ in range(20):
            try:
                if not keyboard.is_pressed("m"):
                    break
            except Exception:
                break
            time.sleep(0.05)
        input_block_event.clear()


def stop_current_detection(hide_overlay=False):
    """Stop any running detector and optionally hide the overlay."""
    global detector, map_showing
    if detector:
        try:
            detector.stop_detection()
        except Exception:
            pass
        detector = None
    if hide_overlay and overlay:
        overlay.hide_grid()
    map_showing = False


def ensure_roi(force=False):
    """Ensure an ROI exists, prompting the user when required."""
    global current_roi

    res_key, _ = screen_resolution_key()
    with config_lock:
        stored_roi = config_store.get_roi(res_key)
    if stored_roi and not force:
        return stored_roi

    frame = capture_screen()

    if not overlay or not overlay.root:
        return stored_roi

    selected_roi = None
    with block_user_input():
        overlay.clear_popup_layers()
        overlay.root.deiconify()
        selected_roi = overlay.show_roi_selector(frame)
        overlay.root.withdraw()
        overlay.is_visible = False

    overlay.clear_popup_layers()

    if selected_roi:
        with config_lock:
            config_store.set_roi(res_key, selected_roi)
            config_store.save()
        matcher.reset_session()
        current_roi = selected_roi
        if overlay:
            overlay.add_status("[ROI] Selection saved")
        time.sleep(1.0)
        return selected_roi

    if stored_roi:
        if overlay:
            overlay.add_status("[ROI] Using existing selection")
        return stored_roi

    if overlay:
        overlay.add_status("[ROI] Selection cancelled")
    return None


def crop_roi(frame, roi):
    """Crop ROI from frame."""
    x, y, w, h = roi
    H, W = frame.shape[:2]
    x = max(0, min(W - 1, x))
    y = max(0, min(H - 1, y))
    w = max(1, min(W - x, w))
    h = max(1, min(H - y, h))
    return frame[y:y + h, x:x + w]


def initialize_monitor_selection():
    """Prompt for monitor selection on startup and apply it."""
    global current_monitor_info

    monitors = get_all_monitors()
    if not monitors:
        set_monitor(1)
        current_monitor_info = None
        return None

    stored_index = app_settings.get("monitor_index", monitors[0]['index'])
    if not any(mon['index'] == stored_index for mon in monitors):
        stored_index = monitors[0]['index']

    selected_index = stored_index
    if len(monitors) > 1:
        selection = show_monitor_selection()
        if selection:
            selected_index = selection

    set_monitor(selected_index)
    app_settings.set("monitor_index", selected_index)
    current_monitor_info = get_monitor_info(selected_index, monitors)
    return current_monitor_info


def apply_monitor_selection(monitor_index, monitors=None, notify=True):
    """Apply a monitor selection while the app is running."""
    global current_monitor_info, current_roi

    monitors = monitors or get_all_monitors()
    info = get_monitor_info(monitor_index, monitors)
    if not info:
        return False

    set_monitor(monitor_index)
    app_settings.set("monitor_index", monitor_index)

    stop_current_detection(hide_overlay=True)
    matcher.reset_session()
    current_roi = None
    current_monitor_info = info

    if overlay:
        overlay.update_monitor(info)
        if notify:
            overlay.add_status(f"[Monitor] Switched to monitor {monitor_index}")

    return True


def request_shutdown(status_message=None):
    """Initiate application shutdown."""
    global tray_manager

    if shutdown_event.is_set():
        return

    shutdown_event.set()

    if status_message and overlay:
        overlay.add_status(status_message)

    stop_current_detection(hide_overlay=True)

    if tray_manager:
        try:
            tray_manager.stop()
        except Exception:
            pass
        tray_manager = None

    # Release single instance lock
    release_single_instance_lock()

    if overlay:
        overlay.stop()


def keyboard_handler():
    """Handle keyboard shortcuts for the application."""
    global map_showing, current_roi, detector

    last_esc_press = 0
    title_canvas = None

    overlay.add_status("=== Map Helper Ready ===")
    overlay.add_status("Press M - Toggle map")
    overlay.add_status("Press R - Reset | ESC x2 - Exit")

    while not shutdown_event.is_set():
        if input_block_event.is_set():
            time.sleep(0.05)
            continue

        if keyboard.is_pressed("esc"):
            current_time = time.time()
            if current_time - last_esc_press < 1.0:
                request_shutdown("[Exit] Closing...")
                break
            last_esc_press = current_time
            overlay.add_status("[ESC] Press again to exit")
            time.sleep(0.5)
            continue

        if keyboard.is_pressed("r"):
            stop_current_detection(hide_overlay=True)
            matcher.reset_session()
            current_roi = None
            overlay.add_status("[Reset] Cache cleared")
            time.sleep(0.5)
            continue

        if keyboard.is_pressed("m"):
            overlay.add_status("[Input] M pressed")

            if matcher.is_cache_expired():
                overlay.add_status("[Cache] Expired - will re-identify")
                matcher.reset_session()
                map_showing = False
                current_roi = None

            if map_showing:
                overlay.hide_grid()
                map_showing = False
                if title_canvas:
                    try:
                        title_canvas.destroy()
                    except Exception:
                        pass
                    title_canvas = None
                overlay.add_status("[Overlay] Hidden")
                time.sleep(0.5)
                continue

            if current_roi and matcher._identified_map:
                map_folder = f"{MAPS_ROOT}/{matcher._identified_map}"
                grid_config = matcher.load_grid_config(map_folder) or (5, 5)
                language = app_settings.get("language", "en")
                location_names = matcher.load_location_names(map_folder, language)

                title_canvas = show_title_overlay(overlay.root, current_roi)
                overlay.show_grid(current_roi, grid_config, matcher._identified_cells, location_names)
                map_showing = True
                overlay.add_status(f"[Overlay] Showing {matcher._identified_map}")
                time.sleep(0.5)
                continue

            roi = ensure_roi()
            if not roi:
                time.sleep(0.5)
                continue

            frame = capture_screen()
            roi_img = crop_roi(frame, roi)
            current_roi = roi

            if matcher._identified_map is None:
                available_maps = get_available_maps()
                if not available_maps:
                    overlay.add_status("[Error] No maps found")
                    time.sleep(1.0)
                    continue

                while True:
                    choice, title_canvas = show_main_menu(overlay.root, available_maps, roi)

                    if choice == "CANCEL":
                        if title_canvas:
                            try:
                                title_canvas.destroy()
                            except Exception:
                                pass
                            title_canvas = None
                        overlay.add_status("[Cancelled]")
                        time.sleep(0.5)
                        break
                    if choice == "SETTINGS":
                        with block_user_input():
                            result = show_settings_dialog(overlay.root, app_settings)
                        overlay.clear_popup_layers()
                        if result == 'BACK':
                            continue
                        overlay.add_status("[Cancelled]")
                        time.sleep(0.5)
                        break
                    if choice is None:
                        matcher.reset_session()
                        overlay.add_status("[Auto-Detect] Checking first cell...")
                        candidates = matcher.identify_map_from_first_cell(roi_img, MAPS_ROOT)

                        if not candidates or not candidates[0]:
                            overlay.add_status("[Unknown] No match")
                            time.sleep(1.0)
                            continue

                        detected_map, confidence, detected_grid, _ = candidates[0]
                        overlay.add_status(f"[Found] {detected_map} ({confidence}% confidence)")

                        confirmation = show_map_confirmation(overlay.root, detected_map)

                        if confirmation == "YES":
                            map_name = detected_map
                            grid_config = detected_grid
                            matcher._identified_cells = {}
                            matcher._identified_map = map_name
                            matcher._cache_timestamp = time.time()
                            overlay.add_status(f"[Confirmed] {map_name}")
                            break
                        if confirmation == "NO":
                            overlay.add_status("[Rejected] Try again")
                            matcher.reset_session()
                            continue
                        if confirmation == "CHOOSE":
                            matcher.reset_session()
                            continue
                        overlay.add_status("[Cancelled]")
                        time.sleep(0.5)
                        break

                    else:
                        map_name = choice
                        grid_config = matcher.load_grid_config(f"{MAPS_ROOT}/{map_name}") or (5, 5)
                        matcher._identified_cells = {}
                        matcher._identified_map = map_name
                        matcher._cache_timestamp = time.time()
                        overlay.add_status(f"[Selected] {map_name}")
                        break

                if matcher._identified_map is None:
                    continue
            else:
                map_name = matcher._identified_map
                grid_config = matcher.load_grid_config(f"{MAPS_ROOT}/{map_name}") or (5, 5)

            map_showing = True
            map_folder = f"{MAPS_ROOT}/{map_name}"
            language = app_settings.get("language", "en")
            location_names = matcher.load_location_names(map_folder, language)
            overlay.show_grid(roi, grid_config, {}, location_names)

            detector = RealtimeDetector(
                overlay_callback=lambda r, g, c: overlay.show_grid(r, g, c, location_names),
                status_callback=lambda message: overlay.add_status(message)
            )
            detector.start_detection(roi_img, map_name, grid_config, roi)

            time.sleep(0.5)
        else:
            time.sleep(0.05)


def main():
    """Main entry point."""
    global overlay, tray_manager

    print("[Init] Starting Map Helper...")

    # Check for single instance
    if not acquire_single_instance_lock():
        print("[Error] Another instance of Map Helper is already running!")
        print("Please close the existing instance before starting a new one.")
        input("Press Enter to exit...")
        sys.exit(1)

    print("[Init] Single instance lock acquired")

    monitor_info = initialize_monitor_selection()

    overlay = OverlayManager()
    overlay.init(monitor_info)

    def dispatch_to_ui(func):
        if overlay and overlay.root:
            overlay.root.after(0, func)
        else:
            func()

    def tray_exit():
        request_shutdown("[Exit] Closing...")

    def tray_select_monitor():
        monitor_list = get_all_monitors()
        if len(monitor_list) <= 1:
            if overlay:
                overlay.add_status("[Monitor] Only one monitor detected")
            return

        def _select():
            selection = show_monitor_selection()
            if selection and apply_monitor_selection(selection, monitor_list, notify=False):
                if overlay:
                    overlay.add_status(f"[Monitor] Switched to monitor {selection}")
            elif selection is None and overlay:
                overlay.add_status("[Monitor] Selection cancelled")

        with block_user_input():
            if overlay:
                overlay.clear_popup_layers()
            _select()
            if overlay:
                overlay.clear_popup_layers()

    def tray_select_roi():
        stop_current_detection(hide_overlay=True)
        matcher.reset_session()
        roi = ensure_roi(force=True)
        if roi is None and overlay:
            overlay.add_status("[ROI] No changes made")

    def tray_open_settings():
        with block_user_input():
            if overlay:
                overlay.clear_popup_layers()
            show_settings_dialog(overlay.root, app_settings)
            if overlay:
                overlay.clear_popup_layers()

    try:
        tray_manager = SystemTrayManager(
            ui_dispatch=dispatch_to_ui,
            on_exit=tray_exit,
            on_select_monitor=tray_select_monitor,
            on_select_roi=tray_select_roi,
            on_open_settings=tray_open_settings,
        )
        tray_manager.start()
        overlay.add_status("[Tray] System tray active")
    except RuntimeError as err:
        tray_manager = None
        print(f"[Tray] {err}")

    kb_thread = threading.Thread(target=keyboard_handler, daemon=True)
    kb_thread.start()

    try:
        overlay.run()
    except KeyboardInterrupt:
        request_shutdown()
    finally:
        if not shutdown_event.is_set():
            request_shutdown()
        release_single_instance_lock()
        print("\n[Exit] Shutting down...")


if __name__ == "__main__":
    main()
