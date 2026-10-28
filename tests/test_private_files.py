import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from permissions import assert_private
from banklens_pdf.private_files import create_private, private_temporary


class PrivateFileTests(unittest.TestCase):
    def test_private_files_resist_permissive_parent_and_preserve_existing(self):
        with tempfile.TemporaryDirectory() as root:
            parent = Path(root)
            if os.name == 'nt':
                # An inheritable Everyone grant must not reach generated files.
                subprocess.run(['icacls', str(parent), '/grant', '*S-1-1-0:(OI)(CI)F'],
                               check=True, capture_output=True)
            else:
                parent.chmod(0o777)
            path = parent / 'synthetic.txt'
            with os.fdopen(create_private(path), 'wb') as output:
                output.write(b'synthetic')
            assert_private(self, path)
            self.assertEqual(path.read_bytes(), b'synthetic')
            with self.assertRaises(FileExistsError):
                create_private(path)
            self.assertEqual(path.read_bytes(), b'synthetic')
            fd, temporary = private_temporary(parent, '.sample-')
            with os.fdopen(fd, 'wb') as output:
                output.write(b'temporary')
            assert_private(self, temporary)
            self.assertEqual(temporary.read_bytes(), b'temporary')


if __name__ == '__main__':
    unittest.main()
