"""Centralized hotkey management using event-driven approach."""
import keyboard
import threading
import traceback
import time


class HotkeyManager:
    """Manages application-wide hotkeys with blocking/unblocking support."""

    def __init__(self, debounce_delay=0.3):
        self.hotkeys = {}  # {name: (hotkey_id, trigger_type)}
        self.callbacks = {}  # {name: callback}
        self._is_blocked = threading.Event()  # When set, hotkeys are blocked
        self.lock = threading.Lock()
        self.debounce_delay = debounce_delay  # Default 300ms debounce
        self.last_trigger_times = {}  # {name: timestamp}

    def register(self, name, key, callback, suppress=False, trigger_on='down'):
        """Register a hotkey with a callback.

        Args:
            name: Unique identifier for this hotkey
            key: Key combination (e.g., 'm', 'ctrl+s')
            callback: Function to call when hotkey is pressed (receives event as parameter)
            suppress: Whether to suppress the key from reaching other apps
            trigger_on: 'down' (default) or 'up' to trigger on key release
        """
        with self.lock:
            # Unregister if already exists
            if name in self.hotkeys:
                self.unregister(name)

            # Wrapper to check if blocked and apply debounce
            def wrapped_callback(event=None):
                if self._is_blocked.is_set():
                    return

                # Apply debounce - prevent rapid repeated triggers
                current_time = time.time()
                last_time = self.last_trigger_times.get(name, 0)
                if current_time - last_time < self.debounce_delay:
                    return  # Silently ignore - too soon after last trigger

                self.last_trigger_times[name] = current_time

                try:
                    # Try to call with event, fallback to no args for compatibility
                    try:
                        callback(event)
                    except TypeError:
                        # Callback doesn't accept event parameter
                        callback()
                except Exception as e:
                    print(f"[HotkeyManager] Error in {name} callback: {e}")
                    traceback.print_exc()

            # Register with keyboard library
            try:
                if trigger_on == 'up':
                    # Use on_release for keyup events
                    hotkey_id = keyboard.on_release_key(key, wrapped_callback, suppress=suppress)
                    self.hotkeys[name] = (hotkey_id, 'up')
                else:
                    # Default: trigger on keydown
                    hotkey_id = keyboard.add_hotkey(key, wrapped_callback, suppress=suppress)
                    self.hotkeys[name] = (hotkey_id, 'down')
                self.callbacks[name] = callback
            except Exception as e:
                print(f"[HotkeyManager] Failed to register {name}: {e}")
                traceback.print_exc()

    def unregister(self, name):
        """Unregister a hotkey."""
        with self.lock:
            if name in self.hotkeys:
                hotkey_id, trigger_type = self.hotkeys[name]
                try:
                    if trigger_type == 'up':
                        # For on_release_key, use unhook
                        keyboard.unhook_key(hotkey_id)
                    else:
                        # For add_hotkey, use remove_hotkey
                        keyboard.remove_hotkey(hotkey_id)
                except:
                    pass
                del self.hotkeys[name]
                del self.callbacks[name]
                # Clean up debounce timestamp
                if name in self.last_trigger_times:
                    del self.last_trigger_times[name]

    def unregister_all(self):
        """Unregister all hotkeys."""
        with self.lock:
            # More efficient: collect all names first, then unregister
            names = list(self.hotkeys.keys())
        for name in names:
            self.unregister(name)

    def block(self):
        """Block all hotkeys from firing."""
        self._is_blocked.set()

    def unblock(self):
        """Unblock hotkeys."""
        self._is_blocked.clear()

    def is_blocked(self):
        """Check if hotkeys are currently blocked."""
        return self._is_blocked.is_set()


# Global instance
_hotkey_manager = None


def get_hotkey_manager():
    """Get the global hotkey manager instance."""
    global _hotkey_manager
    if _hotkey_manager is None:
        _hotkey_manager = HotkeyManager()
    return _hotkey_manager
