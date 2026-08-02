import sys

import proc


def test_non_frozen_keeps_env():
    assert not getattr(sys, "frozen", False)
    assert proc.env() == dict(__import__("os").environ)


def test_frozen_strips_bundle_vars():
    import os

    old_frozen = getattr(sys, "frozen", None)
    old_ld = os.environ.get("LD_LIBRARY_PATH")
    try:
        sys.frozen = True
        os.environ["LD_LIBRARY_PATH"] = "/bundle/lib"
        os.environ["LD_PRELOAD"] = "/bundle/lib/foo.so"
        clean = proc.env()
        assert "LD_LIBRARY_PATH" not in clean
        assert "LD_PRELOAD" not in clean
    finally:
        setattr(sys, "frozen", old_frozen)
        if old_ld is None:
            os.environ.pop("LD_LIBRARY_PATH", None)
        else:
            os.environ["LD_LIBRARY_PATH"] = old_ld
        os.environ.pop("LD_PRELOAD", None)


def test_frozen_restores_original():
    import os

    old_frozen = getattr(sys, "frozen", None)
    old_ld = os.environ.get("LD_LIBRARY_PATH")
    old_orig = os.environ.get("LD_LIBRARY_PATH_ORIG")
    try:
        sys.frozen = True
        os.environ["LD_LIBRARY_PATH"] = "/bundle/lib"
        os.environ["LD_LIBRARY_PATH_ORIG"] = "/usr/lib:/lib"
        clean = proc.env()
        assert clean.get("LD_LIBRARY_PATH") == "/usr/lib:/lib"
    finally:
        setattr(sys, "frozen", old_frozen)
        if old_ld is None:
            os.environ.pop("LD_LIBRARY_PATH", None)
        else:
            os.environ["LD_LIBRARY_PATH"] = old_ld
        if old_orig is None:
            os.environ.pop("LD_LIBRARY_PATH_ORIG", None)
        else:
            os.environ["LD_LIBRARY_PATH_ORIG"] = old_orig
