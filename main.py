"""Map Helper - Main Entry Point"""
import time
import threading
import keyboard
import os

# Import modules
from utils.config import Config
from utils.capture import capture_screen, screen_resolution_key
from utils.settings import get_settings
from utils.resource_path import resource_path
from ui.overlay_manager import OverlayManager
from ui.dialogs import show_main_menu, show_settings_dialog, show_map_confirmation, show_title_overlay
from core.detection import RealtimeDetector
import matcher

# Constants - use resource_path for PyInstaller compatibility
MAPS_ROOT = resource_path("maps")

# Global state
app_settings = get_settings()
overlay = None
detector = None
map_showing = False
current_roi = None


def get_available_maps():
    """Get list of available maps."""
    if not os.path.isdir(MAPS_ROOT):
        return []
    return [name for name in sorted(os.listdir(MAPS_ROOT))
            if os.path.isdir(os.path.join(MAPS_ROOT, name))]


def ensure_roi(cfg):
    """Ensure ROI exists."""
    res_key, _ = screen_resolution_key()
    roi = cfg.get_roi(res_key)
    if roi:
        return roi

    # Capture screen for ROI selection
    frame = capture_screen()

    # Show ROI selector on overlay
    overlay.root.deiconify()
    roi = overlay.show_roi_selector(frame)

    if roi:
        cfg.set_roi(res_key, roi)
        cfg.save()
        overlay.add_status(f"[Init] ROI saved")
        time.sleep(1.0)

    # Hide overlay again until user presses M
    overlay.root.withdraw()
    overlay.is_visible = False

    return roi


def crop_roi(frame, roi):
    """Crop ROI from frame."""
    x, y, w, h = roi
    H, W = frame.shape[:2]
    x = max(0, min(W-1, x))
    y = max(0, min(H-1, y))
    w = max(1, min(W-x, w))
    h = max(1, min(H-y, h))
    return frame[y:y+h, x:x+w]


def keyboard_handler():
    """Handle keyboard input."""
    global map_showing, current_roi, detector

    cfg = Config("config.json")
    last_esc_press = 0  # Track last ESC press time
    title_canvas = None  # Track title canvas for cleanup

    overlay.add_status("=== Map Helper Ready ===")
    overlay.add_status("Press M - Toggle map")
    overlay.add_status("Press R - Reset | ESC x2 - Exit")

    while True:
        if keyboard.is_pressed("esc"):
            current_time = time.time()
            time_since_last_esc = current_time - last_esc_press

            if time_since_last_esc < 1.0:  # Within 1 second
                # Second ESC press - exit
                overlay.add_status("[Exit] Closing...")
                if detector:
                    detector.stop_detection()
                overlay.stop()
                break
            else:
                # First ESC press
                last_esc_press = current_time
                overlay.add_status("[ESC] Press again to exit")
                time.sleep(0.5)
                continue

        if keyboard.is_pressed("r"):
            matcher.reset_session()
            if detector:
                detector.stop_detection()
            map_showing = False
            current_roi = None
            overlay.hide_grid()
            overlay.add_status("[Reset] Cache cleared")
            time.sleep(0.5)
            continue

        if keyboard.is_pressed("m"):
            overlay.add_status("[Input] M pressed")

            # Check cache expiration
            if matcher.is_cache_expired():
                overlay.add_status("[Cache] Expired - will re-identify")
                matcher.reset_session()
                map_showing = False
                current_roi = None

            # If showing, hide
            if map_showing:
                overlay.hide_grid()
                map_showing = False
                # Clean up title canvas if it exists
                if title_canvas:
                    try:
                        title_canvas.destroy()
                    except:
                        pass
                    title_canvas = None
                overlay.add_status("[Overlay] Hidden")
                time.sleep(0.5)
                continue

            # If cached results exist, show them
            if current_roi and matcher._identified_map:
                map_folder = f"{MAPS_ROOT}/{matcher._identified_map}"
                grid_config = matcher.load_grid_config(map_folder)
                if grid_config is None:
                    grid_config = (5, 5)
                language = app_settings.get("language", "en")
                location_names = matcher.load_location_names(map_folder, language)

                # Show title overlay
                title_canvas = show_title_overlay(overlay.root, current_roi)

                overlay.show_grid(current_roi, grid_config, matcher._identified_cells, location_names)
                map_showing = True
                overlay.add_status(f"[Overlay] Showing {matcher._identified_map}")
                time.sleep(0.5)
                continue

            # New detection needed
            roi = ensure_roi(cfg)
            if not roi:
                time.sleep(0.5)
                continue

            frame = capture_screen()
            roi_img = crop_roi(frame, roi)
            current_roi = roi

            # Show menu if no cache
            if matcher._identified_map is None:
                available_maps = get_available_maps()
                if not available_maps:
                    overlay.add_status("[Error] No maps found")
                    time.sleep(1.0)
                    continue

                # Menu loop - handle settings returning to menu
                while True:
                    choice, title_canvas = show_main_menu(overlay.root, available_maps, roi)

                    if choice == "CANCEL":
                        # Clean up title canvas
                        if title_canvas:
                            try:
                                title_canvas.destroy()
                            except:
                                pass
                            title_canvas = None
                        overlay.add_status("[Cancelled]")
                        time.sleep(0.5)
                        continue  # Continue outer M-key loop
                    elif choice == "SETTINGS":
                        result = show_settings_dialog(overlay.root, app_settings)
                        if result == 'BACK':
                            continue  # Continue menu loop
                        else:
                            # Settings closed, cancel operation
                            overlay.add_status("[Cancelled]")
                            time.sleep(0.5)
                            break  # Exit menu loop
                    elif choice is None:
                        # Auto-detect - use FIRST CELL ONLY for speed!
                        matcher.reset_session()
                        overlay.add_status("[Auto-Detect] Checking first cell...")

                        # Check first cell only (fast!)
                        candidates = matcher.identify_map_from_first_cell(roi_img, MAPS_ROOT)

                        if not candidates or not candidates[0]:
                            overlay.add_status(f"[Unknown] No match")
                            time.sleep(1.0)
                            continue  # Continue outer M-key loop

                        # Get top candidate
                        detected_map, confidence, detected_grid, _ = candidates[0]
                        overlay.add_status(f"[Found] {detected_map} ({confidence}% confidence)")

                        # Show confirmation dialog
                        confirmation = show_map_confirmation(overlay.root, detected_map)

                        if confirmation == "YES":
                            map_name = detected_map
                            grid_config = detected_grid
                            # Clear cells so full detection will run
                            matcher._identified_cells = {}
                            matcher._identified_map = map_name
                            matcher._cache_timestamp = time.time()
                            overlay.add_status(f"[Confirmed] {map_name}")
                            break  # Exit menu loop
                        elif confirmation == "NO":
                            overlay.add_status("[Rejected] Try again")
                            matcher.reset_session()  # Clear cache
                            continue  # Continue menu loop - show menu again
                        elif confirmation == "CHOOSE":
                            matcher.reset_session()  # Clear wrong cache before manual selection
                            continue  # Continue menu loop - show menu to choose manually
                        else:
                            # Cancelled
                            overlay.add_status("[Cancelled]")
                            time.sleep(0.5)
                            continue  # Continue outer M-key loop
                    else:
                        # User selected map
                        map_name = choice
                        grid_config = matcher.load_grid_config(f"{MAPS_ROOT}/{map_name}")
                        if grid_config is None:
                            grid_config = (5, 5)
                        # Clear any previous cell cache to avoid using wrong map's cells
                        matcher._identified_cells = {}
                        matcher._identified_map = map_name
                        matcher._cache_timestamp = time.time()
                        overlay.add_status(f"[Selected] {map_name}")
                        break  # Exit menu loop

                # If we broke due to cancel/close, skip detection
                if choice == "CANCEL" or (choice == "SETTINGS" and result != 'BACK'):
                    continue
            else:
                # Use cached map
                map_name = matcher._identified_map
                grid_config = matcher.load_grid_config(f"{MAPS_ROOT}/{map_name}")
                if grid_config is None:
                    grid_config = (5, 5)

            # Start real-time detection
            map_showing = True
            map_folder = f"{MAPS_ROOT}/{map_name}"
            language = app_settings.get("language", "en")
            location_names = matcher.load_location_names(map_folder, language)
            overlay.show_grid(roi, grid_config, {}, location_names)  # Show empty grid first

            detector = RealtimeDetector(
                overlay_callback=lambda r, g, c: overlay.show_grid(r, g, c, location_names),
                status_callback=lambda m: overlay.add_status(m)
            )
            detector.start_detection(roi_img, map_name, grid_config, roi)

            time.sleep(0.5)
        else:
            time.sleep(0.05)


def main():
    """Main entry point."""
    global overlay

    print("[Init] Starting Map Helper...")

    # Initialize overlay
    overlay = OverlayManager()
    overlay.init()

    # Start keyboard handler
    kb_thread = threading.Thread(target=keyboard_handler, daemon=True)
    kb_thread.start()

    # Run overlay main loop
    try:
        overlay.run()
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[Exit] Shutting down...")


if __name__ == "__main__":
    main()
