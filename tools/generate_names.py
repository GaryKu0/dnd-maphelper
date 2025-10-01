#!/usr/bin/env python3
"""Generate names.json files for map folders by scanning PNG files.

Usage:
  python tools/generate_names.py [--dry-run] [--overwrite]

This script looks under the `maps/` directory, finds folders with PNG files,
and creates a `names.json` mapping where each key is the PNG basename (no ext)
and the value is a humanized display name. By default it does a dry-run.
"""
import argparse
from pathlib import Path
import json
import re


def humanize(key: str, strip_prefix: str | None) -> str:
    # If key starts with prefix_ remove it (case-insensitive)
    original = key
    if strip_prefix and key.lower().startswith(strip_prefix.lower() + "_"):
        key = key[len(strip_prefix) + 1 :]
    # Replace underscores with spaces and split camel/pascal case
    s = key.replace('_', ' ')
    # Insert spaces before caps (e.g., IceAbyss -> Ice Abyss)
    s = re.sub(r'(?<!^)(?=[A-Z][a-z])', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # Capitalize each word
    parts = s.split(' ')
    parts = [p.capitalize() for p in parts]
    return ' '.join(parts) if parts else original


def make_names_for_dir(dirpath: Path, overwrite: bool) -> dict | None:
    pngs = sorted(p for p in dirpath.iterdir() if p.suffix.lower() == '.png')
    if not pngs:
        return None
    out = {'en': {}, 'zh': {}}
    strip_prefix = dirpath.name
    for p in pngs:
        key = p.stem
        display = humanize(key, strip_prefix)
        out['en'][key] = display
        # For now copy English into Chinese to give a fallback the user can edit
        out['zh'][key] = display
    target = dirpath / 'names.json'
    if target.exists() and not overwrite:
        return None
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Do not write files; show what would be created')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing names.json')
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1] / 'maps'
    if not root.exists():
        print('maps/ directory not found at', root)
        return
    created = []
    skipped = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        res = make_names_for_dir(d, args.overwrite)
        if res is None:
            skipped.append(str(d.relative_to(root)))
            continue
        created.append(str(d.relative_to(root)))
        if args.dry_run:
            print(f'Would create {d / "names.json"} with {len(res["en"])} entries')
        else:
            target = d / 'names.json'
            with target.open('w', encoding='utf-8') as f:
                json.dump(res, f, ensure_ascii=False, indent=2)
            print(f'Wrote {target} ({len(res["en"]) } entries)')

    print('\nSummary:')
    print('  Created:', len(created))
    for c in created[:10]:
        print('   -', c)
    print('  Skipped (already have names.json or no PNGs):', len(skipped))


if __name__ == '__main__':
    main()
