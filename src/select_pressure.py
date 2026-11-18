"""Choose the pressure definition by out-of-sample validation.  Run:  python -m src.select_pressure

The combined pressure index has two settings that were set by judgement: the component weights
(match situation / tournament stakes / form) and the share of deliveries treated as high pressure.
This script tests a fixed grid of definitions and keeps the one whose ratings best predict future
pressure performance.

For every definition:
  1. Build the high-pressure flag with that definition (cup.add_pressure).
  2. Rate players on 2022-24 only, with rating weights also taken from 2022-24 (no look-ahead).
  3. Score the definition by how well the 2022-24 rating predicts unshrunk 2025-26 pressure performance
     (runs above same-situation peers for batters, runs conceded below peers for bowlers).

Criterion: mean of the batter and bowler correlations. Secondary: Spearman correlation between the 2022-24
and 2025-26 ratings. The script reports the comparison; the definition actually used is set in src/cup.py
(BASE_CPI / CPI_WEIGHTS / PRESSURE_SHARE). With ~40 players per group the estimates are noisy (neighbouring
definitions differ by up to 0.2), and selecting the best of 21 overstates its advantage, so a result here is
treated as evidence to weigh, not an automatic switch. See outputs/METHODOLOGY_NOTES.md for the decision.
Writes outputs/pressure_selection.csv and outputs/pressure_selection.md.
"""
import numpy as np
import pandas as pd

from . import config as C
from . import cup

WEIGHT_SETS = {"0.5/0.3/0.2": (0.5, 0.3, 0.2), "1/0/0": (1.0, 0.0, 0.0), "0.6/0.4/0": (0.6, 0.4, 0.0),
               "1/3 each": (1 / 3, 1 / 3, 1 / 3), "0.6/0.2/0.2": (0.6, 0.2, 0.2), "0.4/0.4/0.2": (0.4, 0.4, 0.2),
               "0.7/0.2/0.1": (0.7, 0.2, 0.1)}
SHARES = [0.20, 0.30, 0.40]
BASELINE = ("0.5/0.3/0.2", 0.30)
TIE = 0.05


def evaluate(s: pd.DataFrame, share: float) -> dict:
    """Out-of-sample scores for the pressure flags currently in `s`."""
    early, late = s[s["match_date"].dt.year <= 2024], s[s["match_date"].dt.year >= 2025]
    res = {}
    for role, f in [("bat", cup.batting_table), ("bowl", cup.bowling_table)]:
        te, _, rel = f(early)
        tl, _, _ = f(late)
        w = cup.data_weights(rel)                                   # weights from the early period only
        need = cup.ELIGIBLE[role]["p_balls"] / 2 * share / 0.30     # same evidence bar whatever the cut-off
        both = [p for p in te.index.intersection(tl.index)
                if te.at[p, "all_p_balls"] >= need and tl.at[p, "all_p_balls"] >= need]
        sign = 1 if role == "bat" else -1
        early_r = cup.cup_score(te.loc[both].copy(), role, w)
        late_r = cup.cup_score(tl.loc[both].copy(), role, w)
        target = sign * tl.loc[both, "p_runs_ae_raw"]
        ok = early_r.notna() & target.notna()
        res[role] = {"n": int(ok.sum()), "predictive_r": float(np.corrcoef(early_r[ok], target[ok])[0, 1]),
                     "stability": float(early_r.corr(late_r, method="spearman"))}
    return res


def main():
    s = cup.load()
    rows = []
    original_share = cup.PRESSURE_SHARE
    for share in SHARES:
        cup.PRESSURE_SHARE = share
        for label, (wm, wt, wi) in WEIGHT_SETS.items():
            cup.add_pressure(s, wm, wt, wi)
            r = evaluate(s, share)
            rows.append({"weights (situation/stakes/form)": label, "high-pressure share": share,
                         "batters n": r["bat"]["n"], "batters r": r["bat"]["predictive_r"],
                         "bowlers n": r["bowl"]["n"], "bowlers r": r["bowl"]["predictive_r"],
                         "mean r": (r["bat"]["predictive_r"] + r["bowl"]["predictive_r"]) / 2,
                         "mean stability": (r["bat"]["stability"] + r["bowl"]["stability"]) / 2})
            print(f"  {label:12s} share {share:.0%}: mean r {rows[-1]['mean r']:.3f}")
    cup.PRESSURE_SHARE = original_share
    t = pd.DataFrame(rows).sort_values("mean r", ascending=False).reset_index(drop=True)
    base = t[(t["weights (situation/stakes/form)"] == BASELINE[0]) & (t["high-pressure share"] == BASELINE[1])].iloc[0]
    best = t.iloc[0]
    t["in use"] = (t["weights (situation/stakes/form)"] == BASELINE[0]) & (t["high-pressure share"] == BASELINE[1])
    t.to_csv(C.OUTPUTS / "pressure_selection.csv", index=False)
    by_share = t.groupby("high-pressure share")["mean r"].mean()
    verdict = (f"Highest-scoring definition: weights {best['weights (situation/stakes/form)']}, top {best['high-pressure share']:.0%} "
               f"(mean r {best['mean r']:.3f}). Definition in use (0.5/0.3/0.2, top 30%): mean r {base['mean r']:.3f}. "
               f"Average mean r by cut-off: " + ", ".join(f"{k:.0%} {v:.3f}" for k, v in by_share.items()) + ".")
    txt = "\n".join(["# Pressure definition selection (out-of-sample, 2022-24 -> 2025-26)\n", verdict, "",
                     t.round(3).to_markdown(index=False)])
    (C.OUTPUTS / "pressure_selection.md").write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
