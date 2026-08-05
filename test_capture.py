from unittest.mock import MagicMock, patch

import pytest

from capture import (
    GRIM_NOT_FOUND,
    capture_fullscreen,
    capture_monitor,
    capture_region,
    focused_monitor,
    list_monitors,
    parse_monitors,
)


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


@patch("capture.QPixmap", FakeQPixmap)
class TestMonitorCapture:
    def test_basic_args(self):
        with patch("capture.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"pngdata")
            capture_monitor("HDMI-A-1")
        args = mock_run.call_args[0][0]
        assert args == ["grim", "-o", "HDMI-A-1", "-"]

    def test_with_cursor(self):
        with patch("capture.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"pngdata")
            capture_monitor("DP-2", include_cursor=True)
        args = mock_run.call_args[0][0]
        assert args[:2] == ["grim", "--cursor"]
        assert "-o" in args and "DP-2" in args


class TestParseMonitors:
    def test_parses_niri_json(self):
        monitors = parse_monitors(
            '{"HDMI-A-1": {"make": "Link", "model": "0x0001"}, "DP-2": {"make": "", "model": "M"}}'
        )
        assert monitors == [("HDMI-A-1", "Link", "0x0001"), ("DP-2", "", "M")]

    def test_empty_on_bad_json(self):
        assert parse_monitors("not json") == []
        assert parse_monitors("") == []

    def test_skips_non_dict_entries(self):
        assert parse_monitors('{"HDMI-A-1": null, "DP-2": {"make": "A"}}') == [("DP-2", "A", "")]


class TestListMonitors:
    def test_returns_parse_result(self):
        with patch("capture._run_niri", return_value={"X": {"make": "A"}}):
            assert list_monitors() == [("X", "A", "")]

    def test_empty_when_niri_missing(self):
        with patch("capture._run_niri", return_value=None):
            assert list_monitors() == []

    def test_non_dict_entries_skipped(self):
        with patch("capture._run_niri", return_value={"X": {"make": "A"}, "Y": None}):
            assert list_monitors() == [("X", "A", "")]


class TestFocusedMonitor:
    def test_returns_name(self):
        with patch("capture._run_niri", return_value={"name": "DP-2"}):
            assert focused_monitor() == "DP-2"

    def test_none_on_failure(self):
        with patch("capture._run_niri", return_value=None):
            assert focused_monitor() is None
