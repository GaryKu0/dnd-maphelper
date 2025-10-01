"""Centralized hotkey management using event-driven approach."""
import keyboard
import threading


class HotkeyManager:
    """Manages application-wide hotkeys with blocking/unblocking support."""

    def __init__(self):
        self.hotkeys = {}  # {name: hotkey_id}
        self.callbacks = {}  # {name: callback}
        self.blocked = threading.Event()  # When set, hotkeys are blocked
        self.lock = threading.Lock()

    def register(self, name, key, callback, suppress=False):
        """Register a hotkey with a callback.

        Args:
            name: Unique identifier for this hotkey
            key: Key combination (e.g., 'm', 'ctrl+s')
            callback: Function to call when hotkey is pressed
            suppress: Whether to suppress the key from reaching other apps
        """
        with self.lock:
            # Unregister if already exists
            if name in self.hotkeys:
                self.unregister(name)

            # Wrapper to check if blocked
            def wrapped_callback():
                if not self.blocked.is_set():
                    try:
                        callback()
                    except Exception as e:
                        print(f"[HotkeyManager] Error in {name} callback: {e}")

            # Register with keyboard library
            try:
                hotkey_id = keyboard.add_hotkey(key, wrapped_callback, suppress=suppress)
                self.hotkeys[name] = hotkey_id
                self.callbacks[name] = callback
            except Exception as e:
                print(f"[HotkeyManager] Failed to register {name}: {e}")

    def unregister(self, name):
        """Unregister a hotkey."""
        with self.lock:
            if name in self.hotkeys:
                try:
                    keyboard.remove_hotkey(self.hotkeys[name])
                except:
                    pass
                del self.hotkeys[name]
                del self.callbacks[name]

    def unregister_all(self):
        """Unregister all hotkeys."""
        with self.lock:
            for name in list(self.hotkeys.keys()):
                self.unregister(name)

    def block(self):
        """Block all hotkeys from firing."""
        self.blocked.set()

    def unblock(self):
        """Unblock hotkeys."""
        self.blocked.clear()

    def is_blocked(self):
        """Check if hotkeys are currently blocked."""
        return self.blocked.is_set()


# Global instance
_hotkey_manager = None


def get_hotkey_manager():
    """Get the global hotkey manager instance."""
    global _hotkey_manager
    if _hotkey_manager is None:
        _hotkey_manager = HotkeyManager()
    return _hotkey_manager
