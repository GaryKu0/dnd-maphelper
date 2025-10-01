# Contributing to Dark and Darker Map Helper

Thank you for your interest in contributing! This document explains how to contribute to the project.

## Ways to Contribute

### 1. Add New Maps

To add a new map to the application:

1. **Capture Templates**
   - Take screenshots of each cell in the map
   - Save as PNG files named: `CellName_0.png`, `CellName_90.png`, `CellName_180.png`, `CellName_270.png`
   - All 4 rotations are required for accurate detection

2. **Create Map Folder**
   ```
   maps/YourMapName/
   ├── Cell1_0.png
   ├── Cell1_90.png
   ├── Cell1_180.png
   ├── Cell1_270.png
   ├── Cell2_0.png
   └── ...
   ```

3. **Add Grid Configuration** (optional)
   - Create `grid.json` in the map folder:
   ```json
   {
     "rows": 5,
     "cols": 5
   }
   ```

4. **Add Translations** (optional)
   - Create `names.json` for location names:
   ```json
   {
     "en": {
       "Cell1": "Display Name",
       "Cell2": "Another Name"
     },
     "zh": {
       "Cell1": "中文名称",
       "Cell2": "另一个名称"
     }
   }
   ```

5. **Submit a Pull Request**
   - Fork the repository
   - Add your map folder
   - Test it works
   - Submit PR with description

### 2. Contribute Translations

**We need help with translations!**

Current translations are basic/automatic and need improvement. You can contribute by simply changing your game language and recording the location names:

1. **Find Translation Files**
   - Located in: `maps/[MapName]/names.json`
   - Or use the template in `maps/TRANSLATION_GUIDE.md`

2. **Add/Improve Translations**
   - Change your game language setting
   - Play the map and note the location names
   - Update the translation file:
   ```json
   {
     "en": {
       "CellName": "English Location Name"
     },
     "zh": {
       "CellName": "中文位置名称"
     },
     "es": {
       "CellName": "Nombre en Español"
     }
   }
   ```

3. **Supported Languages**
   - English (`en`)
   - Chinese (`zh`)
   - Add more by using ISO 639-1 codes

4. **Submit Translation PR**
   - Fork and update translation files
   - Verify names match the game exactly
   - Submit PR with language and map name
   - Mention which game language setting you used

### 3. Report Bugs

Found a bug? Please open an issue with:
- Description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Screenshots if applicable
- Your configuration (OS, Python version, etc.)

### 4. Suggest Features

Have an idea? Open an issue with:
- Clear description of the feature
- Use case / why it's needed
- Potential implementation ideas

## Development Setup

### Prerequisites

- Python 3.7+
- Git

### Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/dnd-maphelper.git
   cd dnd-maphelper
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Run from Source**
   ```bash
   python main.py
   ```

## Building Executable

### Local Build (Testing)

To build the standalone executable:

```bash
build_local.bat
```

This creates:
- `dist/MapHelper.exe` - Standalone executable (~100MB)
- `release/` - Package folder for testing
- `MapHelper-Local-Windows.zip` - Distribution package

**Note:** The .exe embeds all maps and fonts inside!

### Automated Releases (Maintainers Only)

The repository uses GitHub Actions for automatic builds:

1. **Create and Push Tag**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **GitHub Actions Automatically:**
   - Builds Windows executable
   - Creates release page
   - Uploads `MapHelper-v1.0.0-Windows.zip`

3. **Release appears at:**
   `https://github.com/garyku0/dnd-maphelper/releases`

### Release Workflow (Maintainers)

1. Update version numbers if needed
2. Test locally: `build_local.bat`
3. Commit all changes
4. Create and push tag: `git tag v1.0.0 && git push origin v1.0.0`
5. Wait for GitHub Actions to complete (~5-10 min)
6. Verify release on GitHub

## Code Guidelines

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable names
- Add docstrings to functions
- Keep functions focused and small

### Commit Messages

- Use clear, descriptive messages
- Start with verb: "Add", "Fix", "Update", "Remove"
- Example: `Add French translations for Crypt map`

### Pull Requests

- One feature/fix per PR
- Include description of changes
- Reference related issues
- Test your changes before submitting

## Testing

Before submitting:

1. Test the feature works
2. Test it doesn't break existing functionality
3. Test on actual game maps if possible
4. Check confidence scores with `analyze_confidence.py`

## Questions?

- Open an issue for questions
- Check existing issues/PRs first
- Be respectful and patient

Thank you for contributing! 🎉
