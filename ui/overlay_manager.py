"""Overlay manager - handles all overlay display."""
import tkinter as tk
from collections import deque
import time
import os
import sys

# Font loading for Windows
if sys.platform == 'win32':
    from ctypes import windll, byref, create_unicode_buffer, create_string_buffer
    FR_PRIVATE = 0x10
    FR_NOT_ENUM = 0x20

    def loadfont(fontpath, private=True, enumerable=False):
        """Load custom font on Windows."""
        if isinstance(fontpath, bytes):
            pathbuf = create_string_buffer(fontpath)
            AddFontResourceEx = windll.gdi32.AddFontResourceExA
        elif isinstance(fontpath, str):
            pathbuf = create_unicode_buffer(fontpath)
            AddFontResourceEx = windll.gdi32.AddFontResourceExW
        else:
            raise TypeError('fontpath must be of type str or bytes')

        flags = (FR_PRIVATE if private else 0) | (FR_NOT_ENUM if not enumerable else 0)
        numFontsAdded = AddFontResourceEx(byref(pathbuf), flags, 0)
        return bool(numFontsAdded)
else:
    def loadfont(fontpath, private=True, enumerable=False):
        """Dummy font loader for non-Windows platforms."""
        return False


class OverlayManager:
    """Manages overlay display with status messages and grid."""

    def __init__(self):
        self.root = None
        self.status_messages = deque(maxlen=3)
        self.message_labels = []
        self.grid_canvas = None
        self.help_canvas = None
        self.custom_font = "Arial"  # Default font
        self.is_visible = False  # Track if overlay is currently shown
        self.monitor_info = None
        self.screen_width = None
        self.screen_height = None
        self._load_custom_fonts()

    def _load_custom_fonts(self):
        """Load custom fonts if available."""
        from utils.resource_path import resource_path
        fonts_dir = resource_path("fonts")
        print(f"[Font] Looking for fonts in: {fonts_dir}")
        
        if os.path.isdir(fonts_dir):
            print(f"[Font] Fonts directory exists, contents: {os.listdir(fonts_dir)}")
            for font_file in os.listdir(fonts_dir):
                if font_file.lower().endswith(('.ttf', '.otf')):
                    font_path = os.path.join(fonts_dir, font_file)
                    print(f"[Font] Attempting to load font: {font_path}")
                    if loadfont(font_path):
                        # Get the actual font family name that was registered
                        import tkinter as tk
                        from tkinter import font
                        root = tk.Tk()
                        root.withdraw()  # Hide the window
                        families = font.families()
                        root.destroy()
                        
                        # Find the font family that was just loaded
                        font_name = None
                        for family in families:
                            if 'Solmoe' in family and 'Kim' in family:
                                font_name = family
                                break
                        
                        if font_name:
                            self.custom_font = font_name
                            print(f"[Font] Successfully loaded custom font: {font_name}")
                            return
                        else:
                            self.custom_font = os.path.splitext(font_file)[0]
                            print(f"[Font] Font loaded but family name not found, using filename: {self.custom_font}")
                            return
                    else:
                        print(f"[Font] Failed to load font: {font_path}")
        else:
            print(f"[Font] Fonts directory does not exist: {fonts_dir}")
        
        # Fallback to a better default font
        self.custom_font = "Segoe UI"
        print(f"[Font] Using fallback font: {self.custom_font}")

    def init(self, monitor_info=None):
        """Initialize Tkinter window."""
        self.root = tk.Tk()
        self.monitor_info = monitor_info
        self.root.withdraw()
        self.root.attributes('-alpha', 1.0)
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)
        self.root.attributes('-transparentcolor', 'black')

        self._apply_monitor_geometry()
        self.root.configure(bg='black')

        # Status frame (top-left)
        self.status_frame = tk.Frame(self.root, bg='black')
        self.status_frame.place(x=10, y=10)

        # Create message labels
        for i in range(3):
            label = tk.Label(
                self.status_frame, text="", font=(self.custom_font, 12),
                fg="white", bg="black", anchor="w", justify="left"
            )
            label.pack(anchor="w", pady=2)
            self.message_labels.append(label)

        # Help frame (bottom-left) - using canvas for background
        self.help_canvas = tk.Canvas(
            self.root, width=180, height=70,
            bg='black', highlightthickness=0
        )
        self.help_canvas.place(x=10, y=self.screen_height - 80)

        # Background for help text
        self.help_canvas.create_rectangle(
            0, 0, 180, 70,
            fill="#2a2a2a", outline=""
        )

        help_texts = [
            "[M] Toggle Display",
            "[R] Reset Cache",
            "[ESC x2] Exit"
        ]
        y_offset = 15
        for text in help_texts:
            self.help_canvas.create_text(
                10, y_offset, text=text, font=(self.custom_font, 10),
                fill="#888888", anchor="w"
            )
            y_offset += 20

        # Close button (top-right)
        self.close_button = tk.Button(
            self.root,
            text="✕",
            font=(self.custom_font, 14, "bold"),
            fg="#FF6B6B",
            bg="#2a2a2a",
            activebackground="#FF6B6B",
            activeforeground="white",
            relief="flat",
            bd=0,
            width=3,
            height=1,
            cursor="hand2",
            command=self._on_close_button_click
        )
        self.close_button.place(x=self.screen_width - 40, y=10)

        # Start update loop
        self._update_messages()

    def _apply_monitor_geometry(self):
        """Apply current monitor geometry to the root window."""
        if not self.root:
            return

        if self.monitor_info:
            width = self.monitor_info.get('width', self.root.winfo_screenwidth())
            height = self.monitor_info.get('height', self.root.winfo_screenheight())
            left = self.monitor_info.get('left', 0)
            top = self.monitor_info.get('top', 0)
        else:
            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight()
            left = 0
            top = 0

        self.screen_width = width
        self.screen_height = height
        self.root.geometry(f"{width}x{height}+{left}+{top}")

    def update_monitor(self, monitor_info):
        """Update overlay to display on a different monitor."""
        self.monitor_info = monitor_info
        self._apply_monitor_geometry()
        if self.help_canvas:
            self.help_canvas.place_configure(y=self.screen_height - 80)
        # Hide any existing grid to avoid misplacement
        self._hide_grid_impl()

    def add_status(self, message):
        """Add a status message."""
        if self.root:
            self.root.after(0, self._add_status_impl, message)

    def _add_status_impl(self, message):
        """Internal: add status."""
        self.status_messages.append({'text': message, 'time': time.time()})
        self._update_message_display()

    def _update_messages(self):
        """Update loop to remove old messages."""
        if not self.root:
            return

        # Only update if overlay is visible
        if self.is_visible:
            current_time = time.time()
            # Remove messages older than 5 seconds
            while self.status_messages and (current_time - self.status_messages[0]['time']) > 5.0:
                self.status_messages.popleft()

            self._update_message_display()

        self.root.after(100, self._update_messages)

    def _update_message_display(self):
        """Update message labels."""
        messages_list = list(self.status_messages)
        for i, label in enumerate(self.message_labels):
            if i < len(messages_list):
                label.config(text=messages_list[i]['text'])
            else:
                label.config(text="")

    def clear_popup_layers(self):
        """Destroy temporary popup canvases such as menus or dialogs."""
        if not self.root:
            return
        for widget in list(self.root.winfo_children()):
            if isinstance(widget, tk.Canvas) and getattr(widget, "_maphelper_popup", False):
                widget.destroy()

    def show_grid(self, roi_rect, grid_config, cell_locations, location_names=None):
        """Show grid overlay.

        Args:
            roi_rect: (x, y, w, h) of ROI
            grid_config: (rows, cols)
            cell_locations: {cell_idx: (location_name, rotation)}
            location_names: Optional dict mapping location_name -> display_name
        """
        if not self.root:
            return
        self.root.after(0, self._show_grid_impl, roi_rect, grid_config, cell_locations, location_names)

    def _show_grid_impl(self, roi_rect, grid_config, cell_locations, location_names=None):
        """Internal: show grid."""
        # Clear existing
        if self.grid_canvas:
            self.grid_canvas.destroy()

        x, y, w, h = roi_rect
        rows, cols = grid_config

        # Create canvas
        self.grid_canvas = tk.Canvas(
            self.root, width=w, height=h,
            bg='black', highlightthickness=0
        )
        self.grid_canvas.place(x=x, y=y)

        cell_w, cell_h = w // cols, h // rows

        # Draw grid lines
        for r in range(1, rows):
            self.grid_canvas.create_line(0, r * cell_h, w, r * cell_h, fill="#d0cbc8", width=2)
        for c in range(1, cols):
            self.grid_canvas.create_line(c * cell_w, 0, c * cell_w, h, fill="#d0cbc8", width=2)

        # Draw location names
        for cell_idx, location_data in cell_locations.items():
            if isinstance(location_data, tuple):
                location_name, rotation = location_data
            else:
                location_name, rotation = location_data, 0

            row, col = cell_idx // cols, cell_idx % cols
            center_x = col * cell_w + cell_w // 2
            center_y = row * cell_h + cell_h // 2

            # Use translated name if available
            if location_names and location_name in location_names:
                display_name = location_names[location_name]
            else:
                display_name = location_name.replace('_', ' ')

            # Create text first
            text_id = self.grid_canvas.create_text(
                center_x, center_y, text=display_name,
                fill="#f1f211", font=(self.custom_font, 9), justify="center"
            )

            # Get text bounding box
            bbox = self.grid_canvas.bbox(text_id)

            if bbox:
                # Add padding
                padding = 4
                # Draw background rectangle behind text (dark gray, not black which is transparent)
                bg_rect = self.grid_canvas.create_rectangle(
                    bbox[0] - padding, bbox[1] - padding,
                    bbox[2] + padding, bbox[3] + padding,
                    fill="#2a2a2a", outline=""
                )
                # Move background behind text
                self.grid_canvas.tag_lower(bg_rect, text_id)

        self.is_visible = True
        self.root.deiconify()

    def hide_grid(self):
        """Hide grid overlay."""
        if not self.root:
            return
        self.root.after(0, self._hide_grid_impl)

    def _hide_grid_impl(self):
        """Internal: hide grid."""
        if self.grid_canvas:
            self.grid_canvas.destroy()
            self.grid_canvas = None
        self.is_visible = False
        self.root.withdraw()

    def run(self):
        """Run main loop."""
        if self.root:
            self.root.mainloop()

    def show_roi_selector(self, screenshot):
        """Show ROI selector on overlay. Returns (x, y, w, h) or None."""
        if not self.root:
            return None

        import cv2
        from PIL import Image, ImageTk

        result = {'roi': None}
        selecting = {'flag': False}
        start_pos = {'x': 0, 'y': 0}
        current_rect = {'id': None}

        # Get screen size
        screen_width = self.screen_width or self.root.winfo_screenwidth()
        screen_height = self.screen_height or self.root.winfo_screenheight()

        # Create fullscreen canvas
        selector_canvas = tk.Canvas(
            self.root, width=screen_width, height=screen_height,
            bg='black', highlightthickness=0, cursor='cross'
        )
        selector_canvas.place(x=0, y=0)

        # Convert screenshot to PIL Image and then to PhotoImage
        screenshot_rgb = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(screenshot_rgb)
        # Resize if needed to fit screen
        if pil_image.size != (screen_width, screen_height):
            pil_image = pil_image.resize((screen_width, screen_height), Image.LANCZOS)
        photo = ImageTk.PhotoImage(pil_image)

        # Display screenshot
        selector_canvas.create_image(0, 0, image=photo, anchor='nw')

        # Instructions overlay
        instruction_bg = selector_canvas.create_rectangle(
            screen_width // 2 - 200, 20, screen_width // 2 + 200, 80,
            fill="#2a2a2a", outline="#d0cbc8", width=2
        )
        instruction_text = selector_canvas.create_text(
            screen_width // 2, 50,
            text="Drag to select map area\nPress ENTER to confirm | ESC to cancel",
            fill="white", font=(self.custom_font, 12), justify="center"
        )

        def on_mouse_down(event):
            selecting['flag'] = True
            start_pos['x'] = event.x
            start_pos['y'] = event.y

        def on_mouse_move(event):
            if not selecting['flag']:
                return

            # Delete previous rectangle
            if current_rect['id']:
                selector_canvas.delete(current_rect['id'])

            # Draw new rectangle
            x1, y1 = start_pos['x'], start_pos['y']
            x2, y2 = event.x, event.y

            current_rect['id'] = selector_canvas.create_rectangle(
                x1, y1, x2, y2,
                outline='#00ff00', width=3
            )

        def on_mouse_up(event):
            selecting['flag'] = False

        def on_key(event):
            if event.keysym == 'Return':  # Enter key
                if current_rect['id']:
                    # Get rectangle coordinates
                    coords = selector_canvas.coords(current_rect['id'])
                    if coords:
                        x1, y1, x2, y2 = coords
                        x = int(min(x1, x2))
                        y = int(min(y1, y2))
                        w = int(abs(x2 - x1))
                        h = int(abs(y2 - y1))
                        if w > 10 and h > 10:  # Minimum size
                            result['roi'] = (x, y, w, h)
                selector_canvas.destroy()
            elif event.keysym == 'Escape':
                selector_canvas.destroy()

        selector_canvas.bind('<ButtonPress-1>', on_mouse_down)
        selector_canvas.bind('<B1-Motion>', on_mouse_move)
        selector_canvas.bind('<ButtonRelease-1>', on_mouse_up)
        selector_canvas.bind('<Key>', on_key)
        selector_canvas.focus_set()

        # Wait for selection
        self.root.wait_window(selector_canvas)

        return result['roi']

    def _on_close_button_click(self):
        """Handle close button click."""
        # Import here to avoid circular imports
        from main import request_shutdown
        request_shutdown("[Exit] Close button clicked")

    def stop(self):
        """Stop overlay."""
        if self.root:
            self.root.quit()
