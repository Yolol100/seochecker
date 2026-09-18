import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from safe_http import _read_limited


class LimitedReadTests(unittest.TestCase):
    def test_exact_boundary_is_not_truncated(self):
        body, truncated = _read_limited(io.BytesIO(b"a" * 10), 10, allow_truncate=True)
        self.assertEqual(len(body), 10)
        self.assertFalse(truncated)

    def test_over_boundary_is_truncated_when_allowed(self):
        body, truncated = _read_limited(io.BytesIO(b"a" * 11), 10, allow_truncate=True)
        self.assertEqual(len(body), 10)
        self.assertTrue(truncated)

    def test_over_boundary_fails_closed_by_default(self):
        with self.assertRaisesRegex(ValueError, "response exceeds max_bytes=10"):
            _read_limited(io.BytesIO(b"a" * 11), 10)


if __name__ == "__main__":
    unittest.main()
