"""System tray integration for Map Helper."""
from __future__ import annotations

import threading
from typing import Any, Callable, Optional

from PIL import Image, ImageDraw

try:  # pragma: no cover - optional dependency resolution during linting
    import importlib

    _pystray_module = importlib.import_module("pystray")
    pystray = _pystray_module  # type: ignore[assignment]
    TrayMenu = getattr(_pystray_module, "Menu")
    TrayMenuItem = getattr(_pystray_module, "MenuItem")
except Exception:  # pragma: no cover - pystray optional
    pystray = None  # type: ignore[assignment]
    TrayMenu = None  # type: ignore[assignment]
    TrayMenuItem = None  # type: ignore[assignment]


class SystemTrayManager:
    """Manage the system tray icon and menu actions."""

    def __init__(
        self,
        ui_dispatch: Optional[Callable[[Callable[[], None]], None]],
        on_exit: Callable[[], None],
        on_select_monitor: Optional[Callable[[], None]] = None,
        on_select_roi: Optional[Callable[[], None]] = None,
        on_open_settings: Optional[Callable[[], None]] = None,
    ) -> None:
        self._ui_dispatch = ui_dispatch
        self._on_exit = on_exit
        self._on_select_monitor = on_select_monitor
        self._on_select_roi = on_select_roi
        self._on_open_settings = on_open_settings

        self._icon: Optional[Any] = None
        self._icon_thread: Optional[threading.Thread] = None
        self._icon_image = self._create_icon_image()
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the system tray icon if not already running."""
        with self._lock:
            if self._icon is not None:
                return

            if pystray is None:
                raise RuntimeError("pystray is not available. Please install dependencies from requirements.txt")

            menu_items = []
            if self._on_select_monitor:
                menu_items.append(TrayMenuItem("Select Monitor", self._wrap(self._on_select_monitor)))
            if self._on_select_roi:
                menu_items.append(TrayMenuItem("Select ROI", self._wrap(self._on_select_roi)))
            if self._on_open_settings:
                menu_items.append(TrayMenuItem("Settings", self._wrap(self._on_open_settings)))
            menu_items.append(TrayMenuItem("Exit", self._wrap(self._on_exit)))

            menu = TrayMenu(*menu_items)
            self._icon = pystray.Icon("MapHelper", self._icon_image, "Map Helper", menu)
            self._icon_thread = threading.Thread(target=self._icon.run, daemon=True)
            self._icon_thread.start()

    def stop(self) -> None:
        """Stop the system tray icon if running."""
        with self._lock:
            if self._icon is not None:
                self._icon.stop()
                self._icon = None
            self._icon_thread = None

    def is_running(self) -> bool:
        """Return True if the tray icon is currently running."""
        return self._icon is not None

    def _wrap(self, handler: Callable[[], None]) -> Callable[[Any, Any], None]:
        def callback(icon: Any, item: Any) -> None:
            self._dispatch(handler)

        return callback

    def _dispatch(self, handler: Callable[[], None]) -> None:
        if self._ui_dispatch:
            self._ui_dispatch(handler)
        else:
            handler()

    @staticmethod
    def _create_icon_image(size: int = 64) -> Image.Image:
        """Create a simple tray icon image."""
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Outer circle
        draw.ellipse((4, 4, size - 4, size - 4), outline=(0, 255, 0, 255), width=4)
        # Inner grid representation
        draw.line((size * 0.3, size * 0.3, size * 0.7, size * 0.3), fill=(0, 255, 0, 255), width=3)
        draw.line((size * 0.3, size * 0.5, size * 0.7, size * 0.5), fill=(0, 255, 0, 255), width=3)
        draw.line((size * 0.3, size * 0.7, size * 0.7, size * 0.7), fill=(0, 255, 0, 255), width=3)
        draw.line((size * 0.3, size * 0.3, size * 0.3, size * 0.7), fill=(0, 255, 0, 255), width=3)
        draw.line((size * 0.5, size * 0.3, size * 0.5, size * 0.7), fill=(0, 255, 0, 255), width=3)
        draw.line((size * 0.7, size * 0.3, size * 0.7, size * 0.7), fill=(0, 255, 0, 255), width=3)

        return image
