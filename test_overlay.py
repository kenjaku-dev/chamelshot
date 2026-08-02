import os
from unittest.mock import MagicMock, patch

from overlay import WindowSelector


class FakeQPixmap:
    def __init__(self, path=""):
        self._null = not path

    def isNull(self):  # noqa: N802
        return self._null


def _make_selector() -> tuple[WindowSelector, list[tuple[str, object]]]:
    sel = WindowSelector()
    seen: list[tuple[str, object]] = []
    sel.pixmap_captured.connect(lambda pm: seen.append(("pixmap", pm)))
    sel.error.connect(lambda msg: seen.append(("error", msg)))
    sel.cancelled.connect(lambda: seen.append(("cancelled", None)))
    return sel, seen


def test_unsupported_compositor_emits_error():
    sel, seen = _make_selector()
    with patch.dict(os.environ, {}, clear=True):
        with patch("overlay.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            sel._run()
    assert any(item[0] == "error" for item in seen)


def test_niri_capture_emits_pixmap(tmp_path):
    sel, seen = _make_selector()
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
    assert any(item[0] == "pixmap" for item in seen)


def test_niri_capture_error_surfaces():
    sel, seen = _make_selector()
    with patch.dict(os.environ, {"NIRI_SOCKET": "/run/user/0/niri.sock"}, clear=True):
        with patch("overlay.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"boom")
            sel._run_niri()
    assert any(item[0] == "error" for item in seen)
