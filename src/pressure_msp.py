"""Match Situation Pressure (MSP) for the SECOND innings.  Run:  python -m src.pressure_msp

Pipeline
1. Chase win-probability model  WP(R, B, W, env) for the batting side, where
     R = runs required, B = legal balls remaining, W = wickets in hand (before the ball),
     env = scoring environment = mean run rate of the previous ENV_WINDOW matches in the same
           competition group (strictly earlier matches -> no leakage; captures scoring inflation).
   Interpretable logistic regression on cricket features. Trained only on matches BEFORE
   TEST_START and evaluated on later matches (chronological split).
2. Per-ball quantities (one situation, shared by batter and bowler):
     wp_before / wp_after : chasing side's win probability before / after the ball
     wpa                  : wp_after - wp_before  (batter credit; bowler gets -wpa)
     leverage             : EXPECTED |change in WP| over the possible outcomes of this ball
                            (dot, 1, 2, 3, 4, 6, wicket, extra), weighted by how often each
                            happens in that phase (from training data). Standard leverage idea.
     leverage_index       : leverage / average leverage  (1.0 = an average chase ball)
     msp                  : leverage as a 0-100 percentile across all chase balls
   Directional components for role-specific use:
     batting_pressure_dir : 1 - wp_before (how far behind the chase is)
     bowling_pressure_dir : wp_before      (how far ahead the batting side is)
"""
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C

sys.setrecursionlimit(20000)  # EndgameDP recursion depth ~ runs required + balls left
TEST_START = pd.Timestamp("2025-01-01")
ENV_WINDOW = 40
OUT_FILE = C.PROCESSED / "pressure_msp_inn2.parquet"
FEATURES = ["rrr_rel", "rrr", "log_r", "log_b", "w", "w_sq", "rrr_x_wlost", "r_per_wkt", "is_ipl"]
# outcome -> (runs added, legal balls used, wickets lost)
OUTCOMES = {"dot": (0, 1, 0), "1": (1, 1, 0), "2": (2, 1, 0), "3": (3, 1, 0), "4": (4, 1, 0),
            "6": (6, 1, 0), "wicket": (0, 1, 1), "extra": (1, 0, 0)}


# ---------------------------------------------------------------- scoring environment
def scoring_environment(s: pd.DataFrame) -> pd.Series:
    """Run rate (runs per over) of the previous ENV_WINDOW matches in the same competition group.
    Uses only matches finished BEFORE the current match date (shift by date, not by row)."""
    per = s.groupby(["competition_group", "match_date", "match_id"]).agg(
        runs=("total_runs", "sum"), balls=("legal_ball", "sum")).reset_index().sort_values(["match_date", "match_id"])
    out = []
    for grp, g in per.groupby("competition_group"):
        roll_r = g["runs"].rolling(ENV_WINDOW, min_periods=10).sum().shift(1)
        roll_b = g["balls"].rolling(ENV_WINDOW, min_periods=10).sum().shift(1)
        env = roll_r * 6 / roll_b
        # matches on the same date must not see each other: use value of the first match of that date
        env = env.groupby(g["match_date"].values).transform("first")
        out.append(pd.Series(env.values, index=g["match_id"].values))
    env = pd.concat(out)
    return env.fillna(env.median())


# ---------------------------------------------------------------- model
def features(R, B, W, is_ipl, env) -> pd.DataFrame:
    """Model inputs from runs required (R), legal balls left (B), wickets in hand (W), IPL flag and scoring environment."""
    R, B, W, env = (np.asarray(x, float) for x in (R, B, W, env))
    rrr = np.clip(R * 6 / np.maximum(B, 1), 0, 36)
    return pd.DataFrame({
        "rrr_rel": rrr / env,                        # required rate relative to the current scoring environment
        "rrr": rrr,                                  # required run rate (capped at 36)
        "log_r": np.log1p(np.maximum(R, 0)),         # size of the task
        "log_b": np.log1p(np.maximum(B, 0)),         # time left
        "w": W,                                      # resources left
        "w_sq": W ** 2,                              # the last few wickets matter more
        "rrr_x_wlost": rrr * (10 - W) / 10,          # a high rate is harder with the tail in
        "r_per_wkt": np.maximum(R, 0) / (W + 1),     # runs each remaining wicket must deliver
        "is_ipl": np.asarray(is_ipl, float),
    })


class ChaseWinModel:
    """Logistic-regression win probability of the chasing side (interpretable coefficients)."""
    def __init__(self):
        """Standardise features, then logistic regression."""
        self.model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=3000))

    def fit(self, df):
        """Fit on a chase frame with columns R, B, W, is_ipl, env and label y (1 = chaser won)."""
        self.model.fit(features(df.R, df.B, df.W, df.is_ipl, df.env)[FEATURES], df.y)
        return self

    def predict(self, R, B, W, is_ipl, env) -> np.ndarray:
        """WP of the chasing side, with cricket's terminal states set exactly."""
        R, B, W = (np.asarray(x, float) for x in (R, B, W))
        p = self.model.predict_proba(features(R, B, W, is_ipl, env)[FEATURES])[:, 1]
        done = (B <= 0) | (W <= 0)
        p = np.where(done & (R > 0), np.where((R == 1) & (W > 0), 0.5, 0.0), p)  # out of balls/wickets (1 short = tie)
        return np.where(R <= 0, 1.0, p)                                           # target reached

    def coefficients(self) -> pd.Series:
        """Standardised coefficients, sorted (positive = raises chase win probability)."""
        return pd.Series(self.model[-1].coef_[0], index=FEATURES).sort_values()


class EndgameDP:
    """Exact win probability for the last few balls by recursion over ball outcomes.

    WP(R, B, W) = sum_k p_k * WP(state after outcome k), with death-overs outcome frequencies
    from training data. Near the end a logistic curve is too smooth (it gave 6-off-1 ~1%,
    while ~8% of death balls are sixes); this recursion is exact under its assumptions.
    """
    def __init__(self, death_probs: dict):
        """Store death-overs outcome probabilities and an empty memo cache."""
        self.p = death_probs
        self.cache: dict = {}

    def wp(self, R: int, B: int, W: int) -> float:
        """Exact chase win probability for one (runs required, balls left, wickets in hand) state, memoised."""
        if R <= 0:
            return 1.0
        if B <= 0 or W <= 0:
            return 0.5 if (R == 1 and W > 0) else 0.0
        key = (R, B, W)
        if key not in self.cache:
            v = sum(self.p[k] * self.wp(R - dr, B - db, W - dw) for k, (dr, db, dw) in OUTCOMES.items())
            self.cache[key] = v
        return self.cache[key]

    def predict(self, R, B, W) -> np.ndarray:
        """Vectorised wrapper around wp() for many states."""
        return np.array([self.wp(int(r), int(b), int(w)) for r, b, w in zip(R, B, W)])


class HybridWP:
    """Endgame recursion for the last DP_FULL balls, blending linearly into the logistic model by DP_ZERO balls."""
    DP_FULL, DP_ZERO = 6, 30

    def __init__(self, logit: ChaseWinModel, dp: EndgameDP):
        """Combine a fitted ChaseWinModel with an EndgameDP."""
        self.logit, self.dp = logit, dp

    def predict(self, R, B, W, is_ipl, env) -> np.ndarray:
        """Chase win probability: endgame recursion near the end, logistic model earlier, linear blend in between."""
        R, B, W = (np.asarray(x, float) for x in (R, B, W))
        p = self.logit.predict(R, B, W, is_ipl, env)
        w = np.clip((self.DP_ZERO - B) / (self.DP_ZERO - self.DP_FULL), 0, 1)
        idx = np.flatnonzero(w > 0)
        if len(idx):
            p[idx] = w[idx] * self.dp.predict(R[idx], B[idx], W[idx]) + (1 - w[idx]) * p[idx]
        p = np.where(R <= 0, 1.0, p)
        return p


def outcome_probs(train: pd.DataFrame) -> pd.DataFrame:
    """How often each ball outcome happens, by phase (training data only)."""
    t = train
    cat = np.select(
        [t["is_wicket"], ~t["legal_ball"], t["total_runs"] >= 6, t["total_runs"] >= 4, t["total_runs"] == 3,
         t["total_runs"] == 2, t["total_runs"] == 1],
        ["wicket", "extra", "6", "4", "3", "2", "1"], default="dot")
    p = pd.crosstab(t["innings_phase"], cat, normalize="index")
    return p.reindex(columns=list(OUTCOMES), fill_value=0)


def chase_frame(s: pd.DataFrame) -> pd.DataFrame:
    """Second-innings balls with R, B, W, IPL flag, scoring environment and the result label y."""
    c = s[s["innings"] == 2].copy()
    c["R"], c["B"], c["W"] = c["runs_required"], c["balls_remaining"], c["wickets_in_hand"]
    c["is_ipl"] = c["competition_group"].eq("IPL")
    c["env"] = c["match_id"].map(scoring_environment(s))
    c["y"] = c["batting_team_won"]
    return c


def evaluate(pred, test, name) -> dict:
    """Log loss, Brier score and AUC of a prediction function on decided (0/1) test balls."""
    t = test[test["y"].isin([0, 1])]
    p = np.clip(pred(t), 1e-6, 1 - 1e-6)
    return {"model": name, "balls": len(t), "matches": t["match_id"].nunique(),
            "log_loss": log_loss(t["y"], p), "brier": brier_score_loss(t["y"], p), "auc": roc_auc_score(t["y"], p)}


def calibration(model, t):
    """Predicted vs actual chase win rate in ten probability bands."""
    t = t[t["y"].isin([0, 1])].copy()
    t["p"] = model.predict(t.R, t.B, t.W, t.is_ipl, t.env)
    return t.groupby(pd.cut(t["p"], np.linspace(0, 1, 11)), observed=True).agg(
        balls=("y", "size"), predicted=("p", "mean"), actual=("y", "mean")).round(3)


def score_balls(c: pd.DataFrame, model: ChaseWinModel, probs: pd.DataFrame, mean_lev: float) -> pd.DataFrame:
    """Per chase ball: win probability before/after, WPA (after - before), leverage (expected |WP swing|
    over ball outcomes), leverage index, MSP percentile and directional pressure.
    """
    a = (c.is_ipl, c.env)
    c["wp_before"] = model.predict(c.R, c.B, c.W, *a)
    c["wp_after"] = model.predict(c["target"] - c["score_after"], c["innings_limit_balls"] - c["legal_balls_after"],
                                  10 - c["wickets_after"], *a)
    c["wpa"] = c["wp_after"] - c["wp_before"]
    live = ((c.R > 0) & (c.B > 0) & (c.W > 0)).values
    pr = probs.reindex(c["innings_phase"]).fillna(probs.mean())
    lev = np.zeros(len(c))
    for k, (dr, db, dw) in OUTCOMES.items():
        lev += pr[k].values * np.abs(model.predict(c.R - dr, c.B - db, c.W - dw, *a) - c["wp_before"].values)
    c["leverage"] = np.where(live, lev, 0.0)
    c["leverage_index"] = c["leverage"] / mean_lev
    c["msp"] = c["leverage"].rank(pct=True) * 100
    c["batting_pressure_dir"] = 1 - c["wp_before"]
    c["bowling_pressure_dir"] = c["wp_before"]
    return c


def main():
    """Train on chases before TEST_START, evaluate on later chases, refit on all data, score every chase ball, report."""
    s = pd.read_parquet(C.PROCESSED / "match_state.parquet")
    c = chase_frame(s)
    fit_rows = c["state_reliable"] & c["y"].isin([0, 1]) & (c["R"] > 0) & (c["B"] > 0) & (c["W"] > 0)
    is_train = c["match_date"] < TEST_START
    train, test = c[fit_rows & is_train], c[fit_rows & ~is_train]

    logit = ChaseWinModel().fit(train)
    probs = outcome_probs(train)
    model = HybridWP(logit, EndgameDP(probs.loc["Death"].to_dict()))
    rrr_only = make_pipeline(StandardScaler(), LogisticRegression()).fit(train[["R"]].assign(rrr=features(train.R, train.B, train.W, 0, 8)["rrr"].values)[["rrr"]], train.y)
    no_env = ChaseWinModel()
    no_env.model.fit(features(train.R, train.B, train.W, train.is_ipl, train.env)[FEATURES].assign(rrr_rel=0), train.y)

    report = ["# Second-innings Match Situation Pressure\n",
              f"Train: chases before {TEST_START.date()} ({train['match_id'].nunique()} matches, {len(train):,} balls). "
              f"Test: {test['match_id'].nunique()} later chases ({len(test):,} balls). Ties, no-results and the 3 "
              f"unreliable matches are excluded from fitting.\n",
              f"Test-period chase win rate {test.drop_duplicates('match_id')['y'].mean():.1%} vs "
              f"train {train.drop_duplicates('match_id')['y'].mean():.1%}; scoring environment (runs/over) "
              f"train {train['env'].mean():.2f} vs test {test['env'].mean():.2f}.\n",
              "## Out-of-time accuracy on 2025-26 (lower log loss / Brier is better)"]
    base = train["y"].mean()
    feat = lambda t: features(t.R, t.B, t.W, t.is_ipl, t.env)
    rows = [evaluate(lambda t: np.full(len(t), base), test, "Constant (train win rate)"),
            evaluate(lambda t: rrr_only.predict_proba(feat(t)[["rrr"]])[:, 1], test, "Required run rate only"),
            evaluate(lambda t: no_env.model.predict_proba(feat(t)[FEATURES].assign(rrr_rel=0))[:, 1], test, "Chase model without scoring environment"),
            evaluate(lambda t: logit.predict(t.R, t.B, t.W, t.is_ipl, t.env), test, "Chase model (logistic only)"),
            evaluate(lambda t: model.predict(t.R, t.B, t.W, t.is_ipl, t.env), test, "Chase model + endgame recursion (final)")]
    late = test[test["B"] <= 12]
    rows += [evaluate(lambda t: logit.predict(t.R, t.B, t.W, t.is_ipl, t.env), late, "  last 12 balls: logistic only"),
             evaluate(lambda t: model.predict(t.R, t.B, t.W, t.is_ipl, t.env), late, "  last 12 balls: final")]
    for comp in ["IPL", "T20I"]:
        rows.append(evaluate(lambda t: model.predict(t.R, t.B, t.W, t.is_ipl, t.env),
                             test[test["competition_group"] == comp], f"Final - {comp} only"))
    report.append(pd.DataFrame(rows).round(4).to_markdown(index=False))
    report += ["\n## Calibration on 2025-26 test set (predicted vs actual chase win rate)", calibration(model, test).to_markdown(),
               "\nKnown limitation: chasing has become easier over time (chase win rate 48% to 2024, 53% in 2025, "
               "55% in 2026), so the out-of-time model is a few points pessimistic mid-range. Recency weighting and "
               "a recent-chase-rate feature were tested and did not help consistently across 2025 and 2026, so the "
               "simpler model is kept. The production model is refit on all seasons. Pressure (msp) is a rank, "
               "so it is robust to this."]
    report += ["\n## Model coefficients (standardised; + raises chase win probability)",
               logit.coefficients().round(3).to_frame("coef").to_markdown()]

    # ---- production model: refit on all reliable chases, then score every chase ball
    report += ["\n## Ball outcome frequencies by phase (training data; weights for leverage)", probs.round(3).to_markdown()]
    probs = outcome_probs(c[fit_rows])
    final = HybridWP(ChaseWinModel().fit(c[fit_rows]), EndgameDP(probs.loc["Death"].to_dict()))
    tmp = score_balls(c.copy(), final, probs, 1.0)
    mean_lev = tmp.loc[tmp["leverage"] > 0, "leverage"].mean()
    c = score_balls(c, final, probs, mean_lev)

    keep = ["match_id", "innings", "innings_ball_num", "wp_before", "wp_after", "wpa", "leverage",
            "leverage_index", "msp", "batting_pressure_dir", "bowling_pressure_dir"]
    c[keep].to_parquet(OUT_FILE, index=False)

    # ---- sanity checks on the pressure measure
    end = c.groupby("match_id").tail(1)
    margin = np.where(end["batting_team_won"] == 1, end["innings_limit_balls"] - end["legal_balls_after"],
                      end["target"] - 1 - end["score_after"])
    close = pd.Series(np.select([margin <= 6, margin <= 20], ["close (<=6 runs/balls)", "medium"], "one-sided"),
                      index=end["match_id"])
    c["closeness"] = c["match_id"].map(close)
    report += ["\n## Sanity checks",
               "Mean MSP by over and final margin (pressure should build late in close chases):",
               c.pivot_table(index="closeness", columns="overid", values="msp", aggfunc="mean").round(0).to_markdown(),
               "\nMean MSP by final margin:", c.groupby("closeness")["msp"].mean().round(1).to_markdown()]
    top = c.nlargest(8, "leverage")[["match_id", "competition_group", "overid", "striker_name", "bowler_name",
                                     "runs_required", "balls_remaining", "wickets_in_hand", "wp_before", "leverage_index", "total_runs", "is_wicket"]]
    report += ["\nHighest-leverage balls:", top.round(3).to_markdown(index=False)]
    tew = c[(c["striker_name"] == "Rahul Tewatia") & (c["bowler_name"] == "Odean Smith")]
    report += ["\nTewatia vs Odean Smith, last two balls of GT v PBKS 2022 (12 needed off 2):",
               tew[["runs_required", "balls_remaining", "wp_before", "wp_after", "wpa", "leverage_index", "msp"]].tail(2).round(3).to_markdown(index=False)]

    txt = "\n".join(report)
    print(txt)
    (C.OUTPUTS / "msp_inn2_report.md").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
