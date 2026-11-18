"""Match Situation Pressure (MSP) for the FIRST innings + combined MSP table.
Run (after src.pressure_msp):  python -m src.pressure_msp1

There is no target in the first innings, so:
1. Remaining-runs model: E[runs still to come | balls left, wickets in hand, scoring environment,
   venue par, current run rate]. Gradient boosting with MONOTONIC constraints (more balls or more
   wickets can never mean fewer expected runs). Spread (sd) estimated from residuals by balls left.
2. First-innings win probability = sum over possible final totals T of
       P(final total = T | current state) x (1 - chase WP at the start of the chase with target T+1).
   This reuses the validated chase model, so the two innings join up: WP at the last ball of
   innings 1 equals 1 - chase WP at the first ball of innings 2 (checked below).
3. Leverage / WPA / MSP computed exactly as for the chase, then both innings are put on one
   0-100 scale (msp) so a first-innings ball and a chase ball are directly comparable.

All models are trained on matches before TEST_START and evaluated on later matches; venue par and
scoring environment use strictly earlier matches only.
"""
import os

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))  # silences a Windows joblib core-count warning

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error, roc_auc_score

from . import config as C
from .pressure_msp import (OUTCOMES, ChaseWinModel, EndgameDP, HybridWP, TEST_START, chase_frame,
                           outcome_probs, scoring_environment)

VENUE_SHRINK = 5        # prior matches' worth of weight given to the competition-wide scoring rate
T_MAX = 330             # largest first-innings total considered
RR_FEATURES = ["balls_remaining", "wickets_in_hand", "env", "venue_rr", "crr", "is_ipl"]
RR_MONOTONE = [1, 1, 1, 1, 0, 0]
OUT_FILE = C.PROCESSED / "pressure_msp.parquet"


# ---------------------------------------------------------------- leakage-safe venue par
def venue_run_rate(s: pd.DataFrame, env: pd.Series) -> pd.Series:
    """Run rate at the venue in earlier matches, shrunk towards the scoring environment."""
    per = s.groupby(["venue_id", "match_date", "match_id"]).agg(
        runs=("total_runs", "sum"), balls=("legal_ball", "sum")).reset_index().sort_values(["match_date", "match_id"])
    per["prior_runs"] = per.groupby("venue_id")["runs"].cumsum() - per["runs"]
    per["prior_balls"] = per.groupby("venue_id")["balls"].cumsum() - per["balls"]
    per["n_prior"] = per.groupby("venue_id").cumcount()
    # same-date matches at a venue must not see each other
    first = per.groupby(["venue_id", "match_date"])[["prior_runs", "prior_balls", "n_prior"]].transform("first")
    per[["prior_runs", "prior_balls", "n_prior"]] = first
    e = per["match_id"].map(env)
    venue_rr = np.where(per["prior_balls"] > 0, per["prior_runs"] * 6 / per["prior_balls"].replace(0, np.nan), e)
    shrunk = (per["n_prior"] * venue_rr + VENUE_SHRINK * e) / (per["n_prior"] + VENUE_SHRINK)
    return pd.Series(shrunk.values, index=per["match_id"].values)


def first_innings_frame(s: pd.DataFrame) -> pd.DataFrame:
    """First-innings balls with scoring environment, venue rate, final total and remaining-runs target."""
    env = scoring_environment(s)
    f = s[s["innings"] == 1].copy()
    f["env"] = f["match_id"].map(env)
    f["venue_rr"] = f["match_id"].map(venue_run_rate(s, env))
    f["is_ipl"] = f["competition_group"].eq("IPL")
    f["crr"] = f["current_run_rate"].fillna(f["env"])
    end = f.groupby("match_id").tail(1).set_index("match_id")
    f["final_total"] = f["match_id"].map(end["score_after"])
    # innings that ran their natural course (all out, or used the full allocation) -> valid regression target
    complete = (end["wickets_after"] >= 10) | (end["legal_balls_after"] >= end["innings_limit_balls"])
    f["innings_complete"] = f["match_id"].map(complete)
    f["remaining_runs"] = f["final_total"] - f["score_before"]
    f["y"] = f["batting_team_won"]
    return f


# ---------------------------------------------------------------- models
class RemainingRuns:
    """Predicts runs still to come in a first innings (monotonic gradient boosting) and its uncertainty."""
    def __init__(self):
        """Gradient boosting with monotonic constraints: more balls/wickets never mean fewer expected runs."""
        self.reg = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                                 min_samples_leaf=200, monotonic_cst=RR_MONOTONE, random_state=0)
        self.sd_table = None

    def fit(self, f):
        """Fit the mean model and tabulate the residual standard deviation by balls remaining."""
        self.reg.fit(f[RR_FEATURES], f["remaining_runs"])
        res = f["remaining_runs"] - self.reg.predict(f[RR_FEATURES])
        bins = pd.cut(f["balls_remaining"], np.arange(-1, 121, 6))
        self.sd_table = res.groupby(bins, observed=True).std().rename(lambda iv: iv.right)
        return self

    def mean(self, X) -> np.ndarray:
        """Expected runs still to come (never negative)."""
        return np.maximum(self.reg.predict(X[RR_FEATURES]), 0)

    def sd(self, balls_remaining) -> np.ndarray:
        """Uncertainty (sd) of runs still to come, interpolated by balls remaining; 0 when no balls are left."""
        b = np.asarray(balls_remaining, float)
        x, y = np.r_[0, self.sd_table.index.values.astype(float)], np.r_[0, self.sd_table.values]
        return np.interp(b, x, y)


class FirstInningsWP:
    """WP of the side batting first = E over final total T of (1 - chase WP at start of chase, target T+1)."""

    def __init__(self, rr: RemainingRuns, chase: HybridWP):
        """Combine a remaining-runs model with a chase win-probability model."""
        self.rr, self.chase = rr, chase
        self.grid = np.arange(T_MAX + 1)

    def defend_curve(self, limit, is_ipl, env) -> np.ndarray:
        """P(batting-first side wins | final total T) for T = 0..T_MAX, for one match."""
        n = len(self.grid)
        return 1 - self.chase.predict(self.grid + 1, np.full(n, limit), np.full(n, 10), np.full(n, is_ipl), np.full(n, env))

    def wp(self, score, balls_rem, wkts_in_hand, X, curve) -> np.ndarray:
        """Vectorised over the rows of one match (same curve)."""
        score, b, w = (np.asarray(v, float) for v in (score, balls_rem, wkts_in_hand))
        finished = (b <= 0) | (w <= 0)
        mu = score + np.where(finished, 0, self.rr.mean(X.assign(balls_remaining=b, wickets_in_hand=w)))
        sd = np.where(finished, 0, np.maximum(self.rr.sd(b), 1e-6))
        edges = self.grid[None, :] + 0.5
        cdf = norm.cdf((edges - mu[:, None]) / np.where(sd > 0, sd, 1)[:, None])
        cdf = np.where(sd[:, None] > 0, cdf, (edges >= mu[:, None]).astype(float))
        cdf = np.where(edges < score[:, None], 0.0, cdf)       # final total can't be below current score
        pmf = np.diff(np.c_[np.zeros(len(mu)), cdf], axis=1)
        pmf[:, -1] += 1 - cdf[:, -1]
        return pmf @ curve


def score_innings1(f: pd.DataFrame, wpm: FirstInningsWP, probs: pd.DataFrame) -> pd.DataFrame:
    """Per first-innings ball: win probability before/after, leverage (expected |WP swing|) and WPA."""
    f = f.copy()
    out = {k: np.zeros(len(f)) for k in ["wp_before", "wp_after", "leverage"]}
    pr_all = probs.reindex(f["innings_phase"]).fillna(probs.mean())
    pos = 0
    for mid, g in f.groupby("match_id", sort=False):
        r = g.iloc[0]
        curve = wpm.defend_curve(r["innings_limit_balls"], r["is_ipl"], r["env"])
        X = g[RR_FEATURES]
        S, B, W = g["score_before"].values, g["balls_remaining"].values, g["wickets_in_hand"].values
        wb = wpm.wp(S, B, W, X, curve)
        wa = wpm.wp(g["score_after"].values, g["innings_limit_balls"].values - g["legal_balls_after"].values,
                    10 - g["wickets_after"].values, X, curve)
        lev = np.zeros(len(g))
        pr = pr_all.iloc[pos:pos + len(g)]
        for k, (dr, db, dw) in OUTCOMES.items():
            lev += pr[k].values * np.abs(wpm.wp(S + dr, B - db, W - dw, X, curve) - wb)
        live = (B > 0) & (W > 0)
        idx = slice(pos, pos + len(g))
        out["wp_before"][idx], out["wp_after"][idx], out["leverage"][idx] = wb, wa, np.where(live, lev, 0)
        pos += len(g)
    for k, v in out.items():
        f[k] = v
    f["wpa"] = f["wp_after"] - f["wp_before"]
    return f


def wp_metrics(y, p, name):
    """Log loss, Brier score and AUC on decided matches."""
    m = np.isin(y, [0, 1])
    y, p = np.asarray(y)[m], np.clip(np.asarray(p)[m], 1e-6, 1 - 1e-6)
    return {"model": name, "balls": len(y), "log_loss": log_loss(y, p), "brier": brier_score_loss(y, p), "auc": roc_auc_score(y, p)}


def main():
    """Validate the first-innings models out of time, score all first-innings balls and build the combined MSP table."""
    s = pd.read_parquet(C.PROCESSED / "match_state.parquet")
    f = first_innings_frame(s)
    f = f.sort_values(["match_id", "innings_ball_num"]).reset_index(drop=True)
    is_train = f["match_date"] < TEST_START
    reg_rows = f["innings_complete"] & f["state_reliable"] & (f["balls_remaining"] > 0)
    rep = ["# First-innings Match Situation Pressure\n"]

    # ---- 1. remaining-runs model, out-of-time
    rr = RemainingRuns().fit(f[reg_rows & is_train])
    te = f[reg_rows & ~is_train]
    naive = te["crr"] * te["balls_remaining"] / 6
    envp = te["env"] * te["balls_remaining"] / 6
    rows = [("Current run rate x overs left", mean_absolute_error(te["remaining_runs"], naive)),
            ("Scoring environment x overs left", mean_absolute_error(te["remaining_runs"], envp)),
            ("Remaining-runs model (monotonic GBM)", mean_absolute_error(te["remaining_runs"], rr.mean(te)))]
    rep += [f"## 1. Runs still to come: test MAE on {te['match_id'].nunique()} 2025-26 first innings (lower is better)",
            pd.DataFrame(rows, columns=["method", "MAE (runs)"]).round(2).to_markdown(index=False)]
    at = te[te["legal_balls_before"].isin([0, 36, 60, 96])]
    rep += ["\nMAE of predicted FINAL total at key points:",
            at.assign(err=(at["score_before"] + rr.mean(at) - at["final_total"]).abs())
              .groupby("legal_balls_before")["err"].mean().rename(lambda b: f"after {b // 6} overs").round(1).to_frame("MAE").T.to_markdown()]

    # ---- 2. first-innings WP, out-of-time (chase model also train-only)
    c = chase_frame(s)
    cfit = c["state_reliable"] & c["y"].isin([0, 1]) & (c["R"] > 0) & (c["B"] > 0) & (c["W"] > 0)
    ctr = c[cfit & (c["match_date"] < TEST_START)]
    pr_tr = outcome_probs(ctr)
    chase_tr = HybridWP(ChaseWinModel().fit(ctr), EndgameDP(pr_tr.loc["Death"].to_dict()))
    test_all = f[~is_train & f["state_reliable"]].reset_index(drop=True)
    scored = score_innings1(test_all, FirstInningsWP(rr, chase_tr), outcome_probs(f[is_train]))
    base = f[is_train].drop_duplicates("match_id")["y"].isin([1]).mean()
    rep += ["\n## 2. First-innings win probability on 2025-26 (out-of-time)",
            pd.DataFrame([wp_metrics(scored["y"], np.full(len(scored), base), "Constant"),
                          wp_metrics(scored["y"], scored["wp_before"], "First-innings WP model")]).round(4).to_markdown(index=False)]
    sc = scored[scored["y"].isin([0, 1])]
    rep += ["\nAccuracy by stage of the first innings (AUC grows as the innings reveals more):",
            sc.groupby(pd.cut(sc["legal_balls_before"], [-1, 35, 71, 107, 120], labels=["overs 1-6", "7-12", "13-18", "19-20"]),
                       observed=True).apply(lambda g: pd.Series({"auc": roc_auc_score(g["y"], g["wp_before"]),
                                                                 "mean_pred": g["wp_before"].mean(), "actual": g["y"].mean()}))
              .round(3).to_markdown()]

    # ---- 3. production: all data
    rr_all = RemainingRuns().fit(f[reg_rows])
    pr_c = outcome_probs(c[cfit])
    chase_all = HybridWP(ChaseWinModel().fit(c[cfit]), EndgameDP(pr_c.loc["Death"].to_dict()))
    f1 = score_innings1(f, FirstInningsWP(rr_all, chase_all), outcome_probs(f[f["state_reliable"]]))
    f1["batting_pressure_dir"] = 1 - f1["wp_before"]
    f1["bowling_pressure_dir"] = f1["wp_before"]

    inn2 = pd.read_parquet(C.PROCESSED / "pressure_msp_inn2.parquet").drop(columns=["leverage_index", "msp"])
    cols = ["match_id", "innings", "innings_ball_num", "wp_before", "wp_after", "wpa", "leverage",
            "batting_pressure_dir", "bowling_pressure_dir"]
    allp = pd.concat([f1[cols], inn2[cols]], ignore_index=True)
    mean_lev = allp.loc[allp["leverage"] > 0, "leverage"].mean()
    allp["leverage_index"] = allp["leverage"] / mean_lev
    allp["msp"] = allp["leverage"].rank(pct=True) * 100
    allp.to_parquet(OUT_FILE, index=False)

    # ---- 4. sanity checks
    last1 = f1.groupby("match_id").tail(1).set_index("match_id")["wp_after"]
    first2 = inn2.sort_values("innings_ball_num").groupby("match_id").head(1).set_index("match_id")["wp_before"]
    j = pd.concat([last1, 1 - first2], axis=1, keys=["end_inn1", "start_inn2"]).dropna()
    rep += ["\n## 3. Sanity checks",
            f"- Innings join-up: |WP at end of innings 1 - (1 - chase WP at start of innings 2)| "
            f"mean {(j['end_inn1'] - j['start_inn2']).abs().mean():.4f}, max {(j['end_inn1'] - j['start_inn2']).abs().max():.4f} "
            f"over {len(j)} matches"]
    st = s[["match_id", "innings", "innings_ball_num", "overid", "competition_group", "knock_out"]]
    a = allp.merge(st, on=["match_id", "innings", "innings_ball_num"])
    rep += ["- Mean MSP by innings and over (0-100, one scale for both innings):",
            a.pivot_table(index="innings", columns="overid", values="msp", aggfunc="mean").round(0).to_markdown(),
            f"\n- Mean MSP in knockout matches {a.loc[a['knock_out'] == 1, 'msp'].mean():.1f} vs others "
            f"{a.loc[a['knock_out'] == 0, 'msp'].mean():.1f} (MSP measures the match situation only; stakes are added separately)"]
    ex = f1[f1["match_id"] == f1["match_id"].iloc[0]]
    rep += ["\nExample first innings (every 4th over end): projected WP of batting side",
            ex[ex["over_ball_num"] == 6].iloc[::4][["overid", "score_after", "wickets_after", "wp_after"]].round(3).to_markdown(index=False)]
    txt = "\n".join(rep)
    print(txt)
    (C.OUTPUTS / "msp_inn1_report.md").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
