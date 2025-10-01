"""UI dialog components for menu and settings."""
import tkinter as tk
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


def get_custom_font():
    """Get custom font name or default to Arial."""
    fonts_dir = "./fonts"
    if os.path.isdir(fonts_dir):
        for font_file in os.listdir(fonts_dir):
            if font_file.lower().endswith(('.ttf', '.otf')):
                font_path = os.path.join(fonts_dir, font_file)
                if loadfont(font_path):
                    return os.path.splitext(font_file)[0]
    return "Arial"


CUSTOM_FONT = get_custom_font()


def show_monitor_selection():
    """Show monitor selection dialog if multiple monitors detected.
    Returns selected monitor index (1-based) or None if cancelled/error."""
    from utils.capture import get_all_monitors

    monitors = get_all_monitors()

    # If only one monitor, return it directly
    if len(monitors) == 1:
        return monitors[0]['index']

    # Create dialog window
    dialog = tk.Tk()
    dialog.title("Select Monitor")
    dialog.geometry("500x400")
    dialog.configure(bg="#1a1a1a")
    dialog.resizable(False, False)

    # Center the window
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f'{width}x{height}+{x}+{y}')

    # Selected monitor (use list to allow modification in nested function)
    selected = [None]

    # Title
    title_label = tk.Label(
        dialog,
        text="Select Monitor for Dark and Darker",
        font=(CUSTOM_FONT, 16, "bold"),
        fg="#FFD700",
        bg="#1a1a1a"
    )
    title_label.pack(pady=20)

    # Description
    desc_label = tk.Label(
        dialog,
        text="Which monitor are you playing Dark and Darker on?",
        font=(CUSTOM_FONT, 10),
        fg="#FFFFFF",
        bg="#1a1a1a"
    )
    desc_label.pack(pady=5)

    # Monitor list frame
    list_frame = tk.Frame(dialog, bg="#1a1a1a")
    list_frame.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)

    def on_select(monitor_index):
        selected[0] = monitor_index
        dialog.quit()
        dialog.destroy()

    # Create button for each monitor
    for mon in monitors:
        btn_frame = tk.Frame(list_frame, bg="#2a2a2a", relief=tk.RAISED, bd=2)
        btn_frame.pack(pady=5, fill=tk.X)

        btn = tk.Button(
            btn_frame,
            text=mon['description'],
            font=(CUSTOM_FONT, 11),
            bg="#3a3a3a",
            fg="#FFFFFF",
            activebackground="#4a4a4a",
            activeforeground="#FFD700",
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda m=mon['index']: on_select(m)
        )
        btn.pack(fill=tk.BOTH, padx=5, pady=5)

    # Footer note
    note_label = tk.Label(
        dialog,
        text="You can change this later in Settings",
        font=(CUSTOM_FONT, 8),
        fg="#888888",
        bg="#1a1a1a"
    )
    note_label.pack(pady=10)

    dialog.mainloop()

    return selected[0]


def show_title_overlay(root, roi):
    """Show just the title overlay without menu. Returns title canvas."""
    if not roi:
        return None

    roi_x, roi_y, roi_w, roi_h = roi
    title_x = roi_x + roi_w // 2
    title_y = roi_y - 100  # Higher up

    # Create title canvas (no background)
    title_canvas = tk.Canvas(
        root, width=600, height=80,
        bg='black', highlightthickness=0
    )
    title_canvas.place(x=title_x - 300, y=title_y - 40)
    setattr(title_canvas, "_maphelper_popup", True)

    # Title text - moved higher within canvas
    title_canvas.create_text(
        300, 30, text="Dark and Darker Map",
        fill="#00ff00", font=(CUSTOM_FONT, 28)
    )

    # Credit stays at same screen position (moved down within canvas to compensate)
    title_canvas.create_text(
        560, 75, text="by @garyku0",
        fill="#888888", font=(CUSTOM_FONT, 9), anchor="e"
    )

    return title_canvas


def create_rounded_rect(canvas, x1, y1, x2, y2, radius=15, **kwargs):
    """Create a rounded rectangle on canvas."""
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def show_main_menu(root, available_maps, roi=None):
    """Show main menu. Returns: None (auto-detect), map name, 'SETTINGS', or 'CANCEL'.

    Args:
        root: Tkinter root window
        available_maps: List of available map names
        roi: (x, y, w, h) of map ROI, or None to center on screen
    """
    result = {'value': None}
    waiting = {'flag': True}
    last_esc_press = {'time': 0}  # Track last ESC press time

    # Get screen dimensions
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # Calculate positions based on ROI if provided
    if roi:
        roi_x, roi_y, roi_w, roi_h = roi
        # Menu to the right side of map
        menu_width = 400
        menu_height = 500
        menu_x = roi_x + roi_w + 20
        # If menu goes off screen, put it on the left
        if menu_x + menu_width > screen_width:
            menu_x = roi_x - menu_width - 20
        # If still off screen, center it
        if menu_x < 0:
            menu_x = (screen_width - menu_width) // 2
        menu_y = roi_y
    else:
        # Center on screen as fallback
        menu_width = 400
        menu_height = 500
        menu_x = (screen_width - menu_width) // 2
        menu_y = (screen_height - menu_height) // 2

    # Show title using shared function
    title_canvas = show_title_overlay(root, roi)

    # Create menu canvas with rounded effect
    canvas = tk.Canvas(
        root, width=menu_width, height=menu_height,
        bg='black', highlightthickness=0
    )
    canvas.place(x=menu_x, y=menu_y)
    setattr(canvas, "_maphelper_popup", True)

    # Draw large rounded background
    create_rounded_rect(
        canvas, 0, 0, menu_width, menu_height, radius=25,
        fill="#1a1a1a", outline="#d0cbc8", width=3
    )

    # Create button helper
    def create_button(y, text, command):
        margin = 30  # Equal margins on both sides
        btn_rect = create_rounded_rect(
            canvas, margin, y, menu_width - margin, y + 50, radius=10,
            fill="#2a2a2a", outline="#00ff00", width=2
        )
        btn_text = canvas.create_text(
            menu_width // 2, y + 25, text=text,
            fill="white", font=(CUSTOM_FONT, 12)
        )

        def on_click(event):
            command()

        canvas.tag_bind(btn_rect, '<Button-1>', on_click)
        canvas.tag_bind(btn_text, '<Button-1>', on_click)

    def set_result(value):
        result['value'] = value
        waiting['flag'] = False
        # Keep title visible - only destroy menu
        canvas.destroy()

    # Store title canvas reference so it can be cleaned up later if needed
    result['title_canvas'] = title_canvas

    # Buttons - start from top since title is separate
    button_y = 30
    create_button(button_y, "🔍 Auto-Detect Map", lambda: set_result(None))
    button_y += 65
    create_button(button_y, "⚙️ Settings", lambda: set_result("SETTINGS"))
    button_y += 65

    # Map list in 2 columns
    if available_maps:
        canvas.create_text(
            menu_width // 2, button_y + 20,
            text="Available Maps:", fill="white", font=(CUSTOM_FONT, 12)
        )
        button_y += 50

        # Calculate 2-column layout with equal margins
        margin = 30
        col_width = (menu_width - (margin * 2) - 20) // 2  # 20px gap between columns
        for idx, map_name in enumerate(available_maps):
            col = idx % 2
            row = idx // 2

            x_offset = margin + (col * (col_width + 20))
            y_pos = button_y + (row * 55)

            btn_rect = create_rounded_rect(
                canvas, x_offset, y_pos, x_offset + col_width, y_pos + 45, radius=10,
                fill="#2a2a2a", outline="#00ff00", width=2
            )
            btn_text = canvas.create_text(
                x_offset + col_width // 2, y_pos + 22,
                text=f"📍 {map_name}", fill="white", font=(CUSTOM_FONT, 11)
            )

            def on_map_click(m=map_name):
                set_result(m)

            canvas.tag_bind(btn_rect, '<Button-1>', lambda e, m=map_name: set_result(m))
            canvas.tag_bind(btn_text, '<Button-1>', lambda e, m=map_name: set_result(m))

    # Instructions
    canvas.create_text(
        menu_width // 2, menu_height - 30,
        text="M or ESC to cancel",
        fill="#888888", font=(CUSTOM_FONT, 9)
    )

    # ESC double-press to exit app, M to cancel
    def on_key(event):
        if event.keysym == 'Escape':
            current_time = time.time()
            time_since_last_esc = current_time - last_esc_press['time']

            if time_since_last_esc < 1.0:  # Within 1 second - exit app
                import sys
                sys.exit(0)
            else:
                last_esc_press['time'] = current_time
                set_result("CANCEL")
        elif event.keysym.lower() == 'm':
            set_result("CANCEL")

    root.bind('<Key>', on_key)

    # Wait for selection
    root.deiconify()
    while waiting['flag']:
        root.update()

        # Check for M key press using keyboard library (works even when hotkey manager is blocked)
        try:
            import keyboard
            if keyboard.is_pressed('m'):
                set_result("CANCEL")
                time.sleep(0.1)
                break
        except:
            pass

        time.sleep(0.01)

    root.unbind('<Key>')

    # Return choice and title canvas (for later cleanup)
    return result['value'], result.get('title_canvas')


def show_map_confirmation(root, map_name):
    """Show map confirmation dialog. Returns 'YES', 'NO', or 'CHOOSE'."""
    result = {'value': None}
    waiting = {'flag': True}

    # Get screen dimensions
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # Create dialog
    dialog_width, dialog_height = 500, 300
    dialog_x = (screen_width - dialog_width) // 2
    dialog_y = (screen_height - dialog_height) // 2

    canvas = tk.Canvas(
        root, width=dialog_width, height=dialog_height,
        bg='#1a1a1a', highlightthickness=3, highlightbackground='#d0cbc8'
    )
    canvas.place(x=dialog_x, y=dialog_y)
    setattr(canvas, "_maphelper_popup", True)

    # Title
    canvas.create_text(
        dialog_width // 2, 50, text="Map Detected",
        fill="#00ff00", font=(CUSTOM_FONT, 18)
    )

    # Question
    canvas.create_text(
        dialog_width // 2, 110, text=f"Is this map correct?",
        fill="white", font=(CUSTOM_FONT, 12)
    )

    # Map name
    canvas.create_text(
        dialog_width // 2, 140, text=map_name,
        fill="#f1f211", font=(CUSTOM_FONT, 16)
    )

    def set_result(value):
        result['value'] = value
        waiting['flag'] = False
        canvas.destroy()

    # Yes button
    yes_btn = create_rounded_rect(
        canvas, 40, 180, 180, 230, radius=10,
        fill="#2a2a2a", outline="#00ff00", width=2
    )
    yes_text = canvas.create_text(
        110, 205, text="✓ Yes",
        fill="#00ff00", font=(CUSTOM_FONT, 12)
    )
    canvas.tag_bind(yes_btn, '<Button-1>', lambda e: set_result("YES"))
    canvas.tag_bind(yes_text, '<Button-1>', lambda e: set_result("YES"))

    # No button
    no_btn = create_rounded_rect(
        canvas, 190, 180, 310, 230, radius=10,
        fill="#2a2a2a", outline="#ff0000", width=2
    )
    no_text = canvas.create_text(
        250, 205, text="✗ No",
        fill="#ff0000", font=(CUSTOM_FONT, 12)
    )
    canvas.tag_bind(no_btn, '<Button-1>', lambda e: set_result("NO"))
    canvas.tag_bind(no_text, '<Button-1>', lambda e: set_result("NO"))

    # Choose Map button
    choose_btn = create_rounded_rect(
        canvas, 320, 180, 460, 230, radius=10,
        fill="#2a2a2a", outline="#ffaa00", width=2
    )
    choose_text = canvas.create_text(
        390, 205, text="Choose Map",
        fill="#ffaa00", font=(CUSTOM_FONT, 11)
    )
    canvas.tag_bind(choose_btn, '<Button-1>', lambda e: set_result("CHOOSE"))
    canvas.tag_bind(choose_text, '<Button-1>', lambda e: set_result("CHOOSE"))

    # Instructions
    canvas.create_text(
        dialog_width // 2, dialog_height - 30,
        text="Y = Yes | N = No | M = Choose Map",
        fill="#888888", font=(CUSTOM_FONT, 9)
    )

    # Keyboard shortcuts
    def on_key(event):
        if event.keysym.lower() == 'y':
            set_result("YES")
        elif event.keysym.lower() == 'n':
            set_result("NO")
        elif event.keysym.lower() == 'm':
            set_result("CHOOSE")

    root.bind('<Key>', on_key)

    # Wait for selection
    root.deiconify()
    while waiting['flag']:
        root.update()

        # Check for M key press using keyboard library (works even when hotkey manager is blocked)
        try:
            import keyboard
            if keyboard.is_pressed('m'):
                set_result("CHOOSE")
                time.sleep(0.1)
                break
        except:
            pass

        time.sleep(0.01)

    root.unbind('<Key>')
    return result['value']


def show_settings_dialog(root, settings):
    """Show settings dialog. Returns 'BACK' to go to menu, or 'CLOSE'."""
    changed = {'flag': False}
    waiting = {'flag': True}
    result = {'value': 'CLOSE'}
    last_esc_press = {'time': 0}  # Track last ESC press time

    # Get screen dimensions
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # Create settings canvas
    settings_width, settings_height = 600, 500
    settings_x = (screen_width - settings_width) // 2
    settings_y = (screen_height - settings_height) // 2

    canvas = tk.Canvas(
        root, width=settings_width, height=settings_height,
        bg='#1a1a1a', highlightthickness=3, highlightbackground='#d0cbc8'
    )
    canvas.place(x=settings_x, y=settings_y)
    setattr(canvas, "_maphelper_popup", True)

    # Title
    canvas.create_text(
        settings_width // 2, 30, text="⚙️ SETTINGS",
        fill="#00ff00", font=(CUSTOM_FONT, 20)
    )

    # Threading toggle
    threading_enabled = {'value': settings.get("threading_enabled", True)}
    thread_count = {'value': settings.get("thread_count", 8)}
    languages = ['en', 'zh']  # Available languages
    current_language = {'value': settings.get("language", "en")}
    if current_language['value'] not in languages:
        current_language['value'] = 'en'

    def update_display():
        canvas.delete("dynamic")
        y = 80

        # Threading status
        canvas.create_text(
            50, y,
            text=f"🔄 Multi-threading: {'ON' if threading_enabled['value'] else 'OFF'}",
            fill="#00ff00" if threading_enabled['value'] else "#888888",
            font=(CUSTOM_FONT, 12), anchor="w", tags="dynamic"
        )
        y += 50

        # Thread count with +/- buttons
        if threading_enabled['value']:
            canvas.create_text(
                50, y, text=f"Thread Count:",
                fill="white", font=(CUSTOM_FONT, 11), anchor="w", tags="dynamic"
            )

            # Minus button
            minus_btn = create_rounded_rect(
                canvas, 200, y - 15, 235, y + 15, radius=8,
                fill="#2a2a2a", outline="#888888", width=1, tags="dynamic"
            )
            minus_text = canvas.create_text(
                217, y, text="−", fill="white", font=(CUSTOM_FONT, 16), tags="dynamic"
            )

            # Count display
            canvas.create_text(
                270, y, text=str(thread_count['value']),
                fill="#00ff00", font=(CUSTOM_FONT, 14), tags="dynamic"
            )

            # Plus button
            plus_btn = create_rounded_rect(
                canvas, 305, y - 15, 340, y + 15, radius=8,
                fill="#2a2a2a", outline="#888888", width=1, tags="dynamic"
            )
            plus_text = canvas.create_text(
                322, y, text="+", fill="white", font=(CUSTOM_FONT, 16), tags="dynamic"
            )

            def decrease_threads(e):
                if thread_count['value'] > 2:
                    thread_count['value'] -= 1
                    settings.set("thread_count", thread_count['value'])
                    changed['flag'] = True
                    update_display()

            def increase_threads(e):
                if thread_count['value'] < 16:
                    thread_count['value'] += 1
                    settings.set("thread_count", thread_count['value'])
                    changed['flag'] = True
                    update_display()

            canvas.tag_bind(minus_btn, '<Button-1>', decrease_threads)
            canvas.tag_bind(minus_text, '<Button-1>', decrease_threads)
            canvas.tag_bind(plus_btn, '<Button-1>', increase_threads)
            canvas.tag_bind(plus_text, '<Button-1>', increase_threads)

            y += 50

        # Language selector
        lang_names = {'en': 'English', 'zh': '中文'}
        canvas.create_text(
            50, y, text=f"Language:",
            fill="white", font=(CUSTOM_FONT, 11), anchor="w", tags="dynamic"
        )

        lang_btn = create_rounded_rect(
            canvas, 200, y - 15, 320, y + 15, radius=8,
            fill="#2a2a2a", outline="#00ff00", width=2, tags="dynamic"
        )
        lang_text = canvas.create_text(
            260, y, text=lang_names.get(current_language['value'], current_language['value']),
            fill="#00ff00", font=(CUSTOM_FONT, 12), tags="dynamic"
        )

        def cycle_language(e):
            idx = languages.index(current_language['value'])
            current_language['value'] = languages[(idx + 1) % len(languages)]
            settings.set("language", current_language['value'])
            changed['flag'] = True
            update_display()

        canvas.tag_bind(lang_btn, '<Button-1>', cycle_language)
        canvas.tag_bind(lang_text, '<Button-1>', cycle_language)

        y += 50

        # Other settings
        canvas.create_text(
            50, y, text=f"Min Match Quality: {settings.get('min_inliers', 6)}",
            fill="white", font=(CUSTOM_FONT, 11), anchor="w", tags="dynamic"
        )
        y += 40
        canvas.create_text(
            50, y, text=f"Cache Duration: {settings.get('cache_duration_minutes', 15)} min",
            fill="white", font=(CUSTOM_FONT, 11), anchor="w", tags="dynamic"
        )

    update_display()

    # Buttons
    def toggle_threading():
        threading_enabled['value'] = not threading_enabled['value']
        settings.set("threading_enabled", threading_enabled['value'])
        changed['flag'] = True
        update_display()

    def go_back():
        result['value'] = 'BACK'
        waiting['flag'] = False
        canvas.destroy()

    # Back to Menu button
    back_btn = create_rounded_rect(
        canvas, 50, settings_height - 80, settings_width // 2 - 20, settings_height - 30, radius=10,
        fill="#2a2a2a", outline="#00ff00", width=2
    )
    back_text = canvas.create_text(
        settings_width // 4 + 15, settings_height - 55,
        text="← Back to Menu", fill="white", font=(CUSTOM_FONT, 11)
    )
    canvas.tag_bind(back_btn, '<Button-1>', lambda e: go_back())
    canvas.tag_bind(back_text, '<Button-1>', lambda e: go_back())

    # Toggle Threading button
    toggle_btn = create_rounded_rect(
        canvas, settings_width // 2 + 20, settings_height - 80, settings_width - 50, settings_height - 30, radius=10,
        fill="#2a2a2a", outline="#00ff00", width=2
    )
    toggle_text = canvas.create_text(
        settings_width * 3 // 4, settings_height - 55,
        text="Toggle Threading", fill="white", font=(CUSTOM_FONT, 11)
    )
    canvas.tag_bind(toggle_btn, '<Button-1>', lambda e: toggle_threading())
    canvas.tag_bind(toggle_text, '<Button-1>', lambda e: toggle_threading())

    # ESC double-press to exit app, M or ESC to go back
    def on_key(event):
        if event.keysym == 'Escape':
            current_time = time.time()
            time_since_last_esc = current_time - last_esc_press['time']

            if time_since_last_esc < 1.0:  # Within 1 second - exit app
                import sys
                sys.exit(0)
            else:
                last_esc_press['time'] = current_time
                go_back()
        elif event.keysym.lower() == 'm':
            go_back()

    root.bind('<Key>', on_key)

    # Wait
    root.deiconify()
    while waiting['flag']:
        root.update()

        # Check for M key press using keyboard library (works even when hotkey manager is blocked)
        try:
            import keyboard
            if keyboard.is_pressed('m'):
                go_back()
                time.sleep(0.1)
                break
        except:
            pass

        time.sleep(0.01)

    root.unbind('<Key>')
    return result['value']
