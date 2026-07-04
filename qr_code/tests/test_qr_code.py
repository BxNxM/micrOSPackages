import importlib.util
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "package" / "qr_code.py"
SPEC = importlib.util.spec_from_file_location("qr_code_under_test", str(PATH))
qr_code = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qr_code)


class TestQrCode(unittest.TestCase):
    def test_version_one_matrix(self):
        matrix = qr_code.make("https://a.co")
        self.assertEqual(len(matrix), 21)
        self.assertTrue(all(len(row) == 21 for row in matrix))
        self.assertTrue(all(isinstance(cell, bool)
                            for row in matrix for cell in row))

    def test_larger_url_selects_larger_version(self):
        matrix = qr_code.make("https://example.com/" + "a" * 80)
        self.assertGreater(len(matrix), 21)

    def test_utf8(self):
        self.assertTrue(qr_code.make("https://example.com/árvíztűrő"))

    def test_rejects_oversized_url(self):
        with self.assertRaises(ValueError):
            qr_code.make("x" * 272)

    def test_render_has_quiet_zone(self):
        text = qr_code.render("https://a.co", dark="#", light=".", border=2)
        rows = text.splitlines()
        self.assertEqual(len(rows), 25)
        self.assertEqual(rows[0], "." * 25)

def test_terminal_qr_is_generated_and_shown(capsys):
    """Generate a real QR and leave it visible in the test command output."""
    url = "https://github.com/BxNxM/micrOS"
    with capsys.disabled():
        print("\nTest QR Code for: " + url)
        matrix = qr_code.print_qr(url)
    assert len(matrix) == 25


if __name__ == "__main__":
    unittest.main()
