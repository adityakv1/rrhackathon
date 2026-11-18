"""Delivery-by-delivery match-state reconstruction.  Run:  python -m src.match_state

For every regular-innings ball we record the situation BEFORE the ball (what the
batter and bowler faced) and the state AFTER it. Only information known at that
moment in the match is used, except the innings length limit (see note on
revised overs below) and the final result (kept only as a label for validation
and later model fitting, never as an input).

Validated inputs (src/validate.py):
  * total_runs = runs + extras1_runs + extras_2_runs
  * legal ball = not wide, not Overstep, not 'other'
  * first_inn_revised_overs / second_inn_revised_overs are in BALLS
  * revised_target is the runs-to-win target (DLS where applicable)
"""
import numpy as np
import pandas as pd

from . import config as C

STATE_FILE = C.PROCESSED / "match_state.parquet"


def match_outcomes(matches: pd.DataFrame) -> pd.DataFrame:
    """Classify each match result for regular play: 'win', 'tie' (incl. Super Over decided), 'no_result'."""
    res = matches["result"].fillna("").str.lower()
    super_over = res.str.contains("super over")
    tie = res.str.contains(r"\btie") | super_over
    nr = res.str.contains("no result|abandon") | (matches["win_team_id"].isna() & ~tie)
    out = matches[["match_id", "win_team_id"]].copy()
    out["outcome_type"] = np.select([tie, nr], ["tie", "no_result"], default="win")
    out["decided_by_super_over"] = super_over
    out["dls"] = res.str.contains(r"d/?ls|d/l")
    return out


def innings_limits(matches: pd.DataFrame, deliveries: pd.DataFrame) -> pd.DataFrame:
    """Legal-ball limit for each innings, plus a flag when it had to be inferred.

    Innings 1: first_inn_revised_overs if set. Otherwise, in a DECIDED match, a first innings
      that ended short of 120 legal balls without being bowled out was cut (rain) at that
      point, so its limit = balls bowled. Some shortened matches have no revised value
      recorded (e.g. 31278, 48514), so this inference is needed. Else 120.
    Innings 2: second_inn_revised_overs if set, else the innings-1 limit (same length both sides).
    Note: for cuts DURING an innings the final limit is applied to every ball of it. This is a
    small, documented look-ahead affecting only rain-affected matches (flagged limit_inferred / dls).
    """
    m = matches.set_index("match_id")
    inn1 = deliveries[deliveries["innings"] == 1].groupby("match_id").agg(
        legal=("legal_ball", "sum"), wk=("is_wicket", "sum"))
    m = m.join(inn1, how="left")
    decided = m["result"].str.contains(r"won", case=False, na=False)
    cut = m["first_inn_revised_overs"].isna() & decided & (m["legal"] < C.T20_MAX_BALLS) & (m["wk"] < 10)
    l1 = m["first_inn_revised_overs"].fillna(m["legal"].where(cut)).fillna(C.T20_MAX_BALLS)
    l2 = m["second_inn_revised_overs"].fillna(l1)
    lim = pd.DataFrame({1: l1, 2: l2}).stack().rename("innings_limit_balls").rename_axis(["match_id", "innings"])
    inferred = pd.DataFrame({1: cut, 2: cut & m["second_inn_revised_overs"].isna()}).stack().rename("limit_inferred")
    inferred.index.names = ["match_id", "innings"]
    return pd.concat([lim, inferred], axis=1).reset_index()


def build_match_state(deliveries: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """Build the per-ball match-state table.

    For every regular-innings ball: running score/wickets/legal balls AFTER the ball and the
    situation BEFORE it (balls remaining, wickets in hand, target, runs required, current and
    required run rate, phase), plus the match result as a label and a state_reliable flag.
    """
    d = deliveries.sort_values(["match_id", "innings", "innings_ball_num"]).copy()
    g = d.groupby(["match_id", "innings"], sort=False)

    # --- cumulative state AFTER each ball, then shift to get state BEFORE it
    d["score_after"] = g["total_runs"].cumsum()
    d["wickets_after"] = g["is_wicket"].cumsum().astype(int)
    d["legal_balls_after"] = g["legal_ball"].cumsum().astype(int)
    d["score_before"] = d["score_after"] - d["total_runs"]
    d["wickets_before"] = d["wickets_after"] - d["is_wicket"].astype(int)
    d["legal_balls_before"] = d["legal_balls_after"] - d["legal_ball"].astype(int)

    # --- innings length and target
    d = d.merge(innings_limits(matches, d), on=["match_id", "innings"], how="left")
    first_total = d[d["innings"] == 1].groupby("match_id")["total_runs"].sum().rename("first_innings_total")
    d = d.merge(first_total, on="match_id", how="left")
    d = d.merge(matches[["match_id", "revised_target", "stage", "knock_out", "venue_id"]], on="match_id", how="left")
    d["target"] = np.where(d["innings"] == 2, d["revised_target"].fillna(d["first_innings_total"] + 1), np.nan)

    # --- situation before the ball
    d["balls_remaining"] = (d["innings_limit_balls"] - d["legal_balls_before"]).clip(lower=0)
    d["wickets_in_hand"] = 10 - d["wickets_before"]
    d["current_run_rate"] = np.where(d["legal_balls_before"] > 0,
                                     d["score_before"] * 6 / d["legal_balls_before"].replace(0, np.nan), np.nan)
    d["runs_required"] = d["target"] - d["score_before"]
    d["required_run_rate"] = np.where(d["balls_remaining"] > 0,
                                      d["runs_required"] * 6 / d["balls_remaining"].replace(0, np.nan), np.nan)
    d["rrr_minus_crr"] = d["required_run_rate"] - d["current_run_rate"]
    d["innings_progress"] = d["legal_balls_before"] / d["innings_limit_balls"]
    d["innings_phase"] = pd.cut(d["overid"], [0, 6, 16, 99], labels=list(C.PHASES)).astype(str)

    # --- result label (validation / model target only; never a pressure input)
    o = match_outcomes(matches)
    d = d.merge(o, on="match_id", how="left")
    d["batting_team_won"] = np.select(
        [d["outcome_type"].eq("tie"), d["outcome_type"].eq("no_result")],
        [0.5, np.nan], default=(d["win_team_id"] == d["batting_team_id"]).astype(float))

    # --- reliability flag: chases whose final state cannot reproduce the recorded result
    # (e.g. 'Match Tied' at 75/4 chasing 161; DLS wins in rain-stopped chases with no limit recorded).
    # Kept in the table for descriptive stats, excluded when fitting/validating pressure models.
    end = d[d["innings"] == 2].groupby("match_id").tail(1)
    reached = end["score_after"] >= end["target"]
    ok = np.select([end["outcome_type"].eq("no_result"), end["outcome_type"].eq("tie")],
                   [True, end["score_after"].eq(end["target"] - 1)],
                   default=reached.eq(end["batting_team_won"].eq(1)))
    bad_ids = set(end.loc[~ok.astype(bool), "match_id"])
    d["state_reliable"] = ~d["match_id"].isin(bad_ids)

    cols = ["match_id", "match_date", "season", "comp_id", "competition_group", "stage", "knock_out", "venue_id",
            "innings", "innings_ball_num", "overid", "over_ball_num", "innings_phase",
            "batting_team_id", "bowling_team_id", "striker_id", "striker_name", "non_striker_id",
            "bowler_id", "bowler_name", "pace_or_spin", "batting_order",
            "total_runs", "batter_runs", "bowler_runs", "legal_ball", "ball_faced", "is_wide", "is_no_ball",
            "is_four", "is_six", "is_wicket", "dismissal_type", "dismissed_player_id", "bowler_wicket", "batter_out",
            "score_before", "wickets_before", "legal_balls_before", "balls_remaining", "wickets_in_hand",
            "innings_limit_balls", "limit_inferred", "state_reliable", "innings_progress", "current_run_rate",
            "target", "runs_required", "required_run_rate", "rrr_minus_crr",
            "score_after", "wickets_after", "legal_balls_after",
            "first_innings_total", "outcome_type", "decided_by_super_over", "dls", "win_team_id", "batting_team_won"]
    return d[cols]


def validate_state(s: pd.DataFrame) -> list[str]:
    """Check every innings' final state agrees with the recorded match result."""
    out = ["# Match-state validation\n"]
    last = s.groupby(["match_id", "innings"]).tail(1)
    out.append(f"- Deliveries: {len(s):,}; innings: {len(last):,}; matches: {s['match_id'].nunique()}")
    out.append(f"- Negative balls remaining before a ball: {(s['innings_limit_balls'] - s['legal_balls_before'] < 0).sum()}; "
               f"wickets > 10: {(s['wickets_after'] > 10).sum()}")

    ch = last[(last["innings"] == 2)]
    ch = ch[ch["outcome_type"] != "no_result"]
    reached = ch["score_after"] >= ch["target"]
    won = ch["batting_team_won"] == 1
    tie = ch["outcome_type"] == "tie"
    agree = (won & reached) | (~won & ~tie & ~reached) | (tie & (ch["score_after"] == ch["target"] - 1))
    out.append(f"- Completed chases: {len(ch)}. Final state agrees with recorded result "
               f"(chaser won <=> reached target; tie <=> finished one short): **{agree.mean():.1%}**")
    bad = ch[~agree]
    if len(bad):
        out.append("  - Disagreements: " + "; ".join(
            f"{r.match_id} (score {r.score_after}/{r.wickets_after}, target {r.target:.0f}, "
            f"outcome {r.outcome_type}, dls {r.dls})" for r in bad.itertuples()))

    # How each chase ended: target reached, all out, balls used up
    lost = ch[~won & ~tie]
    ended = np.select([lost["wickets_after"] >= 10, lost["legal_balls_after"] >= lost["innings_limit_balls"]],
                      ["all out", "balls used up"], default="other")
    out.append(f"- Lost chases ending: {pd.Series(ended).value_counts().to_dict()}")
    stopped = last[last["outcome_type"] == "win"]
    early_wins = ch[won & (ch["legal_balls_after"] < ch["innings_limit_balls"]) & (ch["wickets_after"] < 10)]
    out.append(f"- Won chases finishing with balls to spare: {len(early_wins)} of {won.sum()}")
    first = last[(last["innings"] == 1) & (last["outcome_type"] == "win")]
    f_end = np.select([first["wickets_after"] >= 10, first["legal_balls_after"] >= first["innings_limit_balls"]],
                      ["all out", "full quota"], default="short")
    out.append(f"- First innings (decided matches) ending: {pd.Series(f_end).value_counts().to_dict()}")
    out.append(f"- Outcome types (matches): {s.drop_duplicates('match_id')['outcome_type'].value_counts().to_dict()}")
    mm = s.drop_duplicates(["match_id", "innings"])
    out.append(f"- Innings with an inferred (unrecorded) shortened limit: {int(mm['limit_inferred'].sum())}; "
               f"matches flagged state_reliable=False: {sorted(int(x) for x in s.loc[~s['state_reliable'], 'match_id'].unique())}")
    return out


def main():
    """Build and save match_state.parquet, then write outputs/match_state_validation.md."""
    d = pd.read_parquet(C.PROCESSED / "deliveries.parquet")
    m = pd.read_parquet(C.PROCESSED / "matches.parquet")
    s = build_match_state(d, m)
    s.to_parquet(STATE_FILE, index=False)
    lines = validate_state(s)
    print("\n".join(lines))
    (C.OUTPUTS / "match_state_validation.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
