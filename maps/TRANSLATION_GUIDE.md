# Map Translation Guide

## Overview

You can translate location names displayed on the overlay by creating a `names.json` file in each map folder.

## File Structure

Create a `names.json` file in your map folder (e.g., `maps/GoblinCave/names.json`):

```json
{
  "en": {
    "Cave_Altar_02": "Altar Chamber",
    "Cave_Valley": "Cave Valley"
  },
  "zh": {
    "Cave_Altar_02": "祭坛室",
    "Cave_Valley": "洞穴谷地"
  }
}
```

## Format

- **Top level keys**: Language codes (`en`, `zh`, `es`, `fr`, etc.)
- **Second level keys**: Template filename without extension
- **Values**: Display name in that language

## Supported Languages

Currently configured languages:
- `en` - English
- `zh` - Chinese (中文)

You can add more languages by:
1. Adding translations to `names.json`
2. Updating the `languages` list in `ui/dialogs.py` (line 189)

## How It Works

1. The system loads template images from the map folder
2. When a match is found, it looks up the filename in `names.json`
3. If a translation exists for the current language, it displays that
4. Otherwise, it falls back to the filename (with underscores replaced by spaces)

## Example Workflow

1. **List your templates**:
   ```
   maps/MyMap/
     ├── Cave_Entrance.png
     ├── Dark_Hall.png
     └── Boss_Room.png
   ```

2. **Create names.json**:
   ```json
   {
     "en": {
       "Cave_Entrance": "Cave Entrance",
       "Dark_Hall": "Dark Hall",
       "Boss_Room": "Boss Chamber"
     },
     "zh": {
       "Cave_Entrance": "洞穴入口",
       "Dark_Hall": "黑暗大厅",
       "Boss_Room": "首领房间"
     }
   }
   ```

3. **Change language in settings**:
   - Press `M` → Click "⚙️ Settings"
   - Click the Language button to cycle between languages
   - Click "← Back to Menu"

## Tips

- **No names.json?** The system will use the filename automatically
- **Missing translation?** Falls back to English, then to filename
- **UTF-8 encoding**: Make sure to save `names.json` as UTF-8 to support special characters
- **Consistency**: Use the exact filename (without extension) as the key

## Adding a New Language

1. Edit `ui/dialogs.py` line 189:
   ```python
   languages = ['en', 'zh', 'es']  # Add 'es' for Spanish
   ```

2. Add language name display on line 260:
   ```python
   lang_names = {'en': 'English', 'zh': '中文', 'es': 'Español'}
   ```

3. Add translations to your `names.json`:
   ```json
   {
     "en": { ... },
     "zh": { ... },
     "es": { ... }
   }
   ```
