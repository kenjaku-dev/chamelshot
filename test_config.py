import os

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
    assert "mode = \"fullscreen\"" in written
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
