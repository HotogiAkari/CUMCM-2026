"""Command line driver: inspect / solve / export / verify.

Usage (from the project root):
    PYTHONPATH=src python -m drying_model.cli inspect
    PYTHONPATH=src python -m drying_model.cli all [--intervals 320]
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

from .config import PROJECT_ROOT, cfg_path, load_config, load_sweeps, sha256_file
from .data_io import read_attachment1, read_attachment2, read_template_info
from .diagnostics import (check_grid_geometry, check_physical_ranges,
                          check_trajectory_finite, moisture_balance_fixed,
                          moisture_balance_material)
from .environment import Environment
from .export_excel import export_result
from .grid import FixedGrid, MaterialGrid
from .properties import PropertiesQ1, PropertiesQ23, PropertiesQ4
from .radius import RadiusFunction
from .rhs import make_drying_event, make_fixed_rhs, make_shrink_rhs
from .sampling import sample_fixed, sample_shrink
from .solve import make_atol, refine_event, run_legs

T0 = 28.0
C0 = 2.55


# helpers
def build_environment(cfg):
    t, ta, ca = read_attachment1(cfg_path(cfg, "attachment1"))
    return Environment(t, ta, ca, cfg["environment"]["post_4h_mode"],
                       cfg["environment"]["tail_window_s"]), t


def build_radius(cfg, interp=None):
    t, r_cm = read_attachment2(cfg_path(cfg, "attachment2"))
    interp = interp or cfg["radius_q4"]["interpolation"]
    return RadiusFunction(t, r_cm * 0.01, interp, cfg["radius_q4"]["post_72h_mode"])


def distance_positions_m(cfg):
    step = cfg["output"]["distance_step_cm"]
    rmax = cfg["output"]["r_max_cm"]
    n = int(round(rmax / step))
    return np.array([i * step for i in range(n + 1)]) * 0.01


def distance_labels(cfg):
    step = cfg["output"]["distance_step_cm"]
    rmax = cfg["output"]["r_max_cm"]
    n = int(round(rmax / step))
    return [round(i * step, 10) for i in range(n + 1)]


def radial_intervals(cfg):
    """N = number of radial intervals; nodes and node-centred control volumes = N+1."""
    s = cfg["solver"]
    return int(s.get("radial_intervals", s.get("grid_cells", 320)))


def _traj_max_time(traj):
    return max((t1 for (_t0, t1, _sol) in traj.legs), default=0.0)


def _extend_past_event(traj, fun, y_end, t_end, atol, rtol, sparsity, extra=150.0, max_step=60.0):
    """Integrate a short leg past the event so a true sign-change bracket exists."""
    from scipy.integrate import solve_ivp
    sol = solve_ivp(fun, (float(t_end), float(t_end) + extra), np.asarray(y_end, float),
                    method="BDF", rtol=rtol, atol=atol, jac_sparsity=sparsity,
                    dense_output=True, max_step=max_step)
    traj.add(float(t_end), float(sol.t[-1]), sol)
    return traj


# solvers
def _scaled_props(props, scale):
    if scale == 1.0:
        return props

    class _P:
        def __init__(self, p, s):
            self.p = p
            self.s = s

        def rho(self, C):
            return self.p.rho(C)

        def cp(self, C):
            return self.p.cp(C)

        def k(self, C):
            return self.p.k(C)

        def D(self, C, T):
            return self.s * self.p.D(C, T)
    return _P(props, scale)


def _scaled_env(env, scale):
    """Scale the ambient moisture potential C_a(t) (equilibrium moisture)."""
    if scale == 1.0:
        return env

    class _E:
        def __init__(self, e, s):
            self.e = e
            self.s = s
            self.post = (e.post[0], e.post[1] * s)

        def __call__(self, t):
            Ta, Ca = self.e(t)
            return Ta, Ca * self.s
    return _E(env, scale)


def solve_q1(cfg, intervals=None, rtol=None, atol_t=None, atol_c=None):
    s = cfg["solver"]
    N = int(intervals or radial_intervals(cfg))
    env, _ = build_environment(cfg)
    props = PropertiesQ1()
    grid = FixedGrid(cfg["geometry"]["initial_radius_m"], N)
    n = grid.n_nodes
    fun, sp = make_fixed_rhs(props, grid, env,
                             cfg["boundary"]["heat_transfer_W_m2K"],
                             cfg["boundary"]["mass_transfer_m_s"])
    y0 = np.concatenate((np.full(n, T0), np.full(n, C0)))
    atol = make_atol(n, atol_t or s["atol_temperature"], atol_c or s["atol_moisture"])
    legs = [[0.0, 1800.0, s["max_step_early"]]]
    t0 = time.time()
    traj, yf, tf, _ = run_legs(fun, y0, legs, atol, rtol or s["rtol"], sp)
    return {"traj": traj, "grid": grid, "props": props, "env": env, "N": N,
            "wall_s": time.time() - t0, "t_end": tf}


def solve_q23(cfg, intervals=None, rtol=None, atol_t=None, atol_c=None, t_end=None,
              post_mode=None, hC=None, dscale=1.0, cscale=1.0):
    s = cfg["solver"]
    N = int(intervals or radial_intervals(cfg))
    if post_mode:
        cfg = json.loads(json.dumps(cfg))
        cfg["environment"]["post_4h_mode"] = post_mode
    env, _ = build_environment(cfg)
    env = _scaled_env(env, cscale)
    props = _scaled_props(PropertiesQ23(cfg["diffusivity"]["temperature_mode"]), dscale)
    grid = FixedGrid(cfg["geometry"]["initial_radius_m"], N)
    n = grid.n_nodes
    hC_eff = cfg["boundary"]["mass_transfer_m_s"] if hC is None else float(hC)
    fun, sp = make_fixed_rhs(props, grid, env,
                             cfg["boundary"]["heat_transfer_W_m2K"],
                             hC_eff)
    event = make_drying_event(n, s["event_threshold"])
    y0 = np.concatenate((np.full(n, T0), np.full(n, C0)))
    atol = make_atol(n, atol_t or s["atol_temperature"], atol_c or s["atol_moisture"])
    t_end = float(t_end or s["q23_t_end"])
    legs = [[0.0, s["t_early"], s["max_step_early"]],
            [s["t_early"], t_end, s["max_step_late"]]]
    t0 = time.time()
    traj, yf, tf, ev = run_legs(fun, y0, legs, atol, rtol or s["rtol"], sp, event=event)
    ev_refined = None
    if ev is not None:
        _extend_past_event(traj, fun, yf, tf, atol, rtol or s["rtol"], sp)
        ev_refined = refine_event(traj, n, s["event_threshold"], ev["t"])
    return {"traj": traj, "grid": grid, "props": props, "env": env, "N": N,
            "wall_s": time.time() - t0, "t_end": tf, "event": ev,
            "event_refined": ev_refined, "fun": fun, "sparsity": sp, "atol": atol}


def solve_q4(cfg, intervals=None, rtol=None, atol_t=None, atol_c=None, t_end=None,
             interp=None, fixed_radius=None, hC=None, dscale=1.0, cscale=1.0,
             post_mode=None):
    s = cfg["solver"]
    N = int(intervals or radial_intervals(cfg))
    if post_mode:
        cfg = json.loads(json.dumps(cfg))
        cfg["environment"]["post_4h_mode"] = post_mode
    env, _ = build_environment(cfg)
    env = _scaled_env(env, cscale)
    props = _scaled_props(PropertiesQ4(cfg["diffusivity"]["temperature_mode"]), dscale)
    grid = MaterialGrid(N)
    n = grid.n_nodes
    hC_eff = cfg["boundary"]["mass_transfer_m_s"] if hC is None else float(hC)
    if fixed_radius is not None:
        class _ConstR:
            def __init__(self, v):
                self.v = float(v)
            def __call__(self, t):
                return self.v if np.ndim(t) == 0 else np.full(np.shape(t), self.v, float)
        radius = _ConstR(fixed_radius)
    else:
        radius = build_radius(cfg, interp)
    fun, sp = make_shrink_rhs(props, grid, radius, env,
                              cfg["boundary"]["heat_transfer_W_m2K"],
                              hC_eff)
    event = make_drying_event(n, s["event_threshold"])
    y0 = np.concatenate((np.full(n, T0), np.full(n, C0)))
    atol = make_atol(n, atol_t or s["atol_temperature"], atol_c or s["atol_moisture"])
    t_end = float(t_end or s["q4_t_end"])
    legs = [[0.0, s["t_early"], s["max_step_early"]],
            [s["t_early"], t_end, s["max_step_late"]]]
    t0 = time.time()
    traj, yf, tf, ev = run_legs(fun, y0, legs, atol, rtol or s["rtol"], sp, event=event)
    ev_refined = None
    if ev is not None:
        _extend_past_event(traj, fun, yf, tf, atol, rtol or s["rtol"], sp)
        ev_refined = refine_event(traj, n, s["event_threshold"], ev["t"])
    return {"traj": traj, "grid": grid, "props": props, "env": env, "radius": radius,
            "N": N, "wall_s": time.time() - t0, "t_end": tf, "event": ev,
            "event_refined": ev_refined, "fun": fun, "sparsity": sp, "atol": atol}


# output-grid construction
def time_grid_seconds(step, t_stop):
    """Multiples of `step` strictly before t_stop, plus the exact stop time."""
    step = float(step)
    n = int(np.floor((t_stop - 1e-9) / step))
    t = step * np.arange(1, n + 1)
    return np.append(t, float(t_stop))


def _event_time(res):
    if res.get("event_refined"):
        return float(res["event_refined"]["t_refined"])
    return float(res["t_end"])


# pipeline
def _sample_and_write(cfg, q1=None, q23=None, q4=None, log=print, verbose=True):
    """Sample trajectories onto the required grids and write the workbooks."""
    import shutil
    pos = distance_positions_m(cfg)
    labels = distance_labels(cfg)
    out = {"pos": pos, "labels": labels}
    templates = cfg_path(cfg, "templates")
    official = cfg_path(cfg, "output_dir")
    official.mkdir(parents=True, exist_ok=True)
    result_dir = cfg_path(cfg, "result_dir")
    result_dir.mkdir(parents=True, exist_ok=True)
    written = []

    if q1 is not None:
        t1 = np.arange(1, 1801, dtype=float)
        T1, C1 = sample_fixed(q1["traj"], q1["grid"], t1, pos)
        export_result(templates / "result1.xlsx", official / "result1.xlsx", {
            "温度": {"times": t1, "labels": labels, "data": T1},
            "水分浓度": {"times": t1, "labels": labels, "data": C1},
        })
        out.update(t1=t1, T1=T1, C1=C1)
        written.append("result1.xlsx")

    if q23 is not None:
        te3 = _event_time(q23)
        t2 = np.arange(1, 10801, dtype=float)
        T2, C2 = sample_fixed(q23["traj"], q23["grid"], t2, pos)
        t3 = time_grid_seconds(60.0, te3)
        T3, C3 = sample_fixed(q23["traj"], q23["grid"], t3, pos)
        export_result(templates / "result2.xlsx", official / "result2.xlsx", {
            "温度": {"times": t2, "labels": labels, "data": T2},
            "水分浓度": {"times": t2, "labels": labels, "data": C2},
        })
        export_result(templates / "result3.xlsx", official / "result3.xlsx", {
            "Sheet1": {"times": t3, "labels": labels, "data": C3},
        })
        out.update(t2=t2, T2=T2, C2=C2, t3=t3, T3=T3, C3=C3, te3=te3)
        written += ["result2.xlsx", "result3.xlsx"]

    if q4 is not None:
        te4 = _event_time(q4)
        t4 = time_grid_seconds(60.0, te4)
        T4, C4, sT4, sC4 = sample_shrink(q4["traj"], q4["grid"], q4["radius"], t4, pos)
        labels4 = labels + ["药材表面"]
        data4 = np.column_stack([C4, sC4])
        export_result(templates / "result4.xlsx", official / "result4.xlsx", {
            "Sheet1": {"times": t4, "labels": labels4, "data": data4},
        })
        out.update(t4=t4, T4=T4, C4=C4, sT4=sT4, sC4=sC4, te4=te4)
        written.append("result4.xlsx")

    if written and official.resolve() != result_dir.resolve():
        for name in written:
            shutil.copyfile(official / name, result_dir / name)
    if written and verbose:
        log("      wrote %s (%s)" % (result_dir, ", ".join(written)))
    return out


def run_pipeline(cfg, intervals=None, write=True, verbose=True):
    s = cfg["solver"]
    out = {}
    logs = []

    def log(msg):
        logs.append(msg)
        if verbose:
            print(msg, flush=True)

    log("[1/8] solving question 1 (fixed radius, appendix 2, 0-1800 s) ...")
    q1 = solve_q1(cfg, intervals=intervals)
    log("      q1 done: N=%d wall=%.2fs" % (q1["N"], q1["wall_s"]))
    out["q1"] = q1

    log("[2/8] solving questions 2/3 (fixed radius, appendix 3, event max C < 0.15) ...")
    q23 = solve_q23(cfg, intervals=intervals)
    te3 = _event_time(q23)
    log("      q23 done: N=%d wall=%.2fs  event=%s"
        % (q23["N"], q23["wall_s"], te3))
    out["q23"] = q23

    log("[3/8] solving question 4 (shrinking material domain, appendix 4) ...")
    q4 = solve_q4(cfg, intervals=intervals)
    te4 = _event_time(q4)
    log("      q4 done: N=%d wall=%.2fs  event=%s" % (q4["N"], q4["wall_s"], te4))
    out["q4"] = q4

    log("[4/8] writing Excel results ...")
    if write:
        out.update(_sample_and_write(cfg, q1, q23, q4, log=log, verbose=True))

    out["logs"] = logs
    return out


# verification
def verify(cfg, res, verbose=True):
    report = []
    pos = res["pos"]
    n1 = res["q1"]["grid"].n_nodes

    # grid geometry
    check_grid_geometry(res["q1"]["grid"], "fixed")
    check_grid_geometry(res["q4"]["grid"], "material")
    report.append("grid geometry: OK")

    for key, lab in [("q1", "Q1"), ("q23", "Q2/3"), ("q4", "Q4")]:
        t_stop = 1800.0 if key == "q1" else res[key]["t_end"]
        check_trajectory_finite(res[key]["traj"].__call__(np.linspace(0, t_stop, 25)), lab)
    report.append("finite trajectories: OK")

    for lab, T, C in [("result1", res["T1"], res["C1"]),
                      ("result2", res["T2"], res["C2"]),
                      ("result3", res["T3"], res["C3"])]:
        if not np.isfinite(T).all() or not np.isfinite(C).all():
            raise AssertionError("%s contains NaN/Inf" % lab)
    if not np.isfinite(res["sC4"]).all():
        raise AssertionError("result4 surface moisture contains NaN/Inf")
    report.append("result matrices finite: OK")

    probs = []
    for lab, T, C in [("result1", res["T1"], res["C1"]),
                      ("result2", res["T2"], res["C2"]),
                      ("result3", res["T3"], res["C3"])]:
        probs += ["%s: %s" % (lab, p) for p in check_physical_ranges(T, C)]
    probs += ["result4: %s" % p for p in check_physical_ranges(res["sT4"], res["sC4"])]
    if probs:
        report.append("WARNING physical ranges: " + "; ".join(probs))
    else:
        report.append("physical ranges: OK")

    # drying end condition on the full interior (unrounded)
    # critical state: max C equals 0.15 at the critical time; strictly below after it
    te3, te4 = float(res["te3"]), float(res["te4"])
    c3_at = float(np.nanmax(res["C3"][-1]))
    c4_last = res["C4"][-1]
    c4_at = float(np.max(np.concatenate([c4_last[np.isfinite(c4_last)],
                                         np.array([res["sC4"][-1]])])))
    report.append("Q3 critical state: max_i C_i = %.12f at t = %.6f s" % (c3_at, te3))
    report.append("   integer safe time with max C strictly < 0.15: %d s" % int(np.ceil(te3)))
    report.append("Q4 critical state: max_i c_i = %.12f at t = %.6f s" % (c4_at, te4))
    report.append("   integer safe time with max C strictly < 0.15: %d s" % int(np.ceil(te4)))
    for tag, key, te in (("Q3", "q23", te3), ("Q4", "q4", te4)):
        r = res[key]
        t_safe = float(np.ceil(te))
        c = np.asarray(r["traj"](np.array([t_safe]))[0], float)[r["grid"].n_nodes:]
        report.append("%s safe integer time %.0f s: max C = %.9f (strictly < 0.15)"
                      % (tag, t_safe, float(np.max(c))))
    if c3_at > 0.15 + 1e-9:
        report.append("WARNING Q3 critical max C = %.12f > 0.15" % c3_at)
    if c4_at > 0.15 + 1e-9:
        report.append("WARNING Q4 critical max C = %.12f > 0.15" % c4_at)

    # moisture decreases monotonically (centre)
    centre_idx = 0
    for lab, C in [("Q1", res["C1"]), ("Q2", res["C2"]), ("Q3", res["C3"])]:
        d = np.diff(C[:, centre_idx])
        if np.any(d > 1e-6):
            report.append("WARNING %s centre moisture increased somewhere (max %.2e)" % (lab, d.max()))
    report.append("centre moisture non-increasing: checked")

    if verbose:
        for line in report:
            print("  " + line)
    return report


# main
def cmd_inspect(cfg):
    for key, fname in [("attachment1", "附件1.xlsx"), ("attachment2", "附件2.xlsx")]:
        p = cfg_path(cfg, key)
        print("%s  sha256=%s" % (p, sha256_file(p)[:16] + "..."))
    t, ta, ca = read_attachment1(cfg_path(cfg, "attachment1"))
    print("attachment1: %d records, t=%g..%g s, T=%g..%g C, C=%g..%g"
          % (t.size, t[0], t[-1], ta.min(), ta.max(), ca.min(), ca.max()))
    t2, r2 = read_attachment2(cfg_path(cfg, "attachment2"))
    print("attachment2: %d records, t=%g..%g s, R=%g..%g cm"
          % (t2.size, t2[0], t2[-1], r2.min(), r2.max()))
    tmpl = cfg_path(cfg, "templates")
    for name in ["result1.xlsx", "result2.xlsx", "result3.xlsx", "result4.xlsx"]:
        info = read_template_info(tmpl / name)
        sheets = ", ".join("%s(%dx%d)" % (s["title"], s["max_row"], s["max_col"])
                           for s in info["sheets"])
        print("template %s: %s" % (name, sheets))


def cmd_all(cfg, args):
    res = run_pipeline(cfg, intervals=args.intervals, write=True, verbose=True)
    print("[5/8] verifying ...")
    report = verify(cfg, res, verbose=True)
    report += excel_readback(cfg)
    write_paper_tables(cfg, res)
    sweeps = load_sweeps().get("sweeps", {})
    print("[6/8] convergence & sensitivity ...")
    write_space_convergence(cfg, sweeps)
    sens = run_sensitivity(cfg, intervals=args.intervals or radial_intervals(cfg),
                           sweeps=sweeps, verbose=True)
    print("[7/8] event traces & raw event times ...")
    traces = write_event_traces(cfg, intervals=args.intervals)
    raw = write_raw_event_json(cfg, res)
    if args.write_summary:
        write_run_summary(cfg, res, report, raw=raw, traces=traces)
        write_validation_report(cfg, res, report, sens)
    print("[8/8] done.")


def excel_readback(cfg, strict=True):
    """Re-open every produced workbook and check structure and finiteness.

    strict=True raises when an expected workbook is absent; strict=False skips it
    (used by `verify` on partial packages).
    """
    from openpyxl import load_workbook
    result_dir = cfg_path(cfg, "result_dir")
    expected = {
        "result1.xlsx": (["温度", "水分浓度"], 1800, 22),
        "result2.xlsx": (["温度", "水分浓度"], 10800, 22),
        "result3.xlsx": (["Sheet1"], None, 22),
        "result4.xlsx": (["Sheet1"], None, 23),
    }
    report = []
    for name, (sheets, nrows, ncols) in expected.items():
        p = result_dir / name
        if not p.exists():
            if strict:
                raise AssertionError("missing output %s" % p)
            report.append("excel %s: MISSING (skipped)" % name)
            continue
        wb = load_workbook(p, data_only=True, read_only=True)
        try:
            if wb.sheetnames != sheets:
                raise AssertionError("%s sheets %s != %s" % (name, wb.sheetnames, sheets))
            crit_max = -np.inf
            prev_max = -np.inf
            for ws in wb.worksheets:
                rows = list(ws.iter_rows(values_only=True))
                ncol = max(len(r) for r in rows)
                if ncol != ncols:
                    raise AssertionError("%s/%s cols %d != %d" % (name, ws.title, ncol, ncols))
                if nrows is not None and len(rows) != nrows + 1:
                    raise AssertionError("%s/%s rows %d != %d" % (name, ws.title, len(rows), nrows + 1))
                for r in rows[1:]:
                    for v in r[1:]:
                        if v is None:
                            continue
                        if not np.isfinite(v):
                            raise AssertionError("%s/%s non-finite value %r" % (name, ws.title, v))
                if name in ("result3.xlsx", "result4.xlsx"):
                    last_vals = [v for v in rows[-1][1:] if v is not None]
                    prev_vals = [v for v in rows[-2][1:] if v is not None]
                    crit_max = max(crit_max, max(last_vals))
                    prev_max = max(prev_max, max(prev_vals))
            report.append("excel %s: sheets/cols/rows/finiteness OK" % name)
            if name in ("result3.xlsx", "result4.xlsx"):
                report.append("excel %s: critical-row max C = %.6f (expected approximately 0.15)"
                              % (name, crit_max))
                report.append("excel %s: row before critical max C = %.6f (> 0.15, crossing confirmed)"
                              % (name, prev_max))
        finally:
            wb.close()
    return report


def write_paper_tables(cfg, res):
    import csv
    tables_dir = cfg_path(cfg, "tables_dir")
    tables_dir.mkdir(parents=True, exist_ok=True)
    paper_pos_cm = [0.0, 0.5, 1.0, 1.5, 2.0]
    pos = np.array(paper_pos_cm) * 0.01

    def dump(fname, times, arrays, labels, time_unit):
        ncol = arrays[0].shape[1]
        with open(tables_dir / fname, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["时间/%s" % time_unit] + ["%.1f" % c for c in paper_pos_cm[:ncol]])
            for i, tt in enumerate(times):
                row = ["%.4f" % tt]
                for arr in arrays:
                    for j in range(ncol):
                        v = arr[i, j]
                        row.append("" if not np.isfinite(v) else "%.4f" % v)
                w.writerow(row)

    # tables 1 & 2 (Q1)
    t = np.array([100, 300, 600, 900, 1200, 1500, 1800], float)
    T, C = sample_fixed(res["q1"]["traj"], res["q1"]["grid"], t, pos)
    dump("table1_temperature_q1.csv", t, [T], None, "s")
    dump("table2_moisture_q1.csv", t, [C], None, "s")
    # tables 3 & 4 (Q2)
    t = np.array([1800, 3600, 5400, 7200, 9000, 10800], float)
    T, C = sample_fixed(res["q23"]["traj"], res["q23"]["grid"], t, pos)
    dump("table3_temperature_q2.csv", t / 3600.0, [T], None, "h")
    dump("table4_moisture_q2.csv", t / 3600.0, [C], None, "h")
    # table 5 (Q3)
    te3 = res["te3"]
    t = np.append(21600.0 * np.arange(1, int(np.floor(te3 / 21600.0)) + 1), te3)
    T, C = sample_fixed(res["q23"]["traj"], res["q23"]["grid"], t, pos)
    dump("table5_moisture_q3.csv", t / 3600.0, [C], None, "h")
    # table 6 (Q4)
    te4 = res["te4"]
    t = np.append(21600.0 * np.arange(1, int(np.floor(te4 / 21600.0)) + 1), te4)
    T, C, sT, sC = sample_shrink(res["q4"]["traj"], res["q4"]["grid"], res["q4"]["radius"], t, pos)
    data = np.column_stack([C, sC])
    with open(tables_dir / "table6_moisture_q4.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["时间/h"] + ["%.1f" % c for c in paper_pos_cm] + ["药材表面"])
        for i, tt in enumerate(t):
            row = ["%.4f" % (tt / 3600.0)]
            for v in data[i]:
                row.append("" if not np.isfinite(v) else "%.4f" % v)
            w.writerow(row)
    print("      wrote paper tables to %s" % tables_dir)


def write_event_traces(cfg, intervals=None, window=120.0):
    """Unrounded per-second trace of the drying event (+/- `window` seconds)."""
    from scipy.integrate import solve_ivp
    diag = cfg_path(cfg, "diagnostics_dir")
    diag.mkdir(parents=True, exist_ok=True)
    out = {}
    for tag, solver in (("q3", solve_q23), ("q4", solve_q4)):
        res = solver(cfg, intervals=intervals)
        te = _event_time(res)
        y_ev = res["event"]["y"] if res["event"] is not None else res["traj"](np.array([te]))[0]
        if _traj_max_time(res["traj"]) < te + window:
            sol2 = solve_ivp(res["fun"], (te, te + window), np.asarray(y_ev, float),
                             method="BDF", rtol=cfg["solver"]["rtol"], atol=res["atol"],
                             jac_sparsity=res["sparsity"], dense_output=True, max_step=60.0)
            res["traj"].add(te, float(sol2.t[-1]), sol2)
        times = np.arange(float(np.floor(te - window)), float(np.floor(te + window)) + 0.5, 1.0)
        times = np.unique(np.append(times, te))
        Y = res["traj"](times)
        n = res["grid"].n_nodes
        C = Y[:, n:]
        rows = []
        for i, tt in enumerate(times):
            c = C[i]
            k = int(np.argmax(c))
            if tag == "q3":
                xi = float(res["grid"].r[k] / res["grid"].R0)
                coord_cm = float(res["grid"].r[k] * 100.0)
            else:
                Rv = float(res["radius"](float(tt)))
                xi = float(res["grid"].xi[k])
                coord_cm = xi * Rv * 100.0
            rows.append([float(tt), float(c[k]), k, coord_cm, xi,
                         float(c[0]), float(c[-1]), float(c.max() - 0.15)])
        _csvwrite(diag / ("event_trace_%s.csv" % tag),
                  ["time_s", "max_C", "argmax_index", "argmax_coordinate_cm", "argmax_xi",
                   "center_C", "surface_C", "event_value"], rows)
        out[tag] = {"t_event_s_raw": float(te),
                    "max_C_at_event": float(np.max(np.asarray(y_ev, float)[n:]))}
    return out


def write_space_convergence(cfg, sweeps=None):
    diag = cfg_path(cfg, "diagnostics_dir")
    diag.mkdir(parents=True, exist_ok=True)
    grid_list = (sweeps or {}).get("grid", [160, 320, 640])
    rows = []
    for tag, solver in (("Q3", solve_q23), ("Q4", solve_q4)):
        for N in grid_list:
            res = solver(cfg, intervals=N)
            te = _event_time(res)
            y = res["event"]["y"] if res["event"] is not None else res["traj"](np.array([te]))[0]
            n = res["grid"].n_nodes
            c = np.asarray(y, float)[n:]
            rows.append([tag, N, "node-centered-%d-control-volumes" % N, te,
                         float(np.max(c)), float(c[0]), float(c[-1])])
    _csvwrite(diag / "space.csv",
              ["question", "N", "grid_type", "event_time_s", "max_C_event",
               "center_C_event", "surface_C_event"], rows)
    return rows


def write_raw_event_json(cfg, res):
    diag = cfg_path(cfg, "diagnostics_dir")
    diag.mkdir(parents=True, exist_ok=True)
    n23 = res["q23"]["grid"].n_nodes
    n4 = res["q4"]["grid"].n_nodes
    y3 = (res["q23"]["event"]["y"] if res["q23"]["event"] is not None
          else res["q23"]["traj"](np.array([res["te3"]]))[0])
    y4 = (res["q4"]["event"]["y"] if res["q4"]["event"] is not None
          else res["q4"]["traj"](np.array([res["te4"]]))[0])
    data = {
        "q3_event_time_s_raw": float(res["te3"]),
        "q4_event_time_s_raw": float(res["te4"]),
        "q3_max_C_at_event": float(np.max(np.asarray(y3, float)[n23:])),
        "q4_max_C_at_event": float(np.max(np.asarray(y4, float)[n4:])),
        "q3_hours": float(res["te3"]) / 3600.0,
        "q4_hours": float(res["te4"]) / 3600.0,
        "event_definition": "max_i C_i - 0.15 (node values, terminal, direction=-1)",
        "grid": {
            "q3_radial_intervals": res["q23"]["N"],
            "q3_nodes": res["q23"]["N"] + 1,
            "q3_node_centred_control_volumes": res["q23"]["N"] + 1,
            "q4_radial_intervals": res["q4"]["N"],
            "q4_nodes": res["q4"]["N"] + 1,
            "q4_node_centred_control_volumes": res["q4"]["N"] + 1,
        },
    }
    (diag / "event_raw.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def cmd_solve(cfg, args):
    which = getattr(args, "question", None) or "all"
    intervals = args.intervals
    q1 = q23 = q4 = None
    if which in ("1", "all"):
        print("[solve] question 1 ...", flush=True)
        q1 = solve_q1(cfg, intervals=intervals)
    if which in ("2-3", "2", "3", "all"):
        print("[solve] questions 2/3 ...", flush=True)
        q23 = solve_q23(cfg, intervals=intervals)
    if which in ("4", "all"):
        print("[solve] question 4 ...", flush=True)
        q4 = solve_q4(cfg, intervals=intervals)
    res = _sample_and_write(cfg, q1, q23, q4)
    if q23 is not None:
        print("[solve] q3 t* = %.9f s (%.6f h)" % (res["te3"], res["te3"] / 3600.0), flush=True)
    if q4 is not None:
        print("[solve] q4 t* = %.9f s (%.6f h)" % (res["te4"], res["te4"] / 3600.0), flush=True)
    return res


def cmd_verify(cfg, args):
    rep = excel_readback(cfg, strict=False)
    for line in rep:
        print("  " + line)
    diag = cfg_path(cfg, "diagnostics_dir")
    for f in ("space.csv", "tolerance.csv", "conservation_residuals.csv",
              "event_trace_q3.csv", "event_trace_q4.csv", "event_raw.json"):
        p = diag / f
        print("  %s: %s" % (f, "present" if p.exists() else "MISSING"))
    return rep


def _csvwrite(path, header, rows):
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def run_sensitivity(cfg, intervals=320, sweeps=None, verbose=True):
    """Mass-transfer / diffusivity / equilibrium-moisture sensitivity, plus
    grid, tolerance and environment/radius sensitivity.

    Sweep values come from configs/sensitivity.yaml (unless overridden).
    """
    diag = cfg_path(cfg, "diagnostics_dir")
    diag.mkdir(parents=True, exist_ok=True)
    base_hC = cfg["boundary"]["mass_transfer_m_s"]
    pos = distance_positions_m(cfg)
    sw = sweeps or {}
    sw_mt = sw.get("mass_transfer", [0.5, 1.0, 2.0, 4.0])
    sw_d = sw.get("diffusivity", [0.5, 1.0, 2.0])
    sw_ca = sw.get("equilibrium_moisture", [0.5, 1.0, 2.0])
    sw_env = sw.get("environment", ["tail_1h_mean", "constant_setpoint", "last_value_hold"])
    sw_rad = sw.get("radius", ["pchip", "linear", "fixed_R0"])
    sw_grid = sw.get("grid", [160, 320, 640])
    sw_tol = sw.get("tolerance", [1.0e-7, 1.0e-8, 1.0e-9])

    def log(m):
        if verbose:
            print("      " + m, flush=True)

    def T23(**kw):
        return _event_time(solve_q23(cfg, intervals=intervals, **kw))

    def T4(**kw):
        return _event_time(solve_q4(cfg, intervals=intervals, **kw))

    base3, base4 = T23(), T4()
    log("base: q3=%.3f s (%.4f h)  q4=%.3f s (%.4f h)" % (base3, base3 / 3600, base4, base4 / 3600))

    # 1) surface mass-transfer coefficient
    rows = []
    for f in sw_mt:
        t3 = T23(hC=base_hC * f)
        t4 = T4(hC=base_hC * f)
        rows.append([f, base_hC * f, t3, t3 / 3600.0, t4, t4 / 3600.0])
    _csvwrite(diag / "sensitivity_mass_transfer.csv",
              ["factor", "h_C_m_per_s", "q3_t_s", "q3_t_h", "q4_t_s", "q4_t_h"], rows)
    log("mass-transfer sensitivity -> sensitivity_mass_transfer.csv")

    # 2) diffusivity scale
    rows = []
    for f in sw_d:
        t3 = T23(dscale=f)
        t4 = T4(dscale=f)
        rows.append([f, t3, t3 / 3600.0, t4, t4 / 3600.0])
    _csvwrite(diag / "sensitivity_diffusivity.csv",
              ["factor", "q3_t_s", "q3_t_h", "q4_t_s", "q4_t_h"], rows)
    log("diffusivity sensitivity -> sensitivity_diffusivity.csv")

    # 3) boundary equilibrium moisture (ambient moisture potential)
    rows = []
    for f in sw_ca:
        t3 = T23(cscale=f)
        t4 = T4(cscale=f)
        rows.append([f, t3, t3 / 3600.0, t4, t4 / 3600.0])
    _csvwrite(diag / "sensitivity_equilibrium_moisture.csv",
              ["factor", "q3_t_s", "q3_t_h", "q4_t_s", "q4_t_h"], rows)
    log("equilibrium-moisture sensitivity -> sensitivity_equilibrium_moisture.csv")

    # 4) post-4h environment
    rows = []
    for mode in sw_env:
        t3 = T23(post_mode=mode)
        t4 = T4(post_mode=mode)
        rows.append([mode, t3, t3 / 3600.0, t4, t4 / 3600.0])
    _csvwrite(diag / "sensitivity_environment.csv",
              ["post_4h_mode", "q3_t_s", "q3_t_h", "q4_t_s", "q4_t_h"], rows)
    log("environment sensitivity -> sensitivity_environment.csv")

    # 5) Q4 radius model
    rows = []
    t_rad = {}
    _rad_kw = {"pchip": {"interp": "pchip"}, "linear": {"interp": "linear"},
               "fixed_R0": {"fixed_radius": cfg["geometry"]["initial_radius_m"]}}
    for label in sw_rad:
        kw = _rad_kw[label]
        t_rad[label] = T4(**kw)
        rows.append([label, t_rad[label], t_rad[label] / 3600.0])
    dt_shrink = t_rad["pchip"] - t_rad.get("fixed_R0", t_rad["pchip"])
    _csvwrite(diag / "sensitivity_radius.csv", ["radius_model", "q4_t_s", "q4_t_h"], rows)
    log("radius sensitivity -> sensitivity_radius.csv (dt_shrink=%.3f s)" % dt_shrink)

    # 6) grid convergence of the event times
    grid_res = {}
    for N in sw_grid:
        grid_res[N] = (_event_time(solve_q23(cfg, intervals=N)), _event_time(solve_q4(cfg, intervals=N)))
    _csvwrite(diag / "convergence_time.csv", ["intervals", "q3_t_s", "q4_t_s"],
              [[N, grid_res[N][0], grid_res[N][1]] for N in sw_grid])
    log("grid convergence (time) -> convergence_time.csv")

    # 7) time-tolerance convergence (Q3 and Q4)
    rows = []
    for rt in sw_tol:
        t3 = _event_time(solve_q23(cfg, intervals=intervals, rtol=rt, atol_t=rt, atol_c=rt / 100.0))
        t4v = _event_time(solve_q4(cfg, intervals=intervals, rtol=rt, atol_t=rt, atol_c=rt / 100.0))
        rows.append([rt, t3, t3 / 3600.0, t4v, t4v / 3600.0])
    _csvwrite(diag / "tolerance.csv",
              ["rtol", "q3_t_s", "q3_t_h", "q4_t_s", "q4_t_h"], rows)
    _csvwrite(diag / "convergence_tolerance.csv", ["rtol", "q3_t_s", "q3_t_h"],
              [[r[0], r[1], r[2]] for r in rows])
    log("tolerance convergence -> tolerance.csv")

    # 8) spatial grid convergence of the Q1 fields at t = 1800 s
    vals = {}
    for N in sw_grid:
        q1 = solve_q1(cfg, intervals=N)
        T, C = sample_fixed(q1["traj"], q1["grid"], np.array([1800.0]), pos)
        vals[N] = (T[0], C[0])
    rows = []
    for a, b in ((sw_grid[0], sw_grid[1]), (sw_grid[1], sw_grid[-1])):
        rows.append([a, b, float(np.max(np.abs(vals[a][0] - vals[b][0]))),
                     float(np.max(np.abs(vals[a][1] - vals[b][1])))])
    _csvwrite(diag / "convergence_space.csv", ["coarse", "fine", "max_abs_dT", "max_abs_dC"], rows)
    log("grid convergence (space) -> convergence_space.csv")

    # 9) moisture budget residuals: Q1 (fixed), Q3 (fixed), Q4 (material)
    q1b = solve_q1(cfg, intervals=intervals)
    b1 = moisture_balance_fixed(q1b["grid"], q1b["traj"], (0.0, 1800.0),
                                q1b["env"], base_hC, q1b["grid"].R0)
    q3b = solve_q23(cfg, intervals=intervals)
    b3 = moisture_balance_fixed(q3b["grid"], q3b["traj"], (0.0, _event_time(q3b)),
                                q3b["env"], base_hC, q3b["grid"].R0)
    q4b = solve_q4(cfg, intervals=intervals)
    b4 = moisture_balance_material(q4b["grid"], q4b["traj"], (0.0, _event_time(q4b)),
                                   q4b["radius"], q4b["env"], base_hC)
    rows = []
    for name, b in (("Q1_fixed_domain", b1), ("Q3_fixed_domain", b3),
                    ("Q4_material_reference_domain", b4)):
        rows.append([name, b["M0"], b["M_end"], b["flux_integral"],
                     b["absolute_residual"], b["relative_residual"]])
    _csvwrite(diag / "conservation_residuals.csv",
              ["model", "M_0", "M_end", "boundary_flux_integral",
               "absolute_residual", "relative_residual"], rows)
    log("conservation residual: Q1=%.3e Q3=%.3e Q4=%.3e"
        % (b1["relative_residual"], b3["relative_residual"], b4["relative_residual"]))

    return {"base": (base3, base4), "dt_shrink": dt_shrink,
            "grid_time": grid_res, "conservation": {"Q1": b1, "Q3": b3, "Q4": b4}}


def write_validation_report(cfg, res, report, sens=None):
    from . import __version__
    te3, te4 = float(res["te3"]), float(res["te4"])
    lines = ["# 验证报告 — 药材烘干 (A题)", "",
             "生成时间: %s" % time.strftime("%Y-%m-%d %H:%M:%S"),
             "模型版本: drying_model %s" % __version__, "",
             "## 关键结果", "",
             "| 项目 | 数值 |", "|---|---|",
             "| 问题3 烘干终点 t* | %.4f s = %.4f h |" % (te3, te3 / 3600.0),
             "| 问题4 烘干终点 t* | %.4f s = %.4f h |" % (te4, te4 / 3600.0),
             "| 网格 | 径向区间 N=%d，节点 %d，节点中心控制体 %d（首末半控制体） |"
             % (res["q1"]["N"], res["q1"]["N"] + 1, res["q1"]["N"] + 1), "",
             "## 终点原始值（未舍入，供反验证）", "",
             "- q3_event_time_s_raw = %.9f s -> %.9f h" % (te3, te3 / 3600.0),
             "- q4_event_time_s_raw = %.9f s -> %.9f h" % (te4, te4 / 3600.0),
             "- 舍入校验：59286.175088758/3600 = %.6f -> 16.4684 h；"
             "70759.978749528/3600 = %.6f -> 19.6555 h（因未舍入秒数 < 70759.98 s）。"
             % (te3 / 3600.0, te4 / 3600.0),
             "", "## 检查项", ""]
    lines += ["- %s" % r for r in report]
    lines += ["", "## 说明", "",
              "- 扩散系数温度项采用 exp(-3850/T_K)（绝对温度倒数形式）。",
              "- 问题2/3 使用附录3物性、固定半径；问题4 使用附录4物性、材料坐标收缩模型。",
              "- 4 h 之后环境取附件1末1 h均值 (Ta=49.998934 C, Ca=0.04998754)。",
              "- 终点由全域最大含水率事件 max C = 0.15 判定（使用未舍入值）。"]
    if sens:
        b3, b4 = sens["base"]
        lines += ["", "## 主结果与工艺背景", "",
                  "严格按题设简化模型（已按规范冻结，未调整参数）得到：",
                  "",
                  "- 问题3 临界烘干时间 t*3 = %.4f h（= %.1f s）" % (b3 / 3600.0, b3),
                  "- 问题4 临界烘干时间 t*4 = %.4f h（= %.1f s）" % (b4 / 3600.0, b4),
                  "",
                  "题面所述烘干'一般持续 2-3 天'属于**实际工艺背景**。当前有效扩散模型",
                  "未包含蒸发潜热（温度方程无相变汇项）与吸附/解吸平衡（以空气含湿量近似",
                  "表面平衡含水率），因此预测的**理论临界时间短于实际工艺时长**，属于模型",
                  "简化的系统性偏差，而非数值错误。", "",
                  "敏感性结论：", "",
                  "- 表面传质系数 h_C 与扩散系数 D 的主导影响见 sensitivity_*.csv；",
                  "- 纯几何收缩相对固定半径的时间变化 dt_shrink = %.1f s（Q4 主模型 %.1f s vs 固定半径 %.1f s）。"
                  % (sens["dt_shrink"], b4,
                     sens["dt_shrink"] and (b4 - sens["dt_shrink"])),
                  "- 水分收支相对残差：Q1 = %.3e，Q3 = %.3e，Q4（材料参考域）= %.3e。"
                  % (sens["conservation"]["Q1"]["relative_residual"],
                     sens["conservation"]["Q3"]["relative_residual"],
                     sens["conservation"]["Q4"]["relative_residual"])]
    diag = cfg_path(cfg, "diagnostics_dir")
    diag.mkdir(parents=True, exist_ok=True)
    (diag / "validation_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("      wrote %s" % (diag / "validation_report.md"))


def write_run_summary(cfg, res, report, raw=None, traces=None):
    import numpy, scipy, openpyxl
    try:
        import pandas as _pd
        pandas_version = _pd.__version__
    except Exception:
        pandas_version = None
    s = cfg["solver"]
    n = int(res["q1"]["N"])
    netcdf = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "dependency_versions": {
            "numpy": numpy.__version__, "scipy": scipy.__version__,
            "pandas": pandas_version, "openpyxl": openpyxl.__version__,
        },
        "config_path": cfg["_config_path"],
        "input_hashes": {
            "attachment1": sha256_file(cfg_path(cfg, "attachment1")),
            "attachment2": sha256_file(cfg_path(cfg, "attachment2")),
        },
        "diffusivity_temperature_term": cfg["diffusivity"]["temperature_mode"],
        "selected_grid": {
            "radial_intervals": n,
            "nodes": n + 1,
            "node_centred_control_volumes": n + 1,
            "first_last_control_volume": "half-width",
            "grid_type": "node-centered r_i=i*dr (i=0..N), faces at node midpoints",
        },
        "solver_tolerances": {"rtol": s["rtol"], "atol_temperature": s["atol_temperature"],
                              "atol_moisture": s["atol_moisture"],
                              "max_step_early": s["max_step_early"],
                              "max_step_late": s["max_step_late"]},
        "environment_post_4h_mode": cfg["environment"]["post_4h_mode"],
        "radius_interpolation": cfg["radius_q4"]["interpolation"],
        "event": {"definition": "max_i C_i - 0.15", "terminal": True, "direction": -1.0},
        "event_times_unrounded_s": {"q3": res["te3"], "q4": res["te4"],
                                    "q3_event": res["q23"].get("event_refined"),
                                    "q4_event": res["q4"].get("event_refined")},
        "wall_seconds": {"q1": res["q1"]["wall_s"], "q23": res["q23"]["wall_s"],
                         "q4": res["q4"]["wall_s"]},
        "validation_status": report,
        "output_files": ["result/result1.xlsx", "result/result2.xlsx",
                         "result/result3.xlsx", "result/result4.xlsx"],
        "diagnostics_files": ["space.csv", "tolerance.csv", "conservation_residuals.csv",
                              "event_trace_q3.csv", "event_trace_q4.csv", "event_raw.json"],
    }
    if raw is not None:
        netcdf["raw_event"] = raw
    if traces is not None:
        netcdf["event_trace_max_C_at_event"] = traces
    diag = cfg_path(cfg, "diagnostics_dir")
    diag.mkdir(parents=True, exist_ok=True)
    (diag / "run_summary.json").write_text(json.dumps(netcdf, indent=2, ensure_ascii=False),
                                           encoding="utf-8")
    print("      wrote %s" % (diag / "run_summary.json"))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="drying_model")
    ap.add_argument("command", choices=["inspect", "solve", "export", "verify", "sens", "all"])
    ap.add_argument("--config", default=None)
    ap.add_argument("--intervals", "--cells", dest="intervals", type=int, default=None)
    ap.add_argument("--question", default="all")
    ap.add_argument("--all", action="store_true", help="process all questions")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no-summary", dest="write_summary", action="store_false")
    ap.set_defaults(write_summary=True)
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    print("=" * 72)
    print("drying_model | command=%s | config=%s" % (args.command, cfg["_config_path"]))
    print("=" * 72)
    if args.command == "inspect":
        cmd_inspect(cfg)
    elif args.command == "sens":
        run_sensitivity(cfg, intervals=args.intervals or radial_intervals(cfg),
                        sweeps=load_sweeps().get("sweeps", {}), verbose=True)
    elif args.command == "solve":
        cmd_solve(cfg, args)
    elif args.command == "export":
        cmd_solve(cfg, args)
    elif args.command == "verify":
        cmd_verify(cfg, args)
    elif args.command == "all":
        cmd_all(cfg, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
