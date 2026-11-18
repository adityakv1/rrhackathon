"""Individual Performance Pressure (IPP).  Run:  python -m src.pressure_ipp

A FORM-BASED PROXY: how far a player's recent output has fallen below his own baseline going into
a match. It is not, and must not be presented as, a measure of psychological state.

Everything is computed from matches BEFORE the one being scored (shift by one innings), across
all T20 competitions in the data (form carries across competitions), separately for batting and
bowling.

Batting components (higher = more form pressure)
  runs_drop     : (baseline runs/innings - mean runs over last RECENT innings) / baseline
  sr_drop       : (baseline strike rate - ball-weighted strike rate over last RECENT innings) / baseline
  low_streak    : consecutive most-recent innings below LOW_FRACTION x baseline runs
Bowling components
  econ_rise     : (economy over last RECENT matches - baseline economy) / baseline       (pooled runs/balls)
  wkt_drop      : (baseline wickets/ball - wickets/ball over last RECENT matches) / baseline
  dry_streak    : consecutive most-recent matches without a wicket

Baselines are career-to-date, shrunk towards the population mean with SHRINK innings of weight,
so a newcomer's single bad game is not a "slump". Components are converted to percentiles,
averaged with equal weight, and the average is converted to a 0-100 percentile (ipp).
Players with fewer than MIN_HISTORY previous innings get ipp = NaN (flag: insufficient_history).
"""
import numpy as np
import pandas as pd

from . import config as C

RECENT = 5
SHRINK = 10
MIN_HISTORY = 3
LOW_FRACTION = 0.5
MAX_BAT_POSITION = 7        # batting IPP only for players who usually bat in the top 7
MIN_BALLS_PER_MATCH = 12    # bowling IPP only for players who usually bowl 2+ overs
MIN_RECENT_BALLS = 24       # ... and have bowled 4+ overs across the recent window
OUT_FILE = C.PROCESSED / "pressure_ipp.parquet"


# ---------------------------------------------------------------- per-match player lines
def batting_innings(s: pd.DataFrame) -> pd.DataFrame:
    """One row per batter per match innings, incl. batters dismissed without facing (e.g. run out as non-striker)."""
    keys = ["match_id", "match_date", "innings", "competition_group"]
    faced = s.groupby(keys + ["striker_id", "striker_name"]).agg(
        runs=("batter_runs", "sum"), balls=("ball_faced", "sum"), batting_order=("batting_order", "min")).reset_index()
    faced = faced.rename(columns={"striker_id": "player_id", "striker_name": "player_name"})
    outs = s[s["batter_out"] & s["dismissed_player_id"].notna()].groupby(keys + ["dismissed_player_id"]).size()
    outs = outs.rename("out").reset_index().rename(columns={"dismissed_player_id": "player_id"})
    outs["player_id"] = outs["player_id"].astype(faced["player_id"].dtype)
    b = faced.merge(outs, on=keys + ["player_id"], how="outer")
    names = s.drop_duplicates("striker_id").set_index("striker_id")["striker_name"]
    b["player_name"] = b["player_name"].fillna(b["player_id"].map(names))
    b[["runs", "balls", "out"]] = b[["runs", "balls", "out"]].fillna(0)
    return b


def bowling_matches(s: pd.DataFrame) -> pd.DataFrame:
    """One row per bowler per match innings: runs conceded, legal balls, wickets."""
    return s.groupby(["match_id", "match_date", "innings", "competition_group", "bowler_id", "bowler_name"]).agg(
        runs=("bowler_runs", "sum"), balls=("legal_ball", "sum"), wkts=("bowler_wicket", "sum")).reset_index().rename(
        columns={"bowler_id": "player_id", "bowler_name": "player_name"})


# ---------------------------------------------------------------- helpers
def prior_rolling_sum(g: pd.core.groupby.SeriesGroupBy, window=None) -> pd.Series:
    """Sum over previous innings (excluding the current one); window=None -> career to date."""
    if window is None:
        return g.transform(lambda x: x.cumsum().shift(1))
    return g.transform(lambda x: x.rolling(window, min_periods=1).sum().shift(1))


def streak_before(flag: pd.Series, player: pd.Series) -> pd.Series:
    """Number of consecutive True values immediately BEFORE each row, within player."""
    def run(x):
        """Running count of consecutive True values before each position."""
        out, c = [], 0
        for v in x:
            out.append(c)
            c = c + 1 if v else 0
        return pd.Series(out, index=x.index)
    return flag.groupby(player).transform(run)


def to_pct(x: pd.Series) -> pd.Series:
    """Convert to a 0-100 percentile rank."""
    return x.rank(pct=True) * 100


# ---------------------------------------------------------------- IPP
def batting_ipp(b: pd.DataFrame) -> pd.DataFrame:
    """Batting form pressure: runs drop, strike-rate drop and low-score streak vs the player's own baseline."""
    b = b.sort_values(["player_id", "match_date", "match_id"]).reset_index(drop=True)
    g = b.groupby("player_id")
    pop_rpi = b["runs"].mean()
    pop_sr = b["runs"].sum() / b["balls"].sum() * 100
    n_prior = g.cumcount()
    base_rpi = (prior_rolling_sum(g["runs"]).fillna(0) + SHRINK * pop_rpi) / (n_prior + SHRINK)
    base_sr = (prior_rolling_sum(g["runs"]).fillna(0) + SHRINK * pop_rpi) / \
              (prior_rolling_sum(g["balls"]).fillna(0) + SHRINK * pop_rpi / pop_sr * 100) * 100
    n_recent = np.minimum(n_prior, RECENT).replace(0, np.nan)
    rec_runs = prior_rolling_sum(g["runs"], RECENT)
    rec_balls = prior_rolling_sum(g["balls"], RECENT)
    b["baseline_runs"], b["baseline_sr"] = base_rpi, base_sr
    b["recent_runs"] = rec_runs / n_recent
    b["recent_sr"] = rec_runs / rec_balls.replace(0, np.nan) * 100
    b["runs_drop"] = (base_rpi - b["recent_runs"]) / base_rpi
    b["sr_drop"] = ((base_sr - b["recent_sr"]) / base_sr).fillna(0)
    b["low_streak"] = streak_before(b["runs"] < LOW_FRACTION * base_rpi, b["player_id"])
    b["history_n"] = n_prior
    # role: usual batting position from PREVIOUS innings only; tail-enders are not under batting-form pressure
    b["usual_position"] = g["batting_order"].transform(lambda x: x.expanding().median().shift(1))
    role_ok = b["usual_position"] <= MAX_BAT_POSITION
    return finish(b, ["runs_drop", "sr_drop", "low_streak"], "bat", role_ok)


def bowling_ipp(w: pd.DataFrame) -> pd.DataFrame:
    """Bowling form pressure: economy rise, wicket-rate drop and wicketless streak vs the player's own baseline."""
    w = w[w["balls"] > 0].sort_values(["player_id", "match_date", "match_id"]).reset_index(drop=True)
    g = w.groupby("player_id")
    pop_rpb = w["runs"].sum() / w["balls"].sum()
    pop_wpb = w["wkts"].sum() / w["balls"].sum()
    k_balls = SHRINK * w["balls"].mean()
    cum_r, cum_b, cum_w = (prior_rolling_sum(g[c]).fillna(0) for c in ["runs", "balls", "wkts"])
    base_econ = (cum_r + k_balls * pop_rpb) / (cum_b + k_balls) * 6
    base_wpb = (cum_w + k_balls * pop_wpb) / (cum_b + k_balls)
    rr, rb, rw = (prior_rolling_sum(g[c], RECENT) for c in ["runs", "balls", "wkts"])
    w["baseline_econ"], w["baseline_wkts_per24"] = base_econ, base_wpb * 24
    w["recent_econ"] = rr / rb.replace(0, np.nan) * 6
    w["recent_wkts_per24"] = rw / rb.replace(0, np.nan) * 24
    w["econ_rise"] = (w["recent_econ"] - base_econ) / base_econ
    w["wkt_drop"] = (base_wpb - rw / rb.replace(0, np.nan)) / base_wpb
    w["dry_streak"] = streak_before(w["wkts"] == 0, w["player_id"])
    w["history_n"] = g.cumcount()
    # role: genuine bowlers only (usually bowl >= MIN_BALLS_PER_MATCH), and enough recent balls to judge form
    w["usual_balls"] = cum_b / w["history_n"].replace(0, np.nan)
    role_ok = (w["usual_balls"] >= MIN_BALLS_PER_MATCH) & (rb >= MIN_RECENT_BALLS)
    return finish(w, ["econ_rise", "wkt_drop", "dry_streak"], "bowl", role_ok)


def finish(df: pd.DataFrame, comps: list, role: str, role_ok: pd.Series) -> pd.DataFrame:
    """Turn components into percentiles, average them into a 0-100 IPP and flag history/role exclusions."""
    hist_ok = df["history_n"] >= MIN_HISTORY
    ok = hist_ok & role_ok.fillna(False)
    for c in comps:
        df[f"{c}_pct"] = np.where(ok, to_pct(df[c].where(ok)), np.nan)
    df["ipp_raw"] = df[[f"{c}_pct" for c in comps]].mean(axis=1)
    df["ipp"] = to_pct(df["ipp_raw"])
    df["ipp_flag"] = np.select([~hist_ok, ~ok], ["insufficient_history", "not_role_player"], "ok")
    df["role"] = role
    return df


# ---------------------------------------------------------------- report
def report(bat: pd.DataFrame, bowl: pd.DataFrame) -> str:
    """Build the IPP markdown report: coverage, component correlations, outcomes by band and examples."""
    r = ["# Individual Performance Pressure (form-based proxy)\n",
         "IPP measures how far a player's recent output sits below his own baseline going into a match, "
         "using previous matches only. It is a statistical form signal, NOT a measure of psychological state.\n",
         f"- Batting innings: {bat['ipp_flag'].value_counts().to_dict()} "
         f"(role = usually bats in the top {MAX_BAT_POSITION}, judged from previous innings)",
         f"- Bowling matches: {bowl['ipp_flag'].value_counts().to_dict()} "
         f"(role = usually bowls {MIN_BALLS_PER_MATCH}+ balls and {MIN_RECENT_BALLS}+ balls in the recent window)",
         "\n## Component correlations (should be positive but not ~1: each adds something)",
         "Batting:", bat[["runs_drop", "sr_drop", "low_streak"]].corr(method="spearman").round(2).to_markdown(),
         "\nBowling:", bowl[["econ_rise", "wkt_drop", "dry_streak"]].corr(method="spearman").round(2).to_markdown()]

    # what happens next? (descriptive: form pressure vs the very next performance relative to baseline)
    bt = bat[bat["ipp"].notna()].copy()
    bt["band"] = pd.cut(bt["ipp"], [0, 20, 40, 60, 80, 100], labels=["0-20 (in form)", "20-40", "40-60", "60-80", "80-100 (out of form)"])
    bt["runs_vs_base"] = bt["runs"] - bt["baseline_runs"]
    r += ["\n## What happened in the match itself, by IPP band (descriptive)",
          "Batting: runs in this innings minus the player's baseline. Near-zero differences mean form "
          "pressure carries little predictive signal: it is used as a pressure CONTEXT, not a forecast.",
          bt.groupby("band", observed=True).agg(innings=("runs", "size"), mean_runs=("runs", "mean"),
                                                 baseline=("baseline_runs", "mean"), runs_vs_base=("runs_vs_base", "mean")).round(2).to_markdown()]
    bw = bowl[bowl["ipp"].notna()].copy()
    bw["band"] = pd.cut(bw["ipp"], [0, 20, 40, 60, 80, 100], labels=["0-20 (in form)", "20-40", "40-60", "60-80", "80-100 (out of form)"])
    agg = bw.groupby("band", observed=True).agg(matches=("runs", "size"), runs=("runs", "sum"), balls=("balls", "sum"),
                                                 wkts=("wkts", "sum"), base_econ=("baseline_econ", "mean"))
    agg["econ"] = agg["runs"] / agg["balls"] * 6
    agg["wkts_per24"] = agg["wkts"] / agg["balls"] * 24
    r += ["\nBowling: economy / wickets in this match by IPP band:",
          agg[["matches", "econ", "base_econ", "wkts_per24"]].round(2).to_markdown()]

    ipl = bat[(bat["competition_group"] == "IPL") & bat["ipp"].notna()]
    r += ["\n## Highest batting form pressure going into an IPL match (examples)",
          ipl.nlargest(8, "ipp_raw")[["player_name", "match_date", "baseline_runs", "recent_runs", "recent_sr",
                                      "low_streak", "ipp", "runs", "balls"]].round(1).to_markdown(index=False)]
    iplb = bowl[(bowl["competition_group"] == "IPL") & bowl["ipp"].notna()]
    r += ["\n## Highest bowling form pressure going into an IPL match (examples)",
          iplb.nlargest(8, "ipp_raw")[["player_name", "match_date", "baseline_econ", "recent_econ", "recent_wkts_per24",
                                       "dry_streak", "ipp", "runs", "balls", "wkts"]].round(2).to_markdown(index=False)]
    return "\n".join(r)


def main():
    """Compute batting and bowling IPP, save pressure_ipp.parquet and write outputs/ipp_report.md."""
    s = pd.read_parquet(C.PROCESSED / "match_state.parquet")
    bat = batting_ipp(batting_innings(s))
    bowl = bowling_ipp(bowling_matches(s))
    keep = ["match_id", "innings", "player_id", "player_name", "role", "match_date", "competition_group",
            "history_n", "ipp", "ipp_flag"]
    out = pd.concat([
        bat[keep + ["runs_drop", "sr_drop", "low_streak", "baseline_runs", "baseline_sr", "recent_runs", "recent_sr"]],
        bowl[keep + ["econ_rise", "wkt_drop", "dry_streak", "baseline_econ", "baseline_wkts_per24", "recent_econ", "recent_wkts_per24"]],
    ], ignore_index=True)
    out.to_parquet(OUT_FILE, index=False)
    txt = report(bat, bowl)
    print(txt)
    (C.OUTPUTS / "ipp_report.md").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
