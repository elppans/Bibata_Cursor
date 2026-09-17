#!/usr/bin/env python3
"""Build scalable cursors alongside the existing Xcursor themes."""

import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile
import tomllib
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def recolor(svg, colors):
    """Replace palette tokens in one pass, including black/white swaps."""
    palette = {item['match'].lower(): item['replace'] for item in colors}
    pattern = '|'.join(re.escape(color) for color in palette)
    return re.sub(f'(?:{pattern})(?![0-9a-f])',
                  lambda match: palette[match[0].lower()], svg, flags=re.IGNORECASE)


def source_frames(source, pattern):
    pattern = str(Path(pattern).with_suffix('.svg'))
    frames = list(source.glob(pattern))
    # Animated sources live in symlinked subdirectories (wait, left_ptr_watch).
    for child in source.iterdir():
        if child.is_dir():
            frames.extend(child.glob(pattern))
    if not frames:
        raise ValueError(f'No SVG frames for {source / pattern}')
    return sorted(frames, key=lambda path: path.name)


def frame_metadata(svg, filename, settings, animated):
    root = ET.fromstring(svg)
    width = float(root.attrib['width'].removesuffix('px'))
    height = float(root.attrib['height'].removesuffix('px'))
    if width != height or not width.is_integer() or width <= 0:
        raise ValueError(f'Expected a square pixel canvas: {filename}')
    x, y = settings['x_hotspot'], settings['y_hotspot']
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(f'Hotspot outside canvas: {filename}')
    return {
        'filename': filename,
        'nominal_size': int(width),
        'hotspot_x': x,
        'hotspot_y': y,
        'delay': settings['x11_delay'] if animated else 0,
    }


def build_theme(name, variant, output, root=ROOT):
    side = 'right' if name.endswith('-Right') else 'normal'
    with (root / 'configs' / side / 'x.build.toml').open('rb') as handle:
        config = tomllib.load(handle)
    cursors = config['cursors']
    defaults = cursors['fallback_settings']
    source = root / variant['dir']
    theme_dir = output / name
    theme_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.svg-build-', dir=theme_dir) as temporary:
        scalable = Path(temporary) / 'cursors_scalable'
        scalable.mkdir()
        aliases = {}
        for key, cursor in cursors.items():
            if key == 'fallback_settings':
                continue
            target = scalable / cursor['x11_name']
            target.mkdir()
            frames = source_frames(source, cursor['png'])
            metadata = []
            for frame in frames:
                svg = recolor(frame.read_text(), variant['colors'])
                metadata.append(frame_metadata(svg, frame.name, defaults | cursor, len(frames) > 1))
                (target / frame.name).write_text(svg)
            (target / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
            for alias in cursor.get('x11_symlinks', []):
                if alias in aliases:
                    raise ValueError(f'Duplicate cursor alias: {alias}')
                aliases[alias] = target.name
        for alias, target in aliases.items():
            (scalable / alias).symlink_to(target, target_is_directory=True)
        destination = theme_dir / 'cursors_scalable'
        if destination.exists():
            shutil.rmtree(destination)
        scalable.rename(destination)
    # Standalone SVG builds are discoverable too; preserve ctgen's index if present.
    index = theme_dir / 'index.theme'
    if not index.exists():
        index.write_text(f'[Icon Theme]\nName={name}\nComment=Bibata scalable cursors\n')
    shutil.copyfile(root / 'LICENSE', theme_dir / 'LICENSE')


def main():
    variants = json.loads((ROOT / 'render.json').read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'themes')
    parser.add_argument('--theme', action='append', choices=variants)
    args = parser.parse_args()
    for name in args.theme or variants:
        build_theme(name, variants[name], args.output)
        print(f'Built scalable cursors: {name}')


if __name__ == '__main__':
    main()
