#!/usr/bin/env python3
"""Dependency-free benchmark harness for ChamelShot (stdlib only).

Usage:
  uv run python scripts/bench.py [version|imports|gui_import|daemon|capture|wheel|all]

`capture` needs a live Wayland compositor with grim/slurp (runs the daemon
offscreen, so no windows flash). `daemon` uses an offscreen Qt platform by
default so no tray icon or launcher appears; --live opts into the real
session (tray icon registers, launcher may flash).

Kept out of the pytest suite on purpose: it drives a live session.
"""

import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "main.py"
HISTORY_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "chamelshot" / "history"


def _env(**extra):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.update(extra)
    return env


def _best_of(n, fn):
    best = None
    for _ in range(n):
        elapsed = fn()
        if best is None or elapsed < best:
            best = elapsed
    return best


def bench_version(runs=3):
    t = _best_of(runs, lambda: _time(["--version"]))
    print(f"cli_version_ms = {t:.0f}")


def _time(cli_args):
    start = time.perf_counter()
    subprocess.run(
        [sys.executable, str(MAIN), *cli_args],
        cwd=ROOT,
        env=_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    return (time.perf_counter() - start) * 1000


def bench_gui_import(runs=3):
    code = "import time; t=time.perf_counter(); import main; main._load_gui(); print((time.perf_counter()-t)*1000)"
    t = _best_of(
        runs,
        lambda: float(
            subprocess.run(
                [sys.executable, "-c", code],
                cwd=ROOT,
                env=_env(),
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            ).stdout.strip()
            or "0"
        ),
    )
    print(f"gui_import_ms = {t:.0f}")


def bench_imports(top_n=15):
    code = "import main; main._load_gui()"
    out = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", code],
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        text=True,
        check=False,
    ).stderr
    rows = []
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            continue
        try:
            self_us = float(parts[0].replace("import time:", "").strip())
            cum_us = float(parts[1].strip())
        except ValueError:
            continue
        rows.append((cum_us / 1000, self_us / 1000, parts[2].strip()))
    rows.sort(reverse=True)
    print("import_profile_ms (cumulative | self | module):")
    for cum, self_s, name in rows[:top_n]:
        print(f"  {cum:8.1f} | {self_s:6.1f} | {name}")


def _ping():
    sys.path.insert(0, str(ROOT))
    import config as cfg
    import ipc

    return ipc.send_command(cfg.IPC_SOCKET_PATH, "ping")


def _rss_kb(pid):
    try:
        status = Path(f"/proc/{pid}/status").read_text()
    except OSError:
        return None
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return None


def bench_daemon(live=False):
    if _ping():
        print("daemon_start_ms = skipped (a daemon is already running)")
        return
    platform = [] if live else ["QT_QPA_PLATFORM=offscreen"]
    env = _env()
    if platform:
        key, _, value = platform[0].partition("=")
        env[key] = value
    err = Path("/tmp/chamelshot-bench-daemon.err")
    proc = subprocess.Popen(
        [sys.executable, str(MAIN)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=err.open("w"),
    )
    start = time.perf_counter()
    ready_at = None
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if _ping():
            ready_at = time.perf_counter()
            break
        if proc.poll() is not None:
            break
        time.sleep(0.02)
    rss = _rss_kb(proc.pid) if ready_at else None
    if ready_at:
        print(f"daemon_start_ms = {(ready_at - start) * 1000:.0f}")
        print(f"daemon_rss_kb = {rss}")
        _ping_quit()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    else:
        print("daemon_start_ms = failed (see /tmp/chamelshot-bench-daemon.err)")
        proc.kill()
        print(err.read_text()[:500])


def _ping_quit():
    sys.path.insert(0, str(ROOT))
    import config as cfg
    import ipc

    ipc.send_command(cfg.IPC_SOCKET_PATH, "quit")


def _capture_env(td: Path) -> tuple[subprocess.Popen, Path, Path]:
    """Spawn a daemon on a hermetic temp HOME; returns (proc, sock, history)."""
    conf = td / ".config" / "chamelshot"
    conf.mkdir(parents=True)
    (conf / "config.toml").write_text(
        '[general]\nauto_save = true\n\n[save]\ndirectory = "' + str(td / "shots") + '"\n'
    )
    home_cache = td / ".cache" / "chamelshot"
    home_cache.mkdir(parents=True)
    sock = home_cache / "daemon.sock"
    history = home_cache / "history"
    history.mkdir(parents=True)
    proc = subprocess.Popen(
        [sys.executable, str(MAIN)],
        cwd=ROOT,
        env=_env(HOME=str(td)),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc, sock, history


def _capture_send(sock: Path, cmd: str = "capture-fullscreen") -> bool:
    sys.path.insert(0, str(ROOT))
    import ipc

    return ipc.send_command(str(sock), cmd)


def _wait_shot(history: Path, timeout_s: float) -> float | None:
    """Poll for a new screenshot in the temp history; returns perf_counter time."""
    before = set(history.glob("screenshot_*.png"))
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if len(set(history.glob("screenshot_*.png"))) > len(before):
            return time.perf_counter()
        time.sleep(0.02)
    return None


def _stop_daemon(proc, sock: Path):
    _capture_send(sock, "quit")
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def bench_capture(timeout_s=10):
    """Hot end-to-end latency: daemon already up, keybind→saved-shot.

    Runs the daemon with auto_save=true so every capture lands a file in the
    temp history dir — the only externally observable end of the pipeline.
    Needs a live Wayland compositor for grim.
    """
    if not os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("WAYLAND_SOCKET"):
        print("capture_ms = skipped (no Wayland session)")
        return
    td = Path(tempfile.mkdtemp(prefix="chamelshot-bench-"))
    try:
        proc, sock, history = _capture_env(td)
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if _capture_send(sock, "ping"):
                    break
                if proc.poll() is not None:
                    print("capture_ms = failed (daemon exited early)")
                    return
                time.sleep(0.02)
            # Ping answers from the IPC accept loop, which starts before the Qt
            # main loop; wait for the daemon to be fully settled so this metric
            # is a true hot-keybind latency, not residual startup.
            time.sleep(2)
            start = time.perf_counter()
            _capture_send(sock, "capture-fullscreen")
            shot_at = _wait_shot(history, timeout_s)
            if shot_at:
                print(f"capture_ms = {(shot_at - start) * 1000:.0f} (hot: keybind → screenshot saved)")
            else:
                print("capture_ms = timed out (no screenshot landed in history)")
            _stop_daemon(proc, sock)
        finally:
            if proc.poll() is None:
                proc.kill()
    finally:
        shutil.rmtree(td, ignore_errors=True)


def bench_capture_cold(timeout_s=15):
    """Cold end-to-end latency: no daemon running, keybind→saved-shot.

    The stopwatch starts at process spawn and the capture command is retried
    until the IPC socket accepts it, so the full daemon cold start (the G3
    target) is included. Same end marker as the hot metric.
    """
    if not os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("WAYLAND_SOCKET"):
        print("cold_capture_ms = skipped (no Wayland session)")
        return
    td = Path(tempfile.mkdtemp(prefix="chamelshot-bench-"))
    try:
        start = time.perf_counter()
        proc, sock, history = _capture_env(td)
        try:
            deadline = time.monotonic() + timeout_s
            sent = False
            while time.monotonic() < deadline:
                if _capture_send(sock, "capture-fullscreen"):
                    sent = True
                    break
                if proc.poll() is not None:
                    print("cold_capture_ms = failed (daemon exited early)")
                    return
                time.sleep(0.05)
            if not sent:
                print("cold_capture_ms = timed out (IPC never accepted)")
                return
            shot_at = _wait_shot(history, timeout_s)
            if shot_at:
                print(f"cold_capture_ms = {(shot_at - start) * 1000:.0f} (cold: keybind → screenshot saved)")
            else:
                print("cold_capture_ms = timed out (no screenshot landed in history)")
            _stop_daemon(proc, sock)
        finally:
            if proc.poll() is None:
                proc.kill()
    finally:
        shutil.rmtree(td, ignore_errors=True)


def bench_wheel():
    wheels = sorted((ROOT / "dist").glob("chamelshot-*.whl")) if (ROOT / "dist").is_dir() else []
    if not wheels:
        print("wheel_kb = not-found (no dist/chamelshot-*.whl)")
        return
    newest = wheels[-1]
    kb = newest.stat().st_size / 1024
    print(f"wheel_kb = {kb:.0f} ({newest.name})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "what",
        nargs="?",
        default="all",
        choices=["all", "version", "imports", "gui_import", "daemon", "capture", "capture_cold", "wheel"],
    )
    parser.add_argument("--live", action="store_true", help="run the daemon on the real session (tray icon + launcher)")
    args = parser.parse_args()

    print(f"# chamelshot bench — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# python: {sys.version.split()[0]} · repo: {ROOT}")
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True)

    all_steps = ["version", "imports", "gui_import", "daemon", "capture", "capture_cold", "wheel"]
    steps = all_steps if args.what == "all" else [args.what]
    for step in steps:
        if step == "version":
            bench_version()
        elif step == "imports":
            bench_imports()
        elif step == "gui_import":
            bench_gui_import()
        elif step == "daemon":
            bench_daemon(live=args.live)
        elif step == "capture":
            bench_capture()
        elif step == "capture_cold":
            bench_capture_cold()
        elif step == "wheel":
            bench_wheel()


if __name__ == "__main__":
    main()
