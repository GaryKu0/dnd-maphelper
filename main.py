"""Map Helper - Main Entry Point"""
import os
import sys
import time
import threading
import atexit
from contextlib import contextmanager

from utils.config import Config
from utils.capture import capture_screen, screen_resolution_key, get_all_monitors, set_monitor
from utils.settings import get_settings
from utils.resource_path import resource_path, is_executable
from utils.hotkey_manager import get_hotkey_manager
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
    
    # Use a more appropriate location for lock files
    if is_executable():
        # For executables, use temp directory
        import tempfile
        lock_path = os.path.join(tempfile.gettempdir(), "maphelper.lock")
    else:
        # For development, use current directory
        lock_path = LOCK_FILE
    
    try:
        # Try to create/open the lock file exclusively
        if os.name == 'nt':  # Windows
            import msvcrt
            lock_file_handle = open(lock_path, 'w')
            msvcrt.locking(lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:  # Unix-like systems
            import fcntl
            lock_file_handle = open(lock_path, 'w')
            fcntl.flock(lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        # Write PID to lock file
        lock_file_handle.write(str(os.getpid()))
        lock_file_handle.flush()
        
        # Store the lock path for cleanup
        lock_file_handle.lock_path = lock_path
        
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
        lock_path = getattr(lock_file_handle, 'lock_path', LOCK_FILE)
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
            if os.path.exists(lock_path):
                os.remove(lock_path)
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
    hotkey_mgr = get_hotkey_manager()
    input_block_event.set()
    hotkey_mgr.block()
    try:
        yield
    finally:
        time.sleep(0.1)
        hotkey_mgr.unblock()
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

    # Add delay to allow game map to render properly before screenshot
    if overlay:
        overlay.add_status("[ROI] Preparing screen capture in 0.3 seconds...")
    time.sleep(0.3)
    
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

    # Check config file for stored monitor index
    with config_lock:
        stored_index = config_store.get_monitor_index()

    # If no stored index or invalid, use first available monitor
    if stored_index is None or not any(mon['index'] == stored_index for mon in monitors):
        stored_index = monitors[0]['index']

    selected_index = stored_index

    # Only show monitor selection dialog if:
    # 1. Multiple monitors are available AND
    # 2. No monitor is configured yet
    if len(monitors) > 1 and not config_store.has_monitor_index():
        selection = show_monitor_selection()
        if selection:
            selected_index = selection
        # Save the selection (whether from dialog or default)
        with config_lock:
            config_store.set_monitor_index(selected_index)
            config_store.save()
    elif not config_store.has_monitor_index():
        # Single monitor case - save the default
        with config_lock:
            config_store.set_monitor_index(selected_index)
            config_store.save()

    set_monitor(selected_index)
    current_monitor_info = get_monitor_info(selected_index, monitors)
    return current_monitor_info


def apply_monitor_selection(monitor_index, monitors=None, notify=True):
    """Apply a monitor selection while the app is running."""
    global current_monitor_info, current_roi

    monitors = monitors or get_all_monitors()
    info = get_monitor_info(monitor_index, monitors)
    if not info:
        return False

    # Save monitor selection to config
    with config_lock:
        config_store.set_monitor_index(monitor_index)
        config_store.save()

    set_monitor(monitor_index)

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
    """Handle keyboard shortcuts using event-driven hotkeys."""
    global map_showing, current_roi, detector

    hotkey_mgr = get_hotkey_manager()
    last_esc_press = {'time': 0}
    title_canvas = {'ref': None}

    overlay.add_status("=== Map Helper Ready ===")
    overlay.add_status("Press M - Toggle map")
    overlay.add_status("Press R - Reset | ESC x2 - Exit")

    def handle_esc():
        if input_block_event.is_set():
            return
        current_time = time.time()
        if current_time - last_esc_press['time'] < 1.0:
            request_shutdown("[Exit] Closing...")
        else:
            last_esc_press['time'] = current_time
            overlay.add_status("[ESC] Press again to exit")

    def handle_reset():
        if input_block_event.is_set():
            return

        global current_roi, map_showing

        # Hide current map display
        if map_showing:
            overlay.hide_grid()
            if title_canvas['ref']:
                try:
                    title_canvas['ref'].destroy()
                except Exception:
                    pass
                title_canvas['ref'] = None

        overlay.clear_popup_layers()
        stop_current_detection(hide_overlay=True)
        matcher.reset_session()
        map_showing = False

        overlay.add_status("[Reset] Cache cleared - select map")

        # Get ROI if needed
        roi = ensure_roi()
        if not roi:
            current_roi = None
            return

        frame = capture_screen()
        roi_img = crop_roi(frame, roi)
        current_roi = roi

        # Show map selection menu
        available_maps = get_available_maps()
        if not available_maps:
            overlay.add_status("[Error] No maps found")
            return

        while True:
            menu_debug = "[Debug] About to show main menu..."
            print(menu_debug)
            overlay.add_status(menu_debug)
            
            maps_debug = f"[Debug] Available maps: {len(available_maps)}"
            print(maps_debug)
            overlay.add_status(maps_debug)
            
            roi_debug = f"[Debug] ROI: {roi}"
            print(roi_debug)
            overlay.add_status(roi_debug)
            
            choice, title_canvas['ref'] = show_main_menu(overlay.root, available_maps, roi)
            
            choice_debug = f"[Debug] Menu returned: {choice}"
            print(choice_debug)
            overlay.add_status(choice_debug)

            if choice == "CANCEL":
                if title_canvas['ref']:
                    try:
                        title_canvas['ref'].destroy()
                    except Exception:
                        pass
                    title_canvas['ref'] = None
                overlay.clear_popup_layers()
                overlay.hide_grid()  # Hide the overlay completely
                map_showing = False  # Reset map showing state
                overlay.add_status("[Cancelled]")
                print("[Debug] Menu cancelled - overlay hidden")
                print(f"[Debug] Overlay visible after hide: {overlay.is_visible}")
                print(f"[Debug] Map showing reset to: {map_showing}")
                return
            if choice == "SETTINGS":
                with block_user_input():
                    result = show_settings_dialog(overlay.root, app_settings)
                overlay.clear_popup_layers()
                if result == 'BACK':
                    continue
                if title_canvas['ref']:
                    try:
                        title_canvas['ref'].destroy()
                    except Exception:
                        pass
                    title_canvas['ref'] = None
                overlay.clear_popup_layers()
                overlay.hide_grid()  # Hide the overlay completely
                map_showing = False  # Reset map showing state
                overlay.add_status("[Cancelled]")
                print("[Debug] Settings cancelled - overlay hidden")
                print(f"[Debug] Overlay visible after hide: {overlay.is_visible}")
                print(f"[Debug] Map showing reset to: {map_showing}")
                return
            if choice is None:
                # Auto-detect
                matcher.reset_session()
                overlay.add_status("[Auto-Detect] Checking first cell...")
                candidates = matcher.identify_map_from_first_cell(roi_img, MAPS_ROOT)

                if not candidates or not candidates[0]:
                    overlay.add_status("[Unknown] No match")
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
                # Cancelled
                if title_canvas['ref']:
                    try:
                        title_canvas['ref'].destroy()
                    except Exception:
                        pass
                    title_canvas['ref'] = None
                overlay.clear_popup_layers()
                overlay.hide_grid()  # Hide the overlay completely
                map_showing = False  # Reset map showing state
                overlay.add_status("[Cancelled]")
                print("[Debug] Settings cancelled - overlay hidden")
                print(f"[Debug] Overlay visible after hide: {overlay.is_visible}")
                print(f"[Debug] Map showing reset to: {map_showing}")
                return
            else:
                # Manual selection
                map_name = choice
                grid_config = matcher.load_grid_config(f"{MAPS_ROOT}/{map_name}") or (5, 5)
                matcher._identified_cells = {}
                matcher._identified_map = map_name
                matcher._cache_timestamp = time.time()
                overlay.add_status(f"[Selected] {map_name}")
                break

        # Show the map and start detection
        if matcher._identified_map:
            if title_canvas['ref']:
                try:
                    title_canvas['ref'].destroy()
                except Exception:
                    pass
            overlay.clear_popup_layers()

            title_canvas['ref'] = show_title_overlay(overlay.root, roi)
            map_showing = True
            map_folder = f"{MAPS_ROOT}/{matcher._identified_map}"
            language = app_settings.get("language", "en")
            location_names = matcher.load_location_names(map_folder, language)
            overlay.show_grid(roi, grid_config, {}, location_names)

            detector = RealtimeDetector(
                overlay_callback=lambda r, g, c: overlay.show_grid(r, g, c, location_names) if map_showing else None,
                status_callback=lambda message: overlay.add_status(message)
            )
            detector.start_detection(roi_img, matcher._identified_map, grid_config, roi)

    def handle_m():
        global map_showing, current_roi, detector
        if input_block_event.is_set():
            print("[Input] M pressed (blocked)")
            overlay.add_status("[Input] M pressed (blocked)")
            return

        print("[Input] M pressed")
        overlay.add_status("[Input] M pressed")
        
        # Debug information - both overlay and console
        debug_info = [
            f"[Debug] Map showing: {map_showing}",
            f"[Debug] Current ROI: {bool(current_roi)}",
            f"[Debug] Identified map: {matcher._identified_map}",
            f"[Debug] Input blocked: {input_block_event.is_set()}",
            f"[Debug] Hotkey blocked: {get_hotkey_manager().is_blocked()}",
            f"[Debug] Overlay root exists: {overlay and overlay.root is not None}",
            f"[Debug] Overlay visible: {overlay and overlay.is_visible}"
        ]
        
        for info in debug_info:
            overlay.add_status(info)
            print(info)  # Also print to console

        if matcher.is_cache_expired():
            overlay.add_status("[Cache] Expired - will re-identify")
            matcher.reset_session()
            map_showing = False
            current_roi = None

        if map_showing:
            overlay.hide_grid()
            map_showing = False
            # Don't stop detector - let it continue in background
            if title_canvas['ref']:
                try:
                    title_canvas['ref'].destroy()
                except Exception:
                    pass
                title_canvas['ref'] = None
            overlay.clear_popup_layers()  # Clear any remaining popups
            overlay.add_status("[Overlay] Hidden (detection continues)")
            return

        if current_roi and matcher._identified_map:
            map_folder = f"{MAPS_ROOT}/{matcher._identified_map}"
            grid_config = matcher.load_grid_config(map_folder) or (5, 5)
            language = app_settings.get("language", "en")
            location_names = matcher.load_location_names(map_folder, language)

            overlay.clear_popup_layers()  # Clear any leftover popups
            title_canvas['ref'] = show_title_overlay(overlay.root, current_roi)

            # Show current detection results (including partial if still detecting)
            current_cells = detector.current_results.copy() if detector and detector.is_running else matcher._identified_cells
            overlay.show_grid(current_roi, grid_config, current_cells, location_names)
            map_showing = True

            # Start detector if not running
            if not detector or not detector.is_running:
                frame = capture_screen()
                roi_img = crop_roi(frame, current_roi)
                detector = RealtimeDetector(
                    overlay_callback=lambda r, g, c: overlay.show_grid(r, g, c, location_names) if map_showing else None,
                    status_callback=lambda message: overlay.add_status(message)
                )
                detector.start_detection(roi_img, matcher._identified_map, grid_config, current_roi)
                overlay.add_status(f"[Overlay] Showing {matcher._identified_map} (detecting...)")
            else:
                overlay.add_status(f"[Overlay] Showing {matcher._identified_map} (detection in progress)")
            return

        print("[Debug] Calling ensure_roi()...")
        overlay.add_status("[Debug] Calling ensure_roi()...")
        roi = ensure_roi()
        roi_debug = f"[Debug] ensure_roi() returned: {roi}"
        print(roi_debug)
        overlay.add_status(roi_debug)
        if not roi:
            print("[Debug] ROI is None - ensure_roi failed")
            overlay.add_status("[Debug] ROI is None - ensure_roi failed")
            return

        frame = capture_screen()
        roi_img = crop_roi(frame, roi)
        current_roi = roi

        if matcher._identified_map is None:
            available_maps = get_available_maps()
            if not available_maps:
                overlay.add_status("[Error] No maps found")
                return

            while True:
                menu_debug = "[Debug] About to show main menu..."
                print(menu_debug)
                overlay.add_status(menu_debug)
                
                maps_debug = f"[Debug] Available maps: {len(available_maps)}"
                print(maps_debug)
                overlay.add_status(maps_debug)
                
                roi_debug = f"[Debug] ROI: {roi}"
                print(roi_debug)
                overlay.add_status(roi_debug)
                
                choice, title_canvas['ref'] = show_main_menu(overlay.root, available_maps, roi)
                
                choice_debug = f"[Debug] Menu returned: {choice}"
                print(choice_debug)
                overlay.add_status(choice_debug)

                if choice == "CANCEL":
                    if title_canvas['ref']:
                        try:
                            title_canvas['ref'].destroy()
                        except Exception:
                            pass
                        title_canvas['ref'] = None
                    overlay.clear_popup_layers()
                    overlay.hide_grid()  # Hide the overlay completely
                    overlay.add_status("[Cancelled]")
                    print("[Debug] Menu cancelled - overlay hidden")
                    return
                if choice == "SETTINGS":
                    with block_user_input():
                        result = show_settings_dialog(overlay.root, app_settings)
                    overlay.clear_popup_layers()
                    if result == 'BACK':
                        continue
                    # User closed settings without going back - cancel entire operation
                    if title_canvas['ref']:
                        try:
                            title_canvas['ref'].destroy()
                        except Exception:
                            pass
                        title_canvas['ref'] = None
                    overlay.clear_popup_layers()
                    overlay.add_status("[Cancelled]")
                    return
                if choice is None:
                    matcher.reset_session()
                    overlay.add_status("[Auto-Detect] Checking first cell...")
                    candidates = matcher.identify_map_from_first_cell(roi_img, MAPS_ROOT)

                    if not candidates or not candidates[0]:
                        overlay.add_status("[Unknown] No match")
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
                    # Confirmation was cancelled
                    if title_canvas['ref']:
                        try:
                            title_canvas['ref'].destroy()
                        except Exception:
                            pass
                        title_canvas['ref'] = None
                    overlay.clear_popup_layers()
                    overlay.add_status("[Cancelled]")
                    return

                else:
                    map_name = choice
                    grid_config = matcher.load_grid_config(f"{MAPS_ROOT}/{map_name}") or (5, 5)
                    matcher._identified_cells = {}
                    matcher._identified_map = map_name
                    matcher._cache_timestamp = time.time()
                    overlay.add_status(f"[Selected] {map_name}")
                    break

            # If we get here without a map, something went wrong
            if matcher._identified_map is None:
                if title_canvas['ref']:
                    try:
                        title_canvas['ref'].destroy()
                    except Exception:
                        pass
                    title_canvas['ref'] = None
                overlay.clear_popup_layers()
                return
        else:
            map_name = matcher._identified_map
            grid_config = matcher.load_grid_config(f"{MAPS_ROOT}/{map_name}") or (5, 5)

        # Clean up menu title canvas and create new one for grid
        if title_canvas['ref']:
            try:
                title_canvas['ref'].destroy()
            except Exception:
                pass
        overlay.clear_popup_layers()

        # Show the grid with new title
        title_canvas['ref'] = show_title_overlay(overlay.root, roi)
        map_showing = True
        map_folder = f"{MAPS_ROOT}/{map_name}"
        language = app_settings.get("language", "en")
        location_names = matcher.load_location_names(map_folder, language)
        overlay.show_grid(roi, grid_config, {}, location_names)

        detector = RealtimeDetector(
            overlay_callback=lambda r, g, c: overlay.show_grid(r, g, c, location_names) if map_showing else None,
            status_callback=lambda message: overlay.add_status(message)
        )
        detector.start_detection(roi_img, map_name, grid_config, roi)

    def dispatch(callback):
        def wrapper():
            if overlay and overlay.root:
                overlay.root.after(0, callback)
        return wrapper

    # Register hotkeys
    hotkey_mgr.register('esc', 'esc', dispatch(handle_esc))
    hotkey_mgr.register('reset', 'r', dispatch(handle_reset))
    hotkey_mgr.register('m', 'm', dispatch(handle_m))

    # Wait for shutdown
    while not shutdown_event.is_set():
        time.sleep(0.1)

    # Cleanup
    hotkey_mgr.unregister_all()




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

    # Only enable system tray when running as script (not as executable)
    if not is_executable():
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
    else:
        tray_manager = None
        overlay.add_status("[Info] Running as executable - System tray disabled")

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
