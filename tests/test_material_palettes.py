"""Keep the distributed palette catalog and rendered colors consistent."""

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
              for v in channels]
    return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


class MaterialPaletteTests(unittest.TestCase):
    def test_pairs_contrast_and_rendered_colors(self):
        palettes = json.loads((ROOT / 'material-palettes.json').read_text())
        variants = json.loads((ROOT / 'render.json').read_text())
        self.assertEqual(len(palettes), 57)
        for name, palette in palettes.items():
            if name == 'Classic':
                continue
            with self.subTest(theme=name):
                self.assertIn(name.removesuffix('-Light') + '-Light', palettes)
                values = sorted((luminance(palette['body']), luminance(palette['primary'])))
                self.assertGreaterEqual((values[1] + 0.05) / (values[0] + 0.05), 4.5)
                actual = variants['Bibata-Material-' + name]['colors']
                self.assertEqual([c['replace'] for c in actual],
                                 [palette[k] for k in ('body', 'primary', 'watch')])
        self.assertNotIn('Bibata-Material-Classic', variants)


if __name__ == '__main__':
    unittest.main()
