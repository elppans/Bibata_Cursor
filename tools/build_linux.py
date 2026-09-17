#!/usr/bin/env python3
"""Build Linux themes with both Xcursor and scalable SVG assets."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from build_svg_cursors import ROOT, build_theme


def render_frame(args):
    source, destination = args
    subprocess.run(['rsvg-convert', '--output', str(destination), str(source)], check=True)


def build_linux(name, variant, output, sizes=None):
    build_theme(name, variant, output)
    scalable = output / name / 'cursors_scalable'
    side = 'right' if name.endswith('-Right') else 'normal'
    with tempfile.TemporaryDirectory(prefix='bibata-bitmaps-') as temporary:
        bitmaps = Path(temporary)
        compiled = bitmaps / 'compiled'
        frames = []
        for cursor in scalable.iterdir():
            if cursor.is_symlink():
                continue
            for svg in cursor.glob('*.svg'):
                frames.append((svg, bitmaps / f'{svg.stem}.png'))
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(render_frame, frames))
        command = [
            'ctgen', str(ROOT / 'configs' / side / 'x.build.toml'),
            '-p', 'x11', '-d', str(bitmaps), '-o', str(compiled),
            '-n', name, '-c', 'Bibata Xcursor and scalable SVG cursors',
        ]
        if sizes:
            command.extend(['-s', *(str(size) for size in sizes)])
        subprocess.run(command, check=True)
        # ctgen cannot overwrite its symlinks. Publish a fresh build instead.
        legacy = output / name / 'cursors'
        if legacy.exists():
            shutil.rmtree(legacy)
        shutil.move(str(compiled / name / 'cursors'), legacy)
        shutil.copyfile(compiled / name / 'index.theme', output / name / 'index.theme')
    if not (output / name / 'cursors/default').is_file():
        raise RuntimeError(f'Missing Xcursor output: {name}')
    if not (scalable / 'default/metadata.json').is_file():
        raise RuntimeError(f'Missing SVG output: {name}')


def main():
    variants = json.loads((ROOT / 'render.json').read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'themes')
    parser.add_argument('--theme', action='append', choices=variants)
    parser.add_argument('--sizes', type=int, nargs='+', help='Legacy Xcursor sizes only')
    args = parser.parse_args()
    if args.sizes and any(size <= 0 for size in args.sizes):
        parser.error('Cursor sizes must be positive')
    for command in ('ctgen', 'rsvg-convert'):
        if not shutil.which(command):
            parser.error(f'Required build tool not found: {command}')
    for name in args.theme or variants:
        print(f'Building Linux theme: {name}', flush=True)
        build_linux(name, variants[name], args.output.resolve(), args.sizes)


if __name__ == '__main__':
    main()
