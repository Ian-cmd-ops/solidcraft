#!/usr/bin/env python3
"""GPU half of the hard smoke test: drives the SolidCraft desktop app over its control channel.

solidcraft-cli never uses the GPU (it renders with a CPU rasterizer), so GPU use is measured on
the app's viewport. For each scene the app loads a heavy model, then the camera turns a full
circle in small steps while the harness samples GPU busy %, VRAM, RAM and CPU cores. Frames per
second is steps per second of that orbit: each ui.camera request is answered between frames.

Needs a display (a desktop session, or Xvfb for a smoke run without a real GPU).

Usage:
  python3 tools/hardsmoke_app.py --app PATH/solidcraft --out DIR [--steps 360] [--size 1920x1080]
                                 [--baseline DIR/app_results.json]
"""
import argparse
import json
import math
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hardsmoke as hs  # noqa: E402


class Channel:
    def __init__(self, port, token, timeout=120):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.buf = b""
        self.token = token
        self.n = 0

    def call(self, method, params=None):
        self.n += 1
        req = {"id": self.n, "method": method, "params": params or {}}
        if self.token:
            req["token"], self.token = self.token, None
        self.sock.sendall((json.dumps(req) + "\n").encode())
        while b"\n" not in self.buf:
            chunk = self.sock.recv(1 << 20)
            if not chunk:
                raise ConnectionError("the app closed the control channel")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        reply = json.loads(line)
        if not reply.get("ok"):
            raise RuntimeError(f"{method}: {reply.get('error')}")
        return reply.get("result")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def scenes(out):
    torus = out / "torus_1M.stl"
    if not torus.exists():
        hs.write_stl(torus, hs.torus(30.0, 8.0, 1000, 500))
    return [
        ("plate_400_holes", [("engine.execute", {"command": c["command"], "params": c["params"]}) for c in hs.PLATE]),
        ("torus_1M_tris", [("engine.execute", {"command": "file.insert_mesh", "params": {"path": str(torus)}})]),
        ("plate_and_torus", [("engine.execute", {"command": c["command"], "params": c["params"]}) for c in hs.PLATE]
         + [("engine.execute", {"command": "file.insert_mesh", "params": {"path": str(torus)}})]),
    ]


def run_scene(app, name, steps_list, out, n_steps, size):
    port = free_port()
    token = secrets.token_hex(32)
    env = dict(os.environ, SOLIDCRAFT_CONTROL_TOKEN=token)
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    log = open(d / "app.log", "w")
    proc = subprocess.Popen([app, "--control", str(port)], env=env, stdout=log, stderr=subprocess.STDOUT)
    sampler = hs.Sampler(proc.pid)
    sampler.start()
    res = {"name": name}
    t0 = time.monotonic()
    try:
        ch = None
        for _ in range(240):
            if proc.poll() is not None:
                raise RuntimeError(f"the app exited with {proc.returncode} before listening (see {d / 'app.log'})")
            try:
                ch = Channel(port, token)
                break
            except OSError:
                time.sleep(0.25)
        if ch is None:
            raise RuntimeError("the app did not open its control port within 60 s")
        info = ch.call("ui.inspect")
        res["startup_s"] = round(time.monotonic() - t0, 2)
        res["renderer"] = info.get("renderer")
        w, h = (int(x) for x in size.split("x"))
        try:
            ch.call("ui.resize", {"width": w, "height": h})
        except RuntimeError as e:
            res["resize_error"] = str(e)
        t1 = time.monotonic()
        for method, params in steps_list:
            ch.call(method, params)
        ch.call("ui.camera", {"fit": True})
        ch.call("ui.screenshot", {"path": str(d / "first_frame.png")})
        res["load_s"] = round(time.monotonic() - t1, 2)
        cam = ch.call("ui.camera", {})
        yaw0 = cam.get("yaw", 0.0) if isinstance(cam, dict) else 0.0
        before = (sampler.peak_rss, sampler.gpu_util, sampler.gpu_mem)
        sampler.gpu_util = None
        cpu0, w0 = sampler.ticks(hs.tree_pids(proc.pid)), time.monotonic()
        for k in range(n_steps):
            ch.call("ui.camera", {"yaw": yaw0 + 2 * math.pi * (k + 1) / n_steps})
            if k % 60 == 0:
                print(f"      orbit {k}/{n_steps}", flush=True)
        orbit = time.monotonic() - w0
        cpu = (sampler.ticks(hs.tree_pids(proc.pid)) - cpu0) / hs.TICK
        ch.call("ui.screenshot", {"path": str(d / "last_frame.png")})
        res.update({
            "orbit_s": round(orbit, 2), "fps": round(n_steps / orbit, 1) if orbit > 0 else None,
            "orbit_avg_cores": round(cpu / orbit, 2) if orbit > 0 else None,
            "orbit_gpu_util_pct": sampler.gpu_util, "gpu_mem_mb": sampler.gpu_mem,
            "peak_rss_mb": round(sampler.peak_rss / 2**20, 1), "rss_before_orbit_mb": round(before[0] / 2**20, 1),
        })
        info = ch.call("ui.inspect")
        res["timings"] = info.get("timings")
        try:
            ch.call("app.quit", {"force": True})
        except (RuntimeError, ConnectionError, OSError):
            pass
        res["verdict"] = "PASS"
    except Exception as e:  # report every failure as a result, never stop the run
        res["verdict"] = "FAIL"
        res["error"] = f"{type(e).__name__}: {e}"
    finally:
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        sampler.stop_.set()
        sampler.join()
        log.close()
        res["exit_code"] = proc.returncode
        crashed = "panicked" in (d / "app.log").read_text(errors="replace")
        if crashed:
            res["verdict"] = "FAIL"
            res["error"] = (res.get("error", "") + " panic in app.log").strip()
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--steps", type=int, default=360)
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--only", default="")
    ap.add_argument("--baseline")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    only = {x for x in a.only.split(",") if x}
    gpu = "nvidia-smi" if hs.shutil.which("nvidia-smi") else (
        "amdgpu sysfs" if any(Path("/sys/class/drm").glob("card*/device/gpu_busy_percent")) else "none")
    print(f"[{time.strftime('%H:%M:%S')}] app mode on {os.uname().nodename}, {os.cpu_count()} CPUs, GPU sampling: {gpu}, "
          f"display {os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY') or 'NONE'}", flush=True)
    base = {}
    if a.baseline and Path(a.baseline).exists():
        base = {r["name"]: r for r in json.loads(Path(a.baseline).read_text())["results"]}
    results = []
    for name, steps in scenes(out):
        if only and name not in only:
            continue
        print(f"[{time.strftime('%H:%M:%S')}] {name}: start app, load, orbit {a.steps} steps at {a.size}", flush=True)
        r = run_scene(a.app, name, steps, out, a.steps, a.size)
        b = base.get(name)
        flags = []
        if b and b.get("fps") and r.get("fps") and r["fps"] < 0.8 * b["fps"]:
            flags.append(f"SLOWER fps {b['fps']}->{r['fps']}")
        if b and b.get("peak_rss_mb") and r.get("peak_rss_mb") and r["peak_rss_mb"] > 1.25 * b["peak_rss_mb"]:
            flags.append(f"HUNGRIER {b['peak_rss_mb']}->{r['peak_rss_mb']} MB")
        r["flags"] = flags
        results.append(r)
        if r["verdict"] == "PASS":
            print(f"    PASS load {r['load_s']}s  {r['fps']} fps  cores {r['orbit_avg_cores']}  "
                  f"gpu {r['orbit_gpu_util_pct']}% vram {r['gpu_mem_mb']}MB  ram {r['peak_rss_mb']}MB  "
                  f"renderer {json.dumps(r.get('renderer'))[:80]} {' '.join(flags)}", flush=True)
        else:
            print(f"    FAIL {r.get('error', '')[:200]}", flush=True)
    (out / "app_results.json").write_text(json.dumps({"host": os.uname().nodename, "gpu_tool": gpu, "size": a.size,
                                                      "steps": a.steps, "results": results}, indent=1))
    fails = sum(r["verdict"] == "FAIL" for r in results)
    print(f"\nAPP SUMMARY pass {len(results) - fails}, fail {fails} -> {out / 'app_results.json'}", flush=True)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
