from unittest.mock import MagicMock, patch

import pytest

from capture import GRIM_NOT_FOUND, capture_fullscreen, capture_region


class FakeQPixmap:
    @staticmethod
    def loadFromData(data):  # noqa: N802
        return True


@patch("capture.QPixmap", FakeQPixmap)
class TestCaptureRegion:
    def test_basic_args(self):
        with patch("capture.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"pngdata")
            capture_region(100, 200, 300, 400)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "grim"
        assert args[1] == "-g"
        assert args[2] == "100,200 200x200"
        assert args[3] == "-"

    def test_with_cursor(self):
        with patch("capture.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"pngdata")
            capture_region(0, 0, 10, 10, include_cursor=True)
        args = mock_run.call_args[0][0]
        assert "--cursor" in args
        cursor_idx = args.index("--cursor")
        assert args[cursor_idx + 1] == "-g"

    def test_with_delay(self):
        with patch("capture.subprocess.run") as mock_run, patch("capture.time.sleep") as mock_sleep:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"pngdata")
            capture_region(0, 0, 10, 10, delay=3)
        mock_sleep.assert_called_once_with(3)

    def test_raises_on_grim_missing(self):
        with patch("capture.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match=GRIM_NOT_FOUND):
                capture_region(0, 0, 10, 10)

    def test_raises_on_grim_failure(self):
        with patch("capture.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"error", stdout=b"")
            with pytest.raises(RuntimeError, match="grim failed"):
                capture_region(0, 0, 10, 10)


@patch("capture.QPixmap", FakeQPixmap)
class TestCaptureFullscreen:
    def test_basic_args(self):
        with patch("capture.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"pngdata")
            capture_fullscreen()
        args = mock_run.call_args[0][0]
        assert args[0] == "grim"
        assert args[-1] == "-"

    def test_with_cursor(self):
        with patch("capture.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"pngdata")
            capture_fullscreen(include_cursor=True)
        args = mock_run.call_args[0][0]
        assert "--cursor" in args

    def test_with_delay(self):
        with patch("capture.subprocess.run") as mock_run, patch("capture.time.sleep") as mock_sleep:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"pngdata")
            capture_fullscreen(delay=5)
        mock_sleep.assert_called_once_with(5)
