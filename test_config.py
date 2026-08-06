import os
from pathlib import Path

import pytest

import config as cfg


def test_save_with_braces_in_values(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "config.toml")
    cfg.save({"save.directory": "{custom}/path", "save.filename_format": "shot_%Y.png"})
    loaded = cfg.load()
    assert loaded["save.directory"] == "{custom}/path"
    assert loaded["save.filename_format"] == "shot_%Y.png"
    written = (tmp_path / "config.toml").read_text()
    assert "{{custom}}" not in written
    assert "custom" in written


def test_save_writes_comment_template(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "config.toml")
    cfg.save({"capture.mode": "fullscreen"})
    written = (tmp_path / "config.toml").read_text()
    assert 'mode = "fullscreen"' in written
    assert "{" not in written


def test_flatten_unflatten_roundtrip():
    nested = {
        "general": {"auto_copy": True, "auto_save": False},
        "capture": {"mode": "region", "delay": 0},
    }
    flat = cfg._flatten(nested)
    assert flat == {"general.auto_copy": True, "general.auto_save": False, "capture.mode": "region", "capture.delay": 0}
    unflat = cfg._unflatten(flat)
    assert unflat == nested


def test_defaults_have_all_keys():
    flat = cfg._flatten(cfg._unflatten(cfg.DEFAULTS))
    assert flat == cfg.DEFAULTS


def test_defaults_contain_expected_keys():
    required = [
        "general.auto_copy",
        "capture.mode",
        "capture.delay",
        "save.directory",
        "shortcuts.save",
        "preview.max_width",
    ]
    for key in required:
        assert key in cfg.DEFAULTS, f"Missing default: {key}"


def test_toml_val_bool():
    assert cfg._toml_val(True) == "true"
    assert cfg._toml_val(False) == "false"


def test_toml_val_int():
    assert cfg._toml_val(42) == "42"
    assert cfg._toml_val(-1) == "-1"


def test_toml_val_str():
    assert cfg._toml_val("hello") == "hello"


def test_load_creates_defaults_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "config.toml")
    result = cfg.load()
    assert result == cfg.DEFAULTS
    assert (tmp_path / "config.toml").exists()


def test_load_returns_merged_config(monkeypatch, tmp_path):
    toml_path = tmp_path / "config.toml"
    toml_path.write_text('general = { auto_copy = false }\ncapture = { mode = "fullscreen" }')
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_PATH", toml_path)
    result = cfg.load()
    assert result["general.auto_copy"] is False
    assert result["capture.mode"] == "fullscreen"
    assert result["preview.max_width"] == 800


def test_load_fallback_on_corrupt_toml(monkeypatch, tmp_path):
    toml_path = tmp_path / "config.toml"
    toml_path.write_text("this is not valid toml {{{")
    monkeypatch.setattr(cfg, "CONFIG_PATH", toml_path)
    result = cfg.load()
    assert result == cfg.DEFAULTS


def test_load_corrupt_config_warns_once_and_keeps_file(monkeypatch, tmp_path, capsys):
    toml_path = tmp_path / "config.toml"
    corrupt = 'save.directory = "unterminated'
    toml_path.write_text(corrupt)
    monkeypatch.setattr(cfg, "CONFIG_PATH", toml_path)
    monkeypatch.setattr(cfg, "_warned_corrupt_config", False)
    assert cfg.load() == cfg.DEFAULTS
    assert cfg.load() == cfg.DEFAULTS
    captured = capsys.readouterr()
    assert "ignored" in captured.err
    assert captured.err.count("ignored") == 1
    assert toml_path.read_text() == corrupt


def test_save_writes_and_reloads(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "config.toml")
    cfg.save({"general.auto_copy": False, "capture.mode": "fullscreen"})
    loaded = cfg.load()
    assert loaded["general.auto_copy"] is False
    assert loaded["capture.mode"] == "fullscreen"


def test_autostart_install_remove(monkeypatch, tmp_path):
    autostart_dir = tmp_path / "autostart"
    monkeypatch.setattr(cfg, "AUTOSTART_PATH", autostart_dir / "chamelshot.desktop")
    assert not cfg.autostart_enabled()
    cfg.install_autostart()
    assert cfg.autostart_enabled()
    content = (autostart_dir / "chamelshot.desktop").read_text()
    assert "Exec=chamelshot" in content
    cfg.remove_autostart()
    assert not cfg.autostart_enabled()


def test_desktop_install_remove(monkeypatch, tmp_path):
    apps = tmp_path / "applications"
    icons = tmp_path / "icons"
    icon_src = tmp_path / "icon.png"
    icon_src.write_bytes(b"PNGDATA")
    monkeypatch.setattr(cfg, "DESKTOP_PATH", apps / "chamelshot.desktop")
    monkeypatch.setattr(cfg, "ICON_DEST_DIR", icons)
    monkeypatch.setattr(cfg, "ICON_SOURCE", icon_src)
    assert not cfg.desktop_installed()
    cfg.ensure_desktop("/home/u/.local/bin/chamelshot")
    assert cfg.desktop_installed()
    content = (apps / "chamelshot.desktop").read_text()
    assert "Exec=/home/u/.local/bin/chamelshot" in content
    assert "Icon=chamelshot" in content
    assert (icons / "chamelshot.png").read_bytes() == b"PNGDATA"
    cfg.remove_desktop()
    assert not cfg.desktop_installed()


def test_desktop_icon_from_prefix_fallback(monkeypatch, tmp_path):
    apps = tmp_path / "applications"
    icons = tmp_path / "icons"
    prefix_icon = tmp_path / "prefix_icon.png"
    prefix_icon.write_bytes(b"PREFIXPNG")
    monkeypatch.setattr(cfg, "DESKTOP_PATH", apps / "chamelshot.desktop")
    monkeypatch.setattr(cfg, "ICON_DEST_DIR", icons)
    monkeypatch.setattr(cfg, "ICON_SOURCE", tmp_path / "missing.png")
    monkeypatch.setattr(
        cfg,
        "_icon_source",
        lambda: prefix_icon,
    )
    cfg.ensure_desktop("/bin/chamelshot")
    assert (icons / "chamelshot.png").read_bytes() == b"PREFIXPNG"


def test_desktop_rewrites_when_binary_moves(monkeypatch, tmp_path):
    apps = tmp_path / "applications"
    icons = tmp_path / "icons"
    icon_src = tmp_path / "icon.png"
    icon_src.write_bytes(b"PNGDATA")
    monkeypatch.setattr(cfg, "DESKTOP_PATH", apps / "chamelshot.desktop")
    monkeypatch.setattr(cfg, "ICON_DEST_DIR", icons)
    monkeypatch.setattr(cfg, "ICON_SOURCE", icon_src)
    cfg.ensure_desktop("/old/bin/chamelshot")
    cfg.ensure_desktop("/new/bin/chamelshot")
    content = (apps / "chamelshot.desktop").read_text()
    assert "Exec=/new/bin/chamelshot" in content
    assert "Exec=/old/bin/chamelshot" not in content


def test_desktop_idempotent_no_rewrite(monkeypatch, tmp_path):
    apps = tmp_path / "applications"
    icons = tmp_path / "icons"
    icon_src = tmp_path / "icon.png"
    icon_src.write_bytes(b"PNGDATA")
    monkeypatch.setattr(cfg, "DESKTOP_PATH", apps / "chamelshot.desktop")
    monkeypatch.setattr(cfg, "ICON_DEST_DIR", icons)
    monkeypatch.setattr(cfg, "ICON_SOURCE", icon_src)
    writes = []
    orig_write = Path.write_text
    monkeypatch.setattr(Path, "write_text", lambda self, *a, **k: (writes.append(self), orig_write(self, *a, **k)))
    cfg.ensure_desktop("/bin/chamelshot")
    cfg.ensure_desktop("/bin/chamelshot")
    assert len(writes) == 1


def test_generate_save_path_creates_dir(monkeypatch, tmp_path):
    save_dir = tmp_path / "screenshots"
    config = {"save.directory": str(save_dir), "save.filename_format": "test.png"}
    result = cfg.generate_save_path(config)
    assert save_dir.exists()
    assert result == os.path.join(str(save_dir), "test.png")


def test_generate_save_path_uses_strftime(monkeypatch, tmp_path):
    import datetime as dt_mod

    real_dt = dt_mod.datetime
    save_dir = tmp_path / "shots"

    def fake_now():
        return real_dt(2026, 7, 29, 12, 0, 0)

    monkeypatch.setattr(dt_mod, "datetime", type("FakeDatetime", (), {"now": staticmethod(fake_now)}))
    result = cfg.generate_save_path({"save.directory": str(save_dir), "save.filename_format": "cap_%Y%m%d.png"})
    assert result == os.path.join(str(save_dir), "cap_20260729.png")


def test_resolve_extension_returns_lowercase():
    assert cfg.resolve_extension("shot_%Y%m%d.PNG") == "png"
    assert cfg.resolve_extension("cap_%H.jpg") == "jpg"


def test_resolve_extension_none_when_no_dot():
    assert cfg.resolve_extension("shot_%Y%m%d") is None


def test_validate_save_settings_ok(tmp_path):
    config = {
        "save.directory": str(tmp_path),
        "save.filename_format": "shot_%Y%m%d.png",
        "save.format": "PNG",
    }
    assert cfg.validate_save_settings(config) == []


def test_validate_save_settings_extension_mismatch(tmp_path):
    config = {
        "save.directory": str(tmp_path),
        "save.filename_format": "shot_%Y%m%d.jpg",
        "save.format": "PNG",
    }
    warnings = cfg.validate_save_settings(config)
    assert len(warnings) == 1
    assert ".png" in warnings[0]


def test_validate_save_settings_jpeg_accepts_jpg_and_jpeg(tmp_path):
    for fmt in ("shot_%Y.jpg", "shot_%Y.jpeg"):
        config = {"save.directory": str(tmp_path), "save.filename_format": fmt, "save.format": "JPEG"}
        assert cfg.validate_save_settings(config) == []


def test_validate_save_settings_missing_dir_under_writable_parent_is_ok(tmp_path):
    config = {
        "save.directory": str(tmp_path / "new" / "deeper"),
        "save.filename_format": "shot_%Y.png",
        "save.format": "PNG",
    }
    assert cfg.validate_save_settings(config) == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission checks")
def test_validate_save_settings_unwritable_dir(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o000)
    config = {
        "save.directory": str(locked),
        "save.filename_format": "shot_%Y.png",
        "save.format": "PNG",
    }
    warnings = cfg.validate_save_settings(config)
    assert any("not writable" in w for w in warnings)
    locked.chmod(0o755)


def test_validate_shortcuts_ok_with_defaults():
    assert cfg.validate_shortcuts({}) == []


def test_validate_shortcuts_ok_with_custom_binding():
    assert cfg.validate_shortcuts({"shortcuts.save": "Ctrl+Alt+J"}) == []


def test_validate_shortcuts_rejects_unparsable():
    warnings = cfg.validate_shortcuts({"shortcuts.save": "garbage"})
    assert len(warnings) == 1
    assert "shortcuts.save" in warnings[0]


def test_validate_shortcuts_rejects_empty():
    warnings = cfg.validate_shortcuts({"shortcuts.copy": ""})
    assert len(warnings) == 1
    assert "shortcuts.copy" in warnings[0]


def test_validate_shortcuts_detects_duplicates_case_insensitively():
    warnings = cfg.validate_shortcuts({"shortcuts.save": "Ctrl+S", "shortcuts.copy": "ctrl+S"})
    assert len(warnings) == 1
    assert "shortcuts.copy" in warnings[0]
    assert "shortcuts.save" in warnings[0]
