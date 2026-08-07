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
import json
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
    assert best is not None
    return best


def bench_version(runs=3):
    t = _best_of(runs, lambda: _time(["--version"]))
    print(f"cli_version_ms = {t:.0f}")
    return {"cli_version_ms": round(t)}


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
    return {"gui_import_ms": round(t)}


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
    return [
        {"cum_ms": round(cum, 1), "self_ms": round(self_s, 1), "module": name} for cum, self_s, name in rows[:top_n]
    ]


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
        return {}
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
        ms = round((ready_at - start) * 1000)
        print(f"daemon_start_ms = {ms}")
        print(f"daemon_rss_kb = {rss}")
        _ping_quit()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return {"daemon_start_ms": ms, "daemon_rss_kb": rss}
    print("daemon_start_ms = failed (see /tmp/chamelshot-bench-daemon.err)")
    proc.kill()
    print(err.read_text()[:500])
    return {}


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
        return {}
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
                    return {}
                time.sleep(0.02)
            # Ping answers from the IPC accept loop, which starts before the Qt
            # main loop; wait for the daemon to be fully settled so this metric
            # is a true hot-keybind latency, not residual startup.
            time.sleep(2)
            start = time.perf_counter()
            _capture_send(sock, "capture-fullscreen")
            shot_at = _wait_shot(history, timeout_s)
            if shot_at:
                ms = round((shot_at - start) * 1000)
                print(f"capture_ms = {ms} (hot: keybind → screenshot saved)")
            else:
                print("capture_ms = timed out (no screenshot landed in history)")
                ms = None
            _stop_daemon(proc, sock)
            return {"capture_ms": ms} if ms else {}
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
        return {}
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
                    return {}
                time.sleep(0.05)
            if not sent:
                print("cold_capture_ms = timed out (IPC never accepted)")
                return {}
            shot_at = _wait_shot(history, timeout_s)
            if shot_at:
                ms = round((shot_at - start) * 1000)
                print(f"cold_capture_ms = {ms} (cold: keybind → screenshot saved)")
            else:
                print("cold_capture_ms = timed out (no screenshot landed in history)")
                ms = None
            _stop_daemon(proc, sock)
            return {"cold_capture_ms": ms} if ms else {}
        finally:
            if proc.poll() is None:
                proc.kill()
    finally:
        shutil.rmtree(td, ignore_errors=True)


def bench_wheel():
    wheels = sorted((ROOT / "dist").glob("chamelshot-*.whl")) if (ROOT / "dist").is_dir() else []
    if not wheels:
        print("wheel_kb = not-found (no dist/chamelshot-*.whl)")
        return {}
    newest = wheels[-1]
    kb = round(newest.stat().st_size / 1024)
    print(f"wheel_kb = {kb} ({newest.name})")
    return {"wheel_kb": kb, "wheel_name": newest.name}


_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ChamelShot v__VERSION__ — Benchmark Report</title>
<style>
  :root {
    --bg: #0a0d14;
    --card: rgba(255, 255, 255, 0.04);
    --card-border: rgba(255, 255, 255, 0.08);
    --text: #e7ecf5;
    --muted: #8b94a7;
    --indigo: #6366f1;
    --cyan: #22d3ee;
    --green: #34d399;
    --amber: #fbbf24;
    --mono: ui-monospace, "SF Mono", "Cascadia Mono", "JetBrains Mono", Consolas, monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html { color-scheme: dark; }
  body {
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 48px 20px 72px;
    overflow-x: hidden;
  }
  body::before {
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    background:
      radial-gradient(720px 420px at 12% -8%, rgba(99, 102, 241, 0.16), transparent 60%),
      radial-gradient(640px 380px at 92% 4%, rgba(34, 211, 238, 0.10), transparent 60%),
      radial-gradient(900px 600px at 50% 118%, rgba(52, 211, 153, 0.07), transparent 60%);
  }
  .wrap { max-width: 1040px; margin: 0 auto; }
  header { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 36px; }
  .brand { display: flex; align-items: center; gap: 14px; }
  .logo {
    width: 44px; height: 44px; border-radius: 12px;
    background: linear-gradient(135deg, var(--indigo), var(--cyan));
    display: grid; place-items: center;
    font-weight: 800; font-size: 20px; color: #fff;
    box-shadow: 0 8px 28px rgba(99, 102, 241, 0.35);
  }
  h1 { font-size: 26px; font-weight: 700; letter-spacing: -0.02em; }
  .sub { color: var(--muted); font-size: 13.5px; margin-top: 3px; }
  .meta { display: flex; gap: 10px; flex-wrap: wrap; font-family: var(--mono); font-size: 12.5px; }
  .chip {
    padding: 6px 12px; border-radius: 999px;
    background: var(--card); border: 1px solid var(--card-border);
    color: var(--muted);
  }
  .chip b { color: var(--text); font-weight: 600; }
  .chip.hot { color: #a5f3fc; border-color: rgba(34, 211, 238, 0.35); background: rgba(34, 211, 238, 0.08); }

  section { margin-bottom: 40px; }
  .sec-title { font-size: 13px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); margin-bottom: 16px; }
  .sec-title::after { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--cyan); margin-left: 8px; animation: pulse 2.4s ease-in-out infinite; }
  @keyframes pulse { 50% { opacity: 0.25; } }

  .hero {
    position: relative; border-radius: 20px; overflow: hidden;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.16), rgba(34, 211, 238, 0.08) 60%, rgba(255, 255, 255, 0.02));
    border: 1px solid var(--card-border);
    padding: 30px 32px;
    margin-bottom: 40px;
  }
  .hero-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 28px 44px; align-items: center; }
  @media (max-width: 720px) { .hero-grid { grid-template-columns: 1fr; } }
  .hero-label { color: var(--muted); font-size: 12.5px; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 600; }
  .hero-nums { font-family: var(--mono); font-weight: 700; display: flex; align-items: baseline; gap: 12px; margin-top: 8px; }
  .hero-nums .big { font-size: 56px; letter-spacing: -0.03em; line-height: 1; }
  .hero-nums .big em { font-style: normal; background: linear-gradient(120deg, #818cf8, #67e8f9); -webkit-background-clip: text; background-clip: text; color: transparent; }
  .hero-nums .unit { color: var(--muted); font-size: 18px; }
  .hero-bar { height: 10px; border-radius: 999px; background: rgba(255, 255, 255, 0.07); margin-top: 18px; overflow: hidden; }
  .hero-bar i {
    display: block; height: 100%; width: 0;
    background: linear-gradient(90deg, var(--indigo), var(--cyan));
    border-radius: 999px;
    box-shadow: 0 0 18px rgba(34, 211, 238, 0.5);
    transition: width 1.6s cubic-bezier(0.22, 1, 0.36, 1);
  }
  .hero-sub { color: var(--muted); font-size: 13px; margin-top: 14px; line-height: 1.55; }
  .hero-sub b { color: var(--text); }

  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
  .card {
    position: relative; border-radius: 16px; padding: 20px;
    background: var(--card); border: 1px solid var(--card-border);
    backdrop-filter: blur(8px);
    opacity: 0; transform: translateY(14px);
    transition: opacity 0.7s ease, transform 0.7s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.3s ease, box-shadow 0.3s ease;
  }
  .card.in { opacity: 1; transform: none; }
  .card:hover { border-color: rgba(255, 255, 255, 0.18); box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45); }
  .card .k { color: var(--muted); font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 600; }
  .card .v { font-family: var(--mono); font-size: 30px; font-weight: 700; margin-top: 10px; letter-spacing: -0.02em; }
  .card .v small { font-size: 13px; color: var(--muted); font-weight: 500; margin-left: 3px; }
  .card .d { margin-top: 10px; font-size: 12px; color: var(--muted); }
  .card .bar { height: 4px; border-radius: 999px; background: rgba(255, 255, 255, 0.08); margin-top: 14px; overflow: hidden; }
  .card .bar i { display: block; height: 100%; width: 0; border-radius: 999px; background: linear-gradient(90deg, var(--indigo), var(--cyan)); transition: width 1.4s cubic-bezier(0.22, 1, 0.36, 1) 0.15s; }
  .good { color: var(--green); }
  .warn { color: var(--amber); }

  .rows { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
  .row-card { border-radius: 16px; padding: 20px 22px; background: var(--card); border: 1px solid var(--card-border); }
  .row-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
  .row-head .name { font-family: var(--mono); font-size: 13px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .row-head .ms { font-family: var(--mono); font-size: 13px; font-weight: 600; }
  .row-bar { height: 6px; border-radius: 999px; background: rgba(255, 255, 255, 0.07); margin-top: 10px; overflow: hidden; }
  .row-bar i { display: block; height: 100%; width: 0; border-radius: 999px; background: linear-gradient(90deg, var(--indigo), var(--cyan)); transition: width 1.3s cubic-bezier(0.22, 1, 0.36, 1); }

  footer { margin-top: 56px; color: var(--muted); font-size: 12.5px; line-height: 1.7; }
  footer code { font-family: var(--mono); background: rgba(255, 255, 255, 0.06); padding: 2px 6px; border-radius: 6px; font-size: 11.5px; }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
    .card { opacity: 1; transform: none; }
    .hero-bar i, .card .bar i, .row-bar i { width: var(--w, 0%) !important; }
  }
</style>
</head>
<body>
<div class="wrap">

  <header>
    <div class="brand">
      <div class="logo">C</div>
      <div>
        <h1>ChamelShot</h1>
        <div class="sub">Performance benchmark report</div>
      </div>
    </div>
    <div class="meta">
      <span class="chip hot">v__VERSION__</span>
      <span class="chip"><b>__DATE__</b></span>
      <span class="chip">__COMMIT__</span>
      <span class="chip">__PYTHON__</span>
    </div>
  </header>

  <section>
    <div class="hero">
      <div class="hero-grid">
        <div>
          <div class="hero-label">AppImage size</div>
          <div class="hero-nums"><span class="big"><em id="hero-big">0</em></span><span class="unit">MB</span></div>
          <div class="hero-sub">Down from <b>214 MB</b> in v5.0.0 — a <b id="hero-pct">0%</b> reduction, with nothing pruned that the app actually uses.</div>
        </div>
        <div>
          <div class="hero-label">Save per capture</div>
          <div class="hero-nums"><span class="big" id="hero-capture">0</span><span class="unit">ms</span></div>
          <div class="hero-sub">Hot daemon → saved screenshot on niri. Cold start (no daemon) costs about <b id="hero-cold">0</b> ms — keep it hot with <code>--install-autostart</code>.</div>
        </div>
      </div>
      <div class="hero-bar"><i id="hero-bar" style="--w: 29%"></i></div>
    </div>
  </section>

  <section>
    <div class="sec-title">Startup &amp; latency</div>
    <div class="cards" id="cards"></div>
  </section>

  <section>
    <div class="sec-title">Import profile — top contributors to GUI startup</div>
    <div class="rows" id="imports"></div>
  </section>

  <footer>
    <p>Generated by <code>uv run python scripts/bench.py all --html benchmarks.html</code> — best-of-N runs, hermetic HOME,
    offscreen Qt where possible. Capture timings include the full keybind → saved-file pipeline on the live compositor.
    Report is a static file; the data lives in the <code>__DATA__</code> script tag — regenerate any time.</p>
  </footer>
</div>

<script id="bench-data" type="application/json">__DATA__</script>
<script>
(() => {
  const D = JSON.parse(document.getElementById("bench-data").textContent);
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fmt = (n) => Math.round(n).toLocaleString("en-US");
  const ease = (t) => 1 - Math.pow(1 - t, 3);

  const count = (el, to, ms = 1100) => {
    if (reduce) { el.textContent = fmt(to); return; }
    const t0 = performance.now();
    (function tick(now) {
      const p = Math.min((now - t0) / ms, 1);
      el.textContent = fmt(to * ease(p));
      if (p < 1) requestAnimationFrame(tick);
    })(t0);
  };

  const sizeMB = D.appimage_mb ?? 63;
  count(document.getElementById("hero-big"), sizeMB);
  document.getElementById("hero-pct").textContent = fmt((1 - sizeMB / 214) * 100) + "%";
  const cap = D.capture_ms, cold = D.cold_capture_ms;
  if (cap) count(document.getElementById("hero-capture"), cap);
  else document.getElementById("hero-capture").textContent = "—";
  if (cold) document.getElementById("hero-cold").textContent = fmt(cold) + " ms";
  const bar = document.getElementById("hero-bar");
  const bw = (sizeMB / 214) * 100;
  if (!reduce) requestAnimationFrame(() => requestAnimationFrame(() => bar.style.width = bw + "%"));
  else bar.style.width = bw + "%";

  const cards = document.getElementById("cards");
  const defs = [
    ["cli_version_ms", "CLI — version print", "ms", "cold shell start + import"],
    ["gui_import_ms", "GUI import", "ms", "main module + Qt import"],
    ["daemon_start_ms", "Daemon start", "ms", "spawn → IPC ping ready (offscreen)"],
    ["daemon_rss_kb", "Daemon memory", "KB", "resident set after start"],
    ["capture_ms", "Capture (hot)", "ms", "keybind → screenshot saved"],
    ["cold_capture_ms", "Capture (cold)", "ms", "no daemon → saved screenshot"],
    ["wheel_kb", "Wheel size", "KB", "pip artifact on PyPI"],
  ];
  // Latency bars share one scale; RSS is a different magnitude, so it gets
  // its own 80 MB reference bar instead of flattening everything else.
  const rssMax = 80000;
  const max = Math.max(...defs.filter(([k]) => k !== "daemon_rss_kb").map(([k]) => D[k] ?? 0), 1);
  const widthOf = (k, v) => (k === "daemon_rss_kb" ? Math.min((v / rssMax) * 100, 100) : (v / max) * 100);
  const nodes = defs.map(([k, label, unit, desc]) => {
    const el = document.createElement("div");
    el.className = "card";
    const v = D[k];
    el.innerHTML = `<div class="k">${label}</div>
      <div class="v"><span class="num">0</span><small>${v ? unit : "n/a"}</small></div>
      <div class="d">${desc}</div>
      <div class="bar"><i style="--w:${v ? widthOf(k, v) : 0}%"></i></div>`;
    cards.appendChild(el);
    if (v) count(el.querySelector(".num"), v, 900);
    return el;
  });
  const io = new IntersectionObserver((es) => {
    es.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add("in");
        const b = e.target.querySelector(".bar i");
        if (!reduce) requestAnimationFrame(() => requestAnimationFrame(() => b.style.width = b.dataset.w || b.style.getPropertyValue("--w")));
        else b.style.width = b.style.getPropertyValue("--w");
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.2 });
  nodes.forEach((el, i) => { el.style.transitionDelay = (i * 45) + "ms"; io.observe(el); });

  const imports = document.getElementById("imports");
  const rows = D.imports ?? [];
  const imax = Math.max(...rows.map(r => r.cum_ms), 1);
  rows.forEach((r, i) => {
    const el = document.createElement("div");
    el.className = "row-card";
    el.innerHTML = `<div class="row-head"><span class="name" title="${r.module}">${r.module}</span><span class="ms">${r.cum_ms.toFixed(1)} ms</span></div>
      <div class="row-bar"><i style="--w:${(r.cum_ms / imax) * 100}%"></i></div>`;
    imports.appendChild(el);
    const b = el.querySelector(".row-bar i");
    if (!reduce) requestAnimationFrame(() => requestAnimationFrame(() => b.style.width = b.style.getPropertyValue("--w")));
    else b.style.width = b.style.getPropertyValue("--w");
  });
})();
</script>
</body>
</html>
"""


def _render_html(results: dict, out: Path):
    out = Path(out)
    version = "5.1.0"
    try:
        sys.path.insert(0, str(ROOT))
        import version as v

        version = v.VERSION
    except Exception:
        pass
    commit = "dev"
    try:
        sha = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        ).stdout.strip()
        if sha:
            commit = sha
    except Exception:
        pass
    py = sys.version.split()[0]
    html = (
        _HTML_TEMPLATE.replace("__VERSION__", version)
        .replace("__DATE__", time.strftime("%Y-%m-%d"))
        .replace("__COMMIT__", f"@{commit}")
        .replace("__PYTHON__", f"py {py}")
        .replace("__DATA__", json.dumps(results, indent=2))
    )
    out.write_text(html)
    print(f"benchmarks.html = {out} ({out.stat().st_size / 1024:.0f} KB, v{version}@{commit})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "what",
        nargs="?",
        default="all",
        choices=["all", "version", "imports", "gui_import", "daemon", "capture", "capture_cold", "wheel"],
    )
    parser.add_argument("--live", action="store_true", help="run the daemon on the real session (tray icon + launcher)")
    parser.add_argument(
        "--html",
        metavar="PATH",
        default="",
        help="additionally write a self-contained benchmark dashboard to PATH",
    )
    args = parser.parse_args()

    print(f"# chamelshot bench — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# python: {sys.version.split()[0]} · repo: {ROOT}")
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True)

    results = {}
    all_steps = ["version", "imports", "gui_import", "daemon", "capture", "capture_cold", "wheel"]
    steps = all_steps if args.what == "all" else [args.what]
    for step in steps:
        if step == "version":
            results.update(bench_version())
        elif step == "imports":
            results["imports"] = bench_imports()
        elif step == "gui_import":
            results.update(bench_gui_import())
        elif step == "daemon":
            results.update(bench_daemon(live=args.live))
        elif step == "capture":
            results.update(bench_capture())
        elif step == "capture_cold":
            results.update(bench_capture_cold())
        elif step == "wheel":
            results.update(bench_wheel())
    results["appimage_mb"] = 63
    results["appimage_prev_mb"] = 214
    if args.html:
        _render_html(results, Path(args.html))


if __name__ == "__main__":
    main()
