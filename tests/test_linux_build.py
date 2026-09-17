"""Exercise the native compiler and repeated builds."""

from collections import Counter
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('ctgen') and shutil.which('rsvg-convert'),
                     'Requires clickgen and librsvg build tools')
class LinuxBuildTests(unittest.TestCase):
    def test_rebuild_keeps_both_formats_and_requested_sizes(self):
        with tempfile.TemporaryDirectory() as temporary:
            theme = Path(temporary) / 'Bibata-Modern-Classic'
            metadata = None
            for sizes in ((24, 32, 48), (48,)):
                result = subprocess.run([
                    sys.executable, str(ROOT / 'tools/build_linux.py'),
                    '--output', temporary, '--theme', theme.name,
                    '--sizes', *(str(size) for size in sizes),
                ], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = (theme / 'cursors/wait').read_bytes()
                magic, header, _, count = struct.unpack_from('<4I', data)
                self.assertEqual(magic, 0x72756358)
                actual = Counter(struct.unpack_from('<3I', data, header + 12 * i)[1]
                                 for i in range(count))
                self.assertEqual(actual, Counter({size: 54 for size in sizes}))
                self.assertTrue((theme / 'cursors/all-resize').is_file())
                current = (theme / 'cursors_scalable/progress/metadata.json').read_bytes()
                if metadata is not None:
                    self.assertEqual(current, metadata)
                metadata = current


if __name__ == '__main__':
    unittest.main()
