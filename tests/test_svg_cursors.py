"""Validate complete themes against GNOME 51 cursor requirements."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('builder', ROOT / 'tools/build_svg_cursors.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

# clutter_cursor_type_to_name(), Mutter 51.0.
CURSORS = '''default context-menu help pointer progress wait cell crosshair text
vertical-text alias copy move no-drop not-allowed grab grabbing e-resize n-resize
ne-resize nw-resize s-resize se-resize sw-resize w-resize ew-resize ns-resize
nesw-resize nwse-resize col-resize row-resize all-scroll zoom-in zoom-out dnd-ask
all-resize'''.split()


class SvgCursorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.output = Path(cls.directory.name)
        cls.variants = json.loads((ROOT / 'render.json').read_text())
        for name, variant in cls.variants.items():
            builder.build_theme(name, variant, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_all_variants_cover_native_cursor_names(self):
        self.assertEqual(len(self.variants), 70)
        for name in self.variants:
            scalable = self.output / name / 'cursors_scalable'
            for cursor in CURSORS:
                with self.subTest(theme=name, cursor=cursor):
                    metadata = json.loads((scalable / cursor / 'metadata.json').read_text())
                    self.assertTrue(metadata)
                    for frame in metadata:
                        ET.parse(scalable / cursor / frame['filename'])
                        self.assertEqual(frame['nominal_size'], 256)

    def test_animations_keep_frame_order_and_timing(self):
        for name in self.variants:
            for cursor in ('wait', 'progress'):
                frames = json.loads((self.output / name / 'cursors_scalable' / cursor / 'metadata.json').read_text())
                self.assertEqual(len(frames), 54)
                self.assertEqual([f['filename'] for f in frames], sorted(f['filename'] for f in frames))
                self.assertTrue(all(f['delay'] == 40 for f in frames))

    def test_handedness_hotspots_and_colors(self):
        for name, variant in self.variants.items():
            target = self.output / name / 'cursors_scalable/default'
            metadata = json.loads((target / 'metadata.json').read_text())[0]
            self.assertEqual(metadata['hotspot_x'], 207 if name.endswith('-Right') else 55)
            self.assertEqual(metadata['hotspot_y'], 24 if name.endswith('-Right') else 17)
            svg = ET.parse(target / metadata['filename'])
            path = svg.getroot().find('{http://www.w3.org/2000/svg}path')
            palette = {c['match']: c['replace'] for c in variant['colors']}
            self.assertEqual(path.get('fill'), palette['#00FF00'])
            self.assertEqual(path.get('stroke'), palette['#0000FF'])

    def test_rebuild_preserves_legacy_cursors_and_index(self):
        name = 'Bibata-Modern-Classic'
        theme = self.output / name
        (theme / 'cursors').mkdir()
        legacy = theme / 'cursors/left_ptr'
        legacy.write_bytes(b'Xcur legacy fixture')
        index = theme / 'index.theme'
        index.write_text('[Icon Theme]\nName=Existing theme\n')
        builder.build_theme(name, self.variants[name], self.output)
        self.assertEqual(legacy.read_bytes(), b'Xcur legacy fixture')
        self.assertEqual(index.read_text(), '[Icon Theme]\nName=Existing theme\n')
        self.assertTrue((theme / 'cursors_scalable/default/metadata.json').is_file())

    def test_palette_replacement_is_simultaneous(self):
        colors = [{'match': '#000000', 'replace': '#FFFFFF'},
                  {'match': '#FFFFFF', 'replace': '#000000'}]
        self.assertEqual(builder.recolor('#000000 #ffffff', colors), '#FFFFFF #000000')

    def test_missing_source_fails_without_replacing_theme(self):
        name = 'Bibata-Modern-Classic'
        metadata = self.output / name / 'cursors_scalable/default/metadata.json'
        before = metadata.read_bytes()
        with self.assertRaises(ValueError):
            builder.build_theme(name, self.variants[name] | {'dir': 'svg/groups/modern'}, self.output)
        self.assertEqual(metadata.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
