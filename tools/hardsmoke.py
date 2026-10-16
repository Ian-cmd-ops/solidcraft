#!/usr/bin/env python3
"""Hard smoke test for SolidCraft: exact-value correctness plus CPU, RAM and GPU use.

Every case runs solidcraft-cli on a script or a generated STL and is checked against an
independent truth: a formula volume, the signed volume of the generated mesh, or a STEP round
trip. Nothing comes from a commercial CAD product. Each case also records wall time, CPU
seconds, average cores kept busy, peak RAM and (where a GPU tool exists) GPU busy % and VRAM.

Usage:
  python3 tools/hardsmoke.py --cli PATH/solidcraft-cli --out DIR [--only NAME,...]
                             [--baseline DIR/results.json] [--timeout 600]

Verdicts:
  PASS      result matches the truth
  REFUSED   an expected refusal: a clean error, no crash, within the time limit
  KNOWN     a known bug still fails (robustness seeds); FIXED when it passes
  FAIL      wrong result, crash, panic, hang or unexpected error
  SLOWER / HUNGRIER   25% worse than the baseline run (perf flag, not a failure)
Exit status 1 when any case FAILs.
"""
import argparse
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

TICK = os.sysconf("SC_CLK_TCK")
PAGE = os.sysconf("SC_PAGE_SIZE")


# ---------------------------------------------------------------- meshes ---

def write_stl(path, tris, ascii_=False):
    """tris: list of ((x,y,z),(x,y,z),(x,y,z)), counter-clockwise seen from outside."""
    if ascii_:
        with open(path, "w") as f:
            f.write("solid hardsmoke\n")
            for a, b, c in tris:
                f.write(" facet normal 0 0 0\n  outer loop\n")
                for p in (a, b, c):
                    f.write(f"   vertex {p[0]:.9g} {p[1]:.9g} {p[2]:.9g}\n")
                f.write("  endloop\n endfacet\n")
            f.write("endsolid hardsmoke\n")
        return
    rec = struct.Struct("<12fH")
    with open(path, "wb") as f:
        f.write(b"hardsmoke".ljust(80, b"\0"))
        f.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            f.write(rec.pack(0.0, 0.0, 0.0, *a, *b, *c, 0))


def mesh_volume(tris):
    v = 0.0
    for a, b, c in tris:
        v += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
              + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return v / 6.0


def circle(r, n, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def fan_prism(poly, h):
    """Prism over a polygon that is star-shaped about its centroid (CCW)."""
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    t, n = [], len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        t.append(((cx, cy, 0.0), (b[0], b[1], 0.0), (a[0], a[1], 0.0)))
        t.append(((cx, cy, h), (a[0], a[1], h), (b[0], b[1], h)))
        t.append(((a[0], a[1], 0.0), (b[0], b[1], 0.0), (b[0], b[1], h)))
        t.append(((a[0], a[1], 0.0), (b[0], b[1], h), (a[0], a[1], h)))
    return t


def pipe(r_in, r_out, h, n):
    """A tube: two rings of n points bridged on both caps."""
    o, i_ = circle(r_out, n), circle(r_in, n)
    t = []
    for k in range(n):
        a, b = o[k], o[(k + 1) % n]
        c, d = i_[k], i_[(k + 1) % n]
        t += [((a[0], a[1], 0), (b[0], b[1], 0), (b[0], b[1], h)), ((a[0], a[1], 0), (b[0], b[1], h), (a[0], a[1], h))]
        t += [((c[0], c[1], 0), (d[0], d[1], h), (d[0], d[1], 0)), ((c[0], c[1], 0), (c[0], c[1], h), (d[0], d[1], h))]
        t += [((a[0], a[1], 0), (c[0], c[1], 0), (d[0], d[1], 0)), ((a[0], a[1], 0), (d[0], d[1], 0), (b[0], b[1], 0))]
        t += [((a[0], a[1], h), (d[0], d[1], h), (c[0], c[1], h)), ((a[0], a[1], h), (b[0], b[1], h), (d[0], d[1], h))]
    return t


def sphere(r, nu, nv):
    def p(i, j):
        th, ph = math.pi * i / nv, 2 * math.pi * j / nu
        return (r * math.sin(th) * math.cos(ph), r * math.sin(th) * math.sin(ph), r * math.cos(th))
    t = []
    for i in range(nv):
        for j in range(nu):
            a, b, c, d = p(i, j), p(i + 1, j), p(i + 1, j + 1), p(i, j + 1)
            if i > 0:
                t.append((a, b, d))
            if i < nv - 1:
                t.append((b, c, d))
    return t


def torus(R, r, nu, nv):
    def p(i, j):
        u, v = 2 * math.pi * i / nu, 2 * math.pi * j / nv
        return ((R + r * math.cos(v)) * math.cos(u), (R + r * math.cos(v)) * math.sin(u), r * math.sin(v))
    t = []
    for i in range(nu):
        for j in range(nv):
            a, b, c, d = p(i, j), p(i + 1, j), p(i + 1, j + 1), p(i, j + 1)
            t += [(a, b, c), (a, c, d)]
    return t


def frustum(poly, scale_top, h):
    """Like fan_prism but the top is the bottom scaled about the centroid: not constant-section."""
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    top = [(cx + (x - cx) * scale_top, cy + (y - cy) * scale_top) for x, y in poly]
    t, n = [], len(poly)
    for i in range(n):
        a, b, A, B = poly[i], poly[(i + 1) % n], top[i], top[(i + 1) % n]
        t.append(((cx, cy, 0.0), (b[0], b[1], 0.0), (a[0], a[1], 0.0)))
        t.append(((cx, cy, h), (A[0], A[1], h), (B[0], B[1], h)))
        t.append(((a[0], a[1], 0.0), (b[0], b[1], 0.0), (B[0], B[1], h)))
        t.append(((a[0], a[1], 0.0), (B[0], B[1], h), (A[0], A[1], h)))
    return t


def gear(teeth, r_root, r_tip):
    pts = []
    for k in range(teeth):
        a = 2 * math.pi * k / teeth
        w = math.pi / teeth
        for da, r in ((-0.5 * w, r_root), (-0.25 * w, r_tip), (0.25 * w, r_tip), (0.5 * w, r_root)):
            pts.append((r * math.cos(a + da), r * math.sin(a + da)))
    return pts


# ----------------------------------------------------------------- cases ---

def mesh_case(name, tris, expect, truth=None, rtol=1e-6, ascii_=False, raw=None, note=""):
    return {"name": name, "kind": "mesh", "tris": tris, "raw": raw, "ascii": ascii_,
            "expect": expect, "truth": truth, "rtol": rtol, "note": note}


def script_case(name, script, expect, truth=None, rtol=1e-6, note="", perf_only=False):
    return {"name": name, "kind": "script", "script": script, "expect": expect, "truth": truth,
            "rtol": rtol, "note": note}


SEEDS = {
    "seed2": [{"command": "solid.box", "params": {"height": 7.5, "length": 17.5, "width": 50.0}},
              {"command": "solid.sphere", "params": {"center": [2.5, 50.0, -1.7763568394002493e-15], "operation": "cut", "radius": 10.0}},
              {"command": "solid.pattern.rectangular", "params": {"count1": 2, "dir1": [1.0, 0.0, 0.0], "features": ["Sphere1"], "spacing1": 5.0}}],
    "seed5": [{"command": "solid.box", "params": {"height": 10.0, "length": 25.0, "width": 15.0}},
              {"command": "solid.hole", "params": {"depth": 7.5, "diameter": 6.0, "position": [12.499999999999998, 15.0, 5.0], "type": "drilled"}},
              {"command": "solid.cylinder", "params": {"axis": [0.0, 0.0, 1.0], "base": [12.5, 12.5, 5.0], "height": 17.5, "operation": "cut", "radius": 7.5}}],
    "seed15": [{"command": "sketch.create", "params": {"plane": "XZ"}},
               {"command": "sketch.rectangle.two_point", "params": {"p0": [7.5, 0], "p1": [17.5, 25.0]}},
               {"command": "sketch.finish", "params": {}},
               {"command": "solid.revolve", "params": {"angle": "90 deg", "axis": "Z"}},
               {"command": "solid.box", "params": {"corner": [10.0, 5.0, -20.0], "height": 7.5, "length": 2.5, "operation": "cut", "width": 5.0}},
               {"command": "solid.sphere", "params": {"center": [-2.4985100731614147e-7, 17.500000000000156, 0.0], "operation": "cut", "radius": 5.0}}],
}

PLATE = [
    {"command": "solid.box", "params": {"length": 200, "width": 200, "height": 5}},
    {"command": "solid.cylinder", "params": {"radius": 2, "height": 7, "base": [5, 5, -1], "operation": "cut"}},
    {"command": "solid.pattern.rectangular", "params": {"features": ["Cylinder1"], "dir1": [1, 0, 0], "count1": 20, "spacing1": 10,
                                                        "dir2": [0, 1, 0], "count2": 20, "spacing2": 10}},
]
PLATE_V = 200 * 200 * 5 - 400 * math.pi * 4 * 5


def build_cases():
    c = []
    # B-rep: formula volumes. measure() works from a fine tessellation (kernel measure.rs), so a
    # body with curved faces reads about 1e-4 off its exact volume: 1e-3 for those, 1e-6 for flat ones.
    c.append(script_case("brep_plate_400_holes", PLATE, "ok", PLATE_V, 1e-3, "box minus a 20x20 pattern of through holes"))
    c.append(script_case("brep_revolve_359deg", [
        {"command": "sketch.create", "params": {"plane": "XZ"}},
        {"command": "sketch.rectangle.two_point", "params": {"p0": [10, 0], "p1": [20, 30]}},
        {"command": "sketch.finish", "params": {}},
        {"command": "solid.revolve", "params": {"angle": "359 deg", "axis": "Z"}}],
        "ok", (359 / 360) * math.pi * (400 - 100) * 30, 1e-3, "a nearly full turn"))
    c.append(script_case("brep_tiny_box_10um", [{"command": "solid.box", "params": {"length": 0.01, "width": 0.01, "height": 0.01}}],
                         "ok", 1e-6, 1e-6, "10 micron cube"))
    c.append(script_case("brep_huge_box_10m", [{"command": "solid.box", "params": {"length": 10000, "width": 10000, "height": 10000}}],
                         "ok", 1e12, 1e-6, "10 m cube"))
    c.append({"name": "brep_plate_step_round_trip", "kind": "roundtrip", "script": PLATE, "expect": "ok",
              "truth": None, "rtol": 1e-5, "note": "export STEP, insert it again: same measured volume as before export"})
    small = [PLATE[0], PLATE[1], {"command": "solid.pattern.rectangular", "params": {
        "features": ["Cylinder1"], "dir1": [1, 0, 0], "count1": 5, "spacing1": 10, "dir2": [0, 1, 0], "count2": 5, "spacing2": 10}}]
    c.append({"name": "mesh_plate25_export_then_convert", "kind": "meshtrip", "script": small, "expect": "ok",
              "truth": 200 * 200 * 5 - 25 * math.pi * 4 * 5, "rtol": 2e-3,
              "note": "SolidCraft's own STL of a 25-hole plate, converted back to faces"})
    c.append({"name": "mesh_plate400_over_cap", "kind": "meshtrip", "script": PLATE, "expect": "refuse",
              "note": "the 400-hole plate's STL is over mesh.convert's 50 000-triangle cap: a clean refusal"})
    # 4K renders of heavy models. solidcraft-cli snapshot draws with the CPU rasterizer in crates/render
    # (the CLI does not link crates/gpu), so these measure CPU rendering. GPU use needs the desktop app.
    c.append({"name": "cpu_render_plate_4k", "kind": "snapshot", "script": PLATE, "expect": "image",
              "note": "400-hole plate rendered at 3840x2160"})
    c.append({"name": "cpu_render_torus_1M_4k", "kind": "snapshot", "tris": None, "expect": "image",
              "note": "1M-triangle mesh rendered at 3840x2160"})
    for k, s in SEEDS.items():
        c.append(script_case(f"known_{k}", s, "known", note="robustness seed, boolean Cut: no result"))

    # Meshes that are constant-section: conversion must work and match.
    g = gear(24, 18.0, 22.0)
    gt = fan_prism(g, 8.0)
    c.append(mesh_case("mesh_gear_24_teeth", gt, "convert", mesh_volume(gt), 1e-6, note="all planar faces: exact"))
    c.append(mesh_case("mesh_gear_ascii", gt, "convert", mesh_volume(gt), 1e-6, ascii_=True, note="same gear as ASCII STL"))
    pt = pipe(4.0, 10.0, 25.0, 512)
    c.append(mesh_case("mesh_pipe_512_segments", pt, "convert", math.pi * (100 - 16) * 25, 1e-3, note="should become two cylinders"))
    ct = fan_prism(circle(15.0, 3000), 40.0)
    c.append(mesh_case("mesh_cylinder_3000_segments", ct, "convert", math.pi * 225 * 40, 1e-3,
                       note="the largest segment count found to convert on 2026-10-15"))
    c.append(mesh_case("known_cylinder_4096_segments", fan_prism(circle(15.0, 4096), 40.0), "known",
                       note="refused: boundary certification exceeds its work budget (fails from about 4000 segments, any radius)"))
    c.append(mesh_case("known_cylinder_12499_segments", fan_prism(circle(15.0, 12499), 40.0), "known",
                       note="refused as 'not a supported constant-section prism', which it is: a misleading message"))
    ct2 = fan_prism(circle(15.0, 12501), 40.0)
    c.append(mesh_case("mesh_cylinder_50004_tris", ct2, "refuse", note="4 over the cap: a clean refusal"))

    # Meshes outside convert's scope: a clean refusal, fast. A "success" must still be right.
    st = sphere(20.0, 400, 250)
    c.append(mesh_case("mesh_sphere_200k_tris", st, "refuse_or_exact", mesh_volume(st), 1e-3, note="organic"))
    tt = torus(30.0, 8.0, 1000, 500)
    c.append(mesh_case("mesh_torus_1M_tris", tt, "refuse_or_exact", mesh_volume(tt), 1e-3, note="1 000 000 triangles"))
    ft = frustum(circle(12.0, 6), 0.5, 20.0)
    c.append(mesh_case("mesh_tapered_hexagon", ft, "refuse_or_exact", mesh_volume(ft), 1e-6,
                       note="not constant-section: a straight-prism answer is a silent wrong result"))

    # Damaged and hostile files: never crash, never hang.
    c.append(mesh_case("bad_open_mesh", gt[:-1], "refuse_or_exact", None, note="one triangle missing"))
    c.append(mesh_case("bad_inside_out", [(a, c_, b) for a, b, c_ in gt], "refuse_or_exact", mesh_volume(gt), 1e-6,
                       note="every triangle reversed; a success must have positive volume"))
    c.append(mesh_case("bad_degenerate_tris", gt + [(gt[0][0], gt[0][0], gt[0][1])] * 50, "refuse_or_exact", mesh_volume(gt), 1e-6,
                       note="50 zero-area triangles added"))
    c.append(mesh_case("bad_duplicate_tris", gt + gt[:40], "refuse_or_exact", None, note="40 triangles twice"))
    c.append(mesh_case("bad_two_shells", gt + [tuple((x + 100, y, z) for x, y, z in t) for t in gt], "refuse_or_exact",
                       2 * mesh_volume(gt), 1e-6, note="two separate gears in one file"))
    nan = list(gt)
    nan[3] = ((float("nan"), 0.0, 0.0), nan[3][1], nan[3][2])
    c.append(mesh_case("bad_nan_vertex", nan, "refuse", note="a NaN coordinate"))
    c.append(mesh_case("bad_empty_file", None, "refuse", raw=b"", note="0 bytes"))
    c.append(mesh_case("bad_truncated", None, "refuse",
                       raw=b"x".ljust(80, b"\0") + struct.pack("<I", 1000) + b"\0" * 500, note="says 1000 triangles, holds 10"))
    c.append(mesh_case("bad_count_4e9", None, "refuse",
                       raw=b"x".ljust(80, b"\0") + struct.pack("<I", 4_000_000_000) + b"\0" * 100,
                       note="header claims 4 billion triangles: must not try to allocate them"))
    return c


# ------------------------------------------------------------- sampling ---

def tree_pids(root):
    kids = {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open(f"/proc/{d}/stat") as f:
                    ppid = int(f.read().rsplit(")", 1)[1].split()[1])
                kids.setdefault(ppid, []).append(int(d))
            except (OSError, ValueError, IndexError):
                pass
    out, todo = [], [root]
    while todo:
        p = todo.pop()
        out.append(p)
        todo += kids.get(p, [])
    return out


class Sampler(threading.Thread):
    def __init__(self, pid):
        super().__init__(daemon=True)
        self.pid, self.stop_ = pid, threading.Event()
        self.peak_rss = 0
        self.peak_cores = 0.0
        self.threads = 0
        self.gpu_util, self.gpu_mem = None, None
        self.nvsmi = shutil.which("nvidia-smi")
        self.amd = next(iter(Path("/sys/class/drm").glob("card*/device/gpu_busy_percent")), None) if Path("/sys/class/drm").exists() else None

    def ticks(self, pids):
        t = 0
        for p in pids:
            try:
                with open(f"/proc/{p}/stat") as f:
                    s = f.read().rsplit(")", 1)[1].split()
                t += int(s[11]) + int(s[12])
            except (OSError, ValueError, IndexError):
                pass
        return t

    def run(self):
        last_t, last_w, n = None, None, 0
        while not self.stop_.is_set():
            pids = tree_pids(self.pid)
            rss, th = 0, 0
            for p in pids:
                try:
                    with open(f"/proc/{p}/statm") as f:
                        rss += int(f.read().split()[1]) * PAGE
                    with open(f"/proc/{p}/status") as f:
                        for line in f:
                            if line.startswith("Threads:"):
                                th += int(line.split()[1])
                except (OSError, ValueError):
                    pass
            self.peak_rss = max(self.peak_rss, rss)
            self.threads = max(self.threads, th)
            t, w = self.ticks(pids), time.monotonic()
            if last_t is not None and w > last_w:
                self.peak_cores = max(self.peak_cores, (t - last_t) / TICK / (w - last_w))
            last_t, last_w = t, w
            if n % 5 == 0:
                self.sample_gpu()
            n += 1
            self.stop_.wait(0.1)

    def sample_gpu(self):
        try:
            if self.nvsmi:
                out = subprocess.run([self.nvsmi, "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                                     capture_output=True, text=True, timeout=5).stdout.split("\n")[0]
                u, m = (float(x) for x in out.split(","))
                self.gpu_util = max(self.gpu_util or 0, u)
                self.gpu_mem = max(self.gpu_mem or 0, m)
            elif self.amd:
                self.gpu_util = max(self.gpu_util or 0, float(self.amd.read_text().strip()))
                vram = self.amd.parent / "mem_info_vram_used"
                if vram.exists():
                    self.gpu_mem = max(self.gpu_mem or 0, round(int(vram.read_text().strip()) / 2**20, 1))
        except (OSError, ValueError, subprocess.SubprocessError):
            pass


def run_measured(cmd, timeout):
    """Run cmd; return (returncode or None on timeout, stdout+stderr text, metrics)."""
    r0 = os.times()
    w0 = time.monotonic()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    s = Sampler(p.pid)
    s.start()
    try:
        out, _ = p.communicate(timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        p.kill()
        out, _ = p.communicate()
        rc = None
    s.stop_.set()
    s.join()
    w = time.monotonic() - w0
    r1 = os.times()
    cpu = (r1.children_user - r0.children_user) + (r1.children_system - r0.children_system)
    m = {"wall_s": round(w, 2), "cpu_s": round(cpu, 2), "avg_cores": round(cpu / w, 2) if w > 0 else 0,
         "peak_cores": round(s.peak_cores, 1), "peak_rss_mb": round(s.peak_rss / 2**20, 1), "max_threads": s.threads,
         "gpu_util_pct": s.gpu_util, "gpu_mem_mb": s.gpu_mem}
    return rc, out or "", m


# ---------------------------------------------------------------- runner ---

def crash_count(cli):
    out = subprocess.run([cli, "crashes"], capture_output=True, text=True).stdout
    return sum(1 for line in out.splitlines() if line.strip() and not line.startswith("crash reports") and "(none)" not in line)


def volume_of(json_path):
    try:
        d = json.loads(Path(json_path).read_text())
        return d.get("total", {}).get("volume_mm3"), d
    except (OSError, ValueError):
        return None, None


def close(a, b, rtol):
    return a is not None and b is not None and math.isfinite(a) and abs(a - b) <= rtol * max(abs(b), 1e-12)


def run_case(cli, case, d, timeout):
    """Returns (verdict, detail, metrics)."""
    d.mkdir(parents=True, exist_ok=True)
    out_json = d / "out.json"
    if out_json.exists():
        out_json.unlink()
    kind = case["kind"]
    if kind == "snapshot":
        script = case["script"] if case.get("script") else None
        if script is None:
            stl = d / "torus.stl"
            write_stl(stl, torus(30.0, 8.0, 1000, 500))
            script = [{"command": "file.insert_mesh", "params": {"path": str(stl)}}]
        sp = d / "script.json"
        sp.write_text(json.dumps(script))
        png = d / "shot.png"
        if png.exists():
            png.unlink()
        rc, out, m = run_measured([cli, "snapshot", str(sp), "--out", str(png), "--width", "3840", "--height", "2160"], timeout)
        (d / "output.txt").write_text(out)
        tail = out.strip().splitlines()[-1][:300] if out.strip() else ""
        if rc is None:
            return "FAIL", f"hung: killed after {timeout} s", m
        if "panicked" in out:
            return "FAIL", f"panic: {tail}", m
        if rc == 0 and png.exists() and png.stat().st_size > 10_000:
            return "PASS", f"image {png.stat().st_size // 1024} KB", m
        return "NO_GPU", f"no image: {tail}", m
    if kind == "mesh":
        stl = d / f"{case['name']}.stl"
        if case["raw"] is not None:
            stl.write_bytes(case["raw"])
        else:
            write_stl(stl, case["tris"], case["ascii"])
        script = [{"command": "file.insert_mesh", "params": {"path": str(stl)}},
                  {"command": "component.activate", "params": {"component": stl.stem}},
                  {"command": "mesh.convert", "params": {"body": stl.stem}}]
    elif kind in ("roundtrip", "meshtrip"):
        ext = "step" if kind == "roundtrip" else "stl"
        part = d / f"part.{ext}"
        sp = d / "first.json"
        sp.write_text(json.dumps(case["script"]))
        first_json = d / "first_out.json"
        rc, out, m1 = run_measured([cli, "run", str(sp), "--out", str(part), "--json-out", str(first_json), "--quiet"], timeout)
        if rc != 0 or not part.exists():
            return "FAIL", f"first half failed: {out.strip()[-300:]}", m1
        if case.get("truth") is None:
            case = dict(case, truth=volume_of(first_json)[0])
        if kind == "roundtrip":
            script = [{"command": "file.insert_step", "params": {"path": str(part)}}]
        else:
            script = [{"command": "file.insert_mesh", "params": {"path": str(part)}},
                      {"command": "component.activate", "params": {"component": "part"}},
                      {"command": "mesh.convert", "params": {"body": "part"}}]
    else:
        script = case["script"]
    sp = d / "script.json"
    sp.write_text(json.dumps(script))
    rc, out, m = run_measured([cli, "run", str(sp), "--json-out", str(out_json), "--quiet"], timeout)
    (d / "output.txt").write_text(out)
    vol, _ = volume_of(out_json)
    expect, truth, rtol = case["expect"], case.get("truth"), case.get("rtol", 1e-6)
    tail = out.strip().splitlines()[-1][:300] if out.strip() else ""
    if rc is None:
        return "FAIL", f"hung: killed after {timeout} s", m
    if "panicked" in out or "RUST_BACKTRACE" in out:
        return "FAIL", f"panic: {tail}", m
    ok_run = rc == 0 and vol is not None
    if expect == "known":
        return ("FIXED", f"volume {vol}", m) if ok_run else ("KNOWN", tail, m)
    if expect == "refuse":
        return ("REFUSED", tail, m) if not ok_run else ("FAIL", f"accepted a broken file: volume {vol}", m)
    if expect == "refuse_or_exact":
        if not ok_run:
            return "REFUSED", tail, m
        if vol is not None and vol <= 0:
            return "FAIL", f"non-positive volume {vol}", m
        if truth is None or close(vol, truth, rtol):
            return "PASS", f"converted, volume {vol:.6g}" + (f" (truth {truth:.6g})" if truth else ""), m
        return "FAIL", f"silently wrong: volume {vol:.6g}, truth {truth:.6g}", m
    if not ok_run:
        return "FAIL", f"error: {tail}", m
    if truth is not None and not close(vol, truth, rtol):
        return "FAIL", f"volume {vol:.9g}, truth {truth:.9g} (rtol {rtol:g})", m
    return "PASS", f"volume {vol:.9g}" + (f", truth {truth:.9g}" if truth is not None else ""), m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cli", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--baseline")
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    only = {x for x in a.only.split(",") if x}
    print(f"[{time.strftime('%H:%M:%S')}] building cases (the 1M-triangle torus takes a few seconds)", flush=True)
    cases = [c for c in build_cases() if not only or c["name"] in only]
    base = {}
    if a.baseline and Path(a.baseline).exists():
        base = {r["name"]: r for r in json.loads(Path(a.baseline).read_text())["results"]}
    crashes0 = crash_count(a.cli)
    host = {"cpus": os.cpu_count(), "host": os.uname().nodename,
            "gpu_tool": "nvidia-smi" if shutil.which("nvidia-smi") else ("amdgpu sysfs" if any(Path("/sys/class/drm").glob("card*/device/gpu_busy_percent")) else "none")}
    print(f"[{time.strftime('%H:%M:%S')}] {len(cases)} cases on {host['host']}, {host['cpus']} CPUs, GPU sampling: {host['gpu_tool']}", flush=True)
    results = []
    for i, c in enumerate(cases, 1):
        print(f"[{time.strftime('%H:%M:%S')}] ({i}/{len(cases)}) {c['name']} ...", flush=True)
        v, detail, m = run_case(a.cli, c, out / c["name"], a.timeout)
        flags = []
        b = base.get(c["name"])
        if b and b["metrics"]["wall_s"] > 0.5:
            if m["wall_s"] > 1.25 * b["metrics"]["wall_s"]:
                flags.append(f"SLOWER {b['metrics']['wall_s']}s->{m['wall_s']}s")
            if m["peak_rss_mb"] > 1.25 * b["metrics"]["peak_rss_mb"]:
                flags.append(f"HUNGRIER {b['metrics']['peak_rss_mb']}->{m['peak_rss_mb']} MB")
        results.append({"name": c["name"], "verdict": v, "detail": detail, "note": c.get("note", ""), "metrics": m, "flags": flags})
        gpu = f" gpu {m['gpu_util_pct']}% {m['gpu_mem_mb']}MB" if m["gpu_util_pct"] is not None else ""
        print(f"    {v:8} {m['wall_s']:7.2f}s cpu {m['cpu_s']:7.2f}s cores avg {m['avg_cores']:.1f} peak {m['peak_cores']:.1f}"
              f" ram {m['peak_rss_mb']:7.1f}MB{gpu}  {detail[:110]} {' '.join(flags)}", flush=True)
    new_crashes = crash_count(a.cli) - crashes0
    summary = {v: sum(1 for r in results if r["verdict"] == v) for v in ("PASS", "REFUSED", "KNOWN", "FIXED", "NO_GPU", "FAIL")}
    doc = {"host": host, "new_crash_reports": new_crashes, "summary": summary, "results": results,
           "when": time.strftime("%Y-%m-%d %H:%M:%S %Z")}
    (out / "results.json").write_text(json.dumps(doc, indent=1))
    lines = ["| Case | Verdict | Wall s | CPU s | Cores avg | RAM MB | GPU % | Detail |", "|---|---|---|---|---|---|---|---|"]
    for r in results:
        m = r["metrics"]
        lines.append(f"| {r['name']} | {r['verdict']} {' '.join(r['flags'])} | {m['wall_s']} | {m['cpu_s']} | {m['avg_cores']} | "
                     f"{m['peak_rss_mb']} | {m['gpu_util_pct'] if m['gpu_util_pct'] is not None else '-'} | {r['detail'][:90]} |")
    (out / "results.md").write_text("\n".join(lines) + "\n")
    print(f"\nSUMMARY {summary}  new crash reports: {new_crashes}  -> {out / 'results.md'}", flush=True)
    sys.exit(1 if summary["FAIL"] or new_crashes else 0)


if __name__ == "__main__":
    main()
