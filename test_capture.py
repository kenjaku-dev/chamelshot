from unittest.mock import MagicMock, patch

import pytest

from capture import (
    GRIM_NOT_FOUND,
    capture_fullscreen,
    capture_geometry,
    capture_monitor,
    capture_region,
    capture_window,
    find_window_id,
    focused_monitor,
    list_monitors,
    parse_monitors,
    parse_region_geometry,
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


class TestParseRegionGeometry:
    def test_parses_width_height_offsets(self):
        assert parse_region_geometry("1920x1080+0+0") == (0, 0, 1920, 1080)

    def test_parses_non_zero_offsets(self):
        assert parse_region_geometry("800x600+100+200") == (100, 200, 900, 800)

    def test_negative_offsets_not_allowed(self):
        assert parse_region_geometry("100x50+-5+3") is None

    def test_rejects_garbage(self):
        assert parse_region_geometry("foo") is None
        assert parse_region_geometry("1920x1080") is None
        assert parse_region_geometry("") is None


class TestFindWindowId:
    WINDOWS = "not json"

    def test_finds_by_app_id(self):
        windows = '[{"app_id": "firefox", "id": 1}, {"app_id": "term", "id": 2}]'
        assert find_window_id(windows, "firefox") == 1

    def test_returns_none_when_absent(self):
        windows = '[{"app_id": "firefox", "id": 1}]'
        assert find_window_id(windows, "editor") is None

    def test_bad_json(self):
        assert find_window_id(self.WINDOWS, "firefox") is None

    def test_non_list_json(self):
        assert find_window_id('{"app_id": "firefox", "id": 1}', "firefox") is None


@patch("capture.QPixmap", FakeQPixmap)
class TestCaptureGeometry:
    def test_delegates_to_region(self):
        with patch("capture.capture_region") as mock_region:
            mock_region.side_effect = lambda left, top, right, bottom, **kw: "pm"
            assert capture_geometry("1920x1080+0+0") == "pm"
        assert mock_region.call_args.args == (0, 0, 1920, 1080)

    def test_passes_cursor(self):
        with patch("capture.capture_region") as mock_region:
            capture_geometry("100x50+10+20", include_cursor=True)
        assert mock_region.call_args.kwargs == {"delay": 0, "include_cursor": True}

    def test_invalid_geometry_raises_before_capture(self):
        with patch("capture.capture_region") as mock_region:
            try:
                capture_geometry("bogus")
            except RuntimeError as exc:
                assert "geometry" in str(exc)
            else:
                assert False, "expected RuntimeError"
        mock_region.assert_not_called()


class TestCaptureWindow:
    def test_window_not_found_raises(self):
        with patch("capture.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='[{"app_id": "x", "id": 1}]')
            try:
                capture_window("nobody")
            except RuntimeError as exc:
                assert "app_id" in str(exc)
            else:
                assert False, "expected RuntimeError"

    def test_niri_missing_raises(self):
        with patch(
            "capture.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            with pytest.raises(RuntimeError, match="niri"):
                capture_window("firefox")

    def test_success_focuses_and_loads_pixmap(self):
        results = [
            MagicMock(returncode=0, stdout='[{"app_id": "firefox", "id": 7}]'),
            MagicMock(returncode=0, stdout=b""),
            MagicMock(returncode=0, stdout=b""),
        ]
        pm = MagicMock()
        pm.isNull.return_value = False
        with (
            patch("capture.QPixmap", return_value=pm),
            patch("capture.subprocess.run", side_effect=results) as mock_run,
            patch("capture.tempfile.TemporaryDirectory") as mock_tmp,
            patch("capture.time.sleep"),
        ):
            mock_tmp.return_value.__enter__.return_value = "/tmp/x"
            assert capture_window("firefox") is pm
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert cmds[0] == ["niri", "msg", "-j", "windows"]
        assert cmds[1] == ["niri", "msg", "action", "focus-window", "7"]
        assert cmds[2][:5] == ["niri", "msg", "action", "screenshot-window", "--path"]
