import os
from unittest.mock import MagicMock, patch

from overlay import WindowSelector


class FakeQPixmap:
    def __init__(self, path=""):
        self._null = not path

    def isNull(self):  # noqa: N802
        return self._null


def _make_selector():
    sel = WindowSelector()
    sel._seen = []
    sel.pixmap_captured.connect(lambda pm: sel._seen.append(("pixmap", pm)))
    sel.error.connect(lambda msg: sel._seen.append(("error", msg)))
    sel.cancelled.connect(lambda: sel._seen.append(("cancelled",)))
    return sel


def test_unsupported_compositor_emits_error():
    sel = _make_selector()
    with patch.dict(os.environ, {}, clear=True):
        with patch("overlay.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            sel._run()
    assert any(item[0] == "error" for item in sel._seen)


def test_niri_capture_emits_pixmap(tmp_path):
    sel = _make_selector()
    png = tmp_path / "window.png"
    png.write_bytes(b"png")
    with patch.dict(os.environ, {"NIRI_SOCKET": "/run/user/0/niri.sock"}, clear=True):
        with (
            patch("overlay.subprocess.run") as mock_run,
            patch("overlay.QPixmap", FakeQPixmap),
            patch("overlay.time.sleep"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            with patch("overlay.tempfile.TemporaryDirectory") as mock_tmp:
                mock_tmp.return_value.__enter__.return_value = str(tmp_path)
                sel._run()
    assert any(item[0] == "pixmap" for item in sel._seen)


def test_niri_capture_error_surfaces():
    sel = _make_selector()
    with patch.dict(os.environ, {"NIRI_SOCKET": "/run/user/0/niri.sock"}, clear=True):
        with patch("overlay.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"boom")
            sel._run_niri()
    assert any(item[0] == "error" for item in sel._seen)
