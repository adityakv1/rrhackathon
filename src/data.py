"""Load raw CSVs and build the cleaned, reusable delivery table.

Every derived column is documented here so later stages (match state, pressure,
consistency) share one definition of a legal ball, total runs and a wicket.
"""
import numpy as np
import pandas as pd

from . import config as C


def load_raw() -> dict[str, pd.DataFrame]:
    """Read the six raw CSV files from data/raw into a dict of DataFrames keyed by file name."""
    names = ["competitions", "teams", "matches", "ball_by_ball",
             "playing_eleven", "competition_team_player_mapping"]
    return {n: pd.read_csv(C.RAW / f"{n}.csv") for n in names}


def classify_competitions(comps: pd.DataFrame) -> pd.DataFrame:
    """Label each competition 'IPL', 'T20I' or 'Other T20' (column competition_group)."""
    comps = comps.copy()
    is_ipl = comps["comp_name"].str.contains(r"\bIPL\b|Indian Premier League", case=False, regex=True, na=False)
    comps["competition_group"] = np.select(
        [is_ipl, comps["match_format"].eq("T20I")], ["IPL", "T20I"], default="Other T20")
    return comps


def build_matches(raw: dict) -> pd.DataFrame:
    """Match table joined to competition name, season and group; match_date parsed as a date."""
    comps = classify_competitions(raw["competitions"])
    m = raw["matches"].merge(
        comps[["comp_id", "comp_name", "season", "competition_group"]], on="comp_id", how="left")
    m["match_date"] = pd.to_datetime(m["match_date"])
    return m


def build_deliveries(raw: dict, other_as_no_ball: bool = C.OTHER_AS_NO_BALL) -> pd.DataFrame:
    """Regular-innings deliveries with validated derived columns.

    total_runs  : runs + extras1_runs + extras_2_runs (reconciles to match margins, see validate.py)
    batter_runs : bat runs only (byes/leg-byes hold their runs in extras1, so `runs` is bat-only)
    bowler_runs : total_runs minus byes, leg-byes, penalty
    legal_ball  : not a wide, not a no-ball (Overstep; 'other' per scenario flag)
    ball_faced  : not a wide (a no-ball is still faced by the batter)
    """
    b = raw["ball_by_ball"]
    b = b[b["innings"].isin(C.REGULAR_INNINGS)].copy()
    for c in ["extras1_runs", "extras_2_runs", "runs"]:
        b[c] = b[c].fillna(0).astype(int)
    b["is_wicket"] = b["is_wicket"].astype(bool)
    b = b.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)

    et = b["extras_type"]
    b["total_runs"] = b["runs"] + b["extras1_runs"] + b["extras_2_runs"]
    b["batter_runs"] = b["runs"]
    b["is_wide"] = et.eq(C.WIDE)
    b["is_no_ball"] = et.eq(C.NO_BALL) | (et.eq(C.OTHER) if other_as_no_ball else False)
    b["legal_ball"] = ~(b["is_wide"] | b["is_no_ball"])
    b["ball_faced"] = ~b["is_wide"]
    # Byes/leg-byes/penalty runs are not charged to the bowler; bat runs on those balls still are.
    b["bowler_runs"] = np.where(et.isin(["byes", "legbyes", "Penalty"]), b["batter_runs"], b["total_runs"])
    b["bowler_wicket"] = b["is_wicket"] & b["dismissal_type"].isin(C.BOWLER_WICKETS)
    b["batter_out"] = b["is_wicket"] & ~b["dismissal_type"].isin(C.NOT_BATTER_DISMISSALS)

    m = build_matches(raw)[["match_id", "comp_id", "comp_name", "season", "competition_group", "match_date"]]
    return b.merge(m, on="match_id", how="left")


def build_all(save: bool = True):
    """Load raw data, build the clean match and delivery tables and (if save) write them to data/processed."""
    raw = load_raw()
    matches, deliveries = build_matches(raw), build_deliveries(raw)
    if save:
        C.PROCESSED.mkdir(parents=True, exist_ok=True)
        deliveries.to_parquet(C.PROCESSED / "deliveries.parquet", index=False)
        matches.to_parquet(C.PROCESSED / "matches.parquet", index=False)
    return raw, matches, deliveries
