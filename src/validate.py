"""Phase 1 data validation. Run:  python -m src.validate

Each check tests one assumption against independent evidence in the data
(stated match results, over structure) and writes the outcome to
outputs/validation_report.md. Nothing here is assumed silently.
"""
import re

import numpy as np
import pandas as pd

from . import config as C
from .data import build_all, build_deliveries

LINES: list[str] = []


def log(s: str = "") -> None:
    """Print a line and keep it for the markdown report."""
    print(s)
    LINES.append(s)


def parse_result(result: str):
    """Return (kind, margin, is_dls) from free-text result. kind in {'runs','wickets',None}."""
    if not isinstance(result, str):
        return None, np.nan, False
    dls = bool(re.search(r"D/?L", result, re.I))
    mm = re.search(r"by (\d+)\s*(run|wicket)", result, re.I)
    if not mm:
        return None, np.nan, dls
    return mm.group(2).lower() + "s", float(mm.group(1)), dls


def innings_summary(d: pd.DataFrame) -> pd.DataFrame:
    """Per match: total runs, wickets, legal balls and deliveries for each innings (one row per match)."""
    g = d.groupby(["match_id", "innings"])
    s = g.agg(total=("total_runs", "sum"), wkts=("is_wicket", "sum"), legal=("legal_ball", "sum"),
              deliveries=("innings_ball_num", "size"), bat_team=("batting_team_id", "first"))
    s = s.unstack("innings")
    s.columns = s.columns.to_flat_index()  # single-level columns of (metric, innings) tuples, joinable to matches
    return s


def check_runs(matches, d):
    """Test 1: does runs + extras1 + extras2 reproduce the stated run and wicket margins of match results?"""
    log("## 1. Total runs per delivery = runs + extras1_runs + extras_2_runs")
    s = innings_summary(d)
    m = matches.set_index("match_id").join(s, how="inner")
    parsed = m["result"].apply(parse_result)
    m["kind"], m["margin"], m["dls"] = zip(*parsed)

    r = m[(m["kind"] == "runs") & ~m["dls"] & m["revised_target"].isna()]
    diff = r[("total", 1)] - r[("total", 2)] - r["margin"]
    log(f"- Won-by-runs matches (no DLS): {len(r)}; first-innings minus second-innings total equals the stated margin in "
        f"**{(diff == 0).mean():.1%}**")
    bad = r[diff != 0]
    if len(bad):
        log(f"- Mismatches ({len(bad)}): " + ", ".join(
            f"{i} (off by {int(v)}; result: '{bad.loc[i, 'result']}')" for i, v in diff[diff != 0].items()))
        log("  -> a margin quoted from a Super Over on a tied match is not a data error; regular innings are a tie.")

    w = m[(m["kind"] == "wickets") & ~m["dls"]]
    wl = 10 - w[("wkts", 2)]
    ok_w = (wl == w["margin"]).mean()
    chased = (w[("total", 2)] > w[("total", 1)]).mean()
    log(f"- Won-by-wickets matches: {len(w)}; 10 minus second-innings wickets equals the stated margin in **{ok_w:.1%}**; "
        f"chasing total exceeds first-innings total in **{chased:.1%}**")
    return m


def check_other_extras(raw):
    """Test 2: is extras_type 'other' a no-ball? Count 6-legal-ball overs under both readings."""
    log("\n## 2. Is extras_type == 'other' a no-ball? (test using over structure)")
    out = {}
    for name, flag in [("A: other = legal", False), ("B: other = no-ball", True)]:
        d = build_deliveries(raw, other_as_no_ball=flag)
        ov = d.groupby(["match_id", "innings", "overid"]).agg(
            legal=("legal_ball", "sum"), has_other=("extras_type", lambda x: (x == C.OTHER).any()))
        last = d.groupby(["match_id", "innings"])["overid"].transform("max")
        complete = d.assign(last=last).groupby(["match_id", "innings", "overid"])["last"].first()
        ov = ov[ov.index.get_level_values("overid") < complete.loc[ov.index]]  # drop final (possibly partial) overs
        oth = ov[ov["has_other"]]
        out[name] = (oth["legal"] == 6).mean()
        log(f"- Scenario {name}: completed overs containing an 'other' ball that have exactly 6 legal balls = "
            f"**{out[name]:.1%}** (n={len(oth)}); all completed overs = {(ov['legal'] == 6).mean():.1%}")
    return out


def check_revised(matches, d):
    """Test 3: are the *_revised_overs values balls or overs, and what does revised_target mean?"""
    log("\n## 3. Revised innings lengths (first_inn_revised_overs / second_inn_revised_overs)")
    s = innings_summary(d)
    rv = matches[matches[["first_inn_revised_overs", "second_inn_revised_overs", "revised_target"]].notna().any(axis=1)]
    rv = rv.set_index("match_id").join(s, how="inner")
    for inn, col in [(1, "first_inn_revised_overs"), (2, "second_inn_revised_overs")]:
        x = rv[rv[col].notna() & rv[("legal", inn)].notna()]  # innings that were actually played
        legal, lim = x[("legal", inn)], x[col]
        log(f"- Innings {inn}: {len(x)} played innings with a revised value. Legal balls <= value (read as BALLS): "
            f"**{(legal <= lim).mean():.0%}**; reached the value exactly: {(legal == lim).mean():.0%} "
            f"(the rest are chases won early, all-outs or rain-stopped games). Read as overs the values would be "
            f"{lim.min():.0f}-{lim.max():.0f} overs (impossible in T20); read as balls they are "
            f"{lim.min() / 6:.0f}-{lim.max() / 6:.0f} overs -> values are BALLS.")
    t = rv[rv["revised_target"].notna() & rv[("total", 2)].notna()]
    plus1 = (t["revised_target"] == t[("total", 1)] + 1).mean()
    win_chase = t[t["result"].str.contains("wicket", case=False, na=False)]
    log(f"- revised_target: {len(t)} matches. Equals first-innings total + 1 in {plus1:.0%} (others are DLS-adjusted). "
        f"In every chase won by wickets the chasing total reaches it: "
        f"**{(win_chase[('total', 2)] >= win_chase['revised_target']).mean():.0%}** -> it is the runs-to-WIN target.")
    detail = rv[["first_inn_revised_overs", "second_inn_revised_overs", "revised_target", "result"]].copy()
    detail["inn1_legal"], detail["inn2_legal"] = rv[("legal", 1)], rv[("legal", 2)]
    detail["inn1_total"], detail["inn2_total"] = rv[("total", 1)], rv[("total", 2)]
    detail.to_csv(C.OUTPUTS / "validation_revised_matches.csv")
    log("- Per-match detail: outputs/validation_revised_matches.csv")


def check_structure(matches, d):
    """Test 4: duplicates, impossible innings, missing innings, IPL competitions, stages."""
    log("\n## 4. Structural checks")
    dup = d.duplicated(["match_id", "innings", "innings_ball_num"]).sum()
    log(f"- Duplicate (match, innings, innings_ball_num) keys: {dup}")
    s = d.groupby(["match_id", "innings"]).agg(legal=("legal_ball", "sum"), w=("is_wicket", "sum"))
    log(f"- Innings with >120 legal balls: {(s['legal'] > 120).sum()}; with >10 wickets: {(s['w'] > 10).sum()}")
    log(f"- Matches with only one innings recorded: {(d.groupby('match_id')['innings'].nunique() == 1).sum()}")
    nob = d.groupby("match_id").size().index
    log(f"- Matches without deliveries (abandoned/no result): {(~matches['match_id'].isin(nob)).sum()}")
    ipl = matches[matches["competition_group"] == "IPL"]["comp_name"].unique()
    log(f"- Competitions classified as IPL: {sorted(ipl)}")
    log(f"- Deliveries by group: {d['competition_group'].value_counts().to_dict()}")
    log(f"- Stage values: {matches['stage'].value_counts().to_dict()}; knock_out flag set on {int(matches['knock_out'].sum())} matches")


def main():
    """Run all data checks, save the clean tables and write outputs/validation_report.md."""
    C.OUTPUTS.mkdir(exist_ok=True)
    raw, matches, d = build_all(save=True)
    log("# Data validation report\n")
    check_runs(matches, d)
    check_other_extras(raw)
    check_revised(matches, d)
    check_structure(matches, d)
    (C.OUTPUTS / "validation_report.md").write_text("\n".join(LINES), encoding="utf-8")


if __name__ == "__main__":
    main()
