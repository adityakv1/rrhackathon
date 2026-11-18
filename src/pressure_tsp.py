"""Tournament Stakes Pressure (TSP).  Run:  python -m src.pressure_tsp

One principle for every match type (no hand-picked weights):

    TSP(team, match) = P(team wins the competition | wins this match)
                     - P(team wins the competition | loses this match)

"Wins the competition" = lifts the title (IPL, tri-series, multi-team events) or wins the
series (bilateral T20Is; a drawn series counts as half).

League / series matches: the table is rebuilt from results of EARLIER matches only, the remaining
FIXTURES (known in advance) are simulated as 50/50 games N_SIMS times, once with this team winning
this match and once with it losing (common random numbers keep the comparison low-noise).
Knockouts: exact values under 50/50 games, e.g. IPL Final 1.0, Qualifier 2 0.5,
Qualifier 1 0.25 (loser gets a second chance), Eliminator 0.25.

Competitions whose group/qualification rules cannot be recovered from the data (Asia Cup-style
events) get TSP only for their knockouts; other stages are left missing and flagged, rather than
inventing rules. TSP is a property of the TEAM in a match, so the two sides can differ
(a must-win game for one, a dead rubber for the other).
"""
import numpy as np
import pandas as pd

from . import config as C

N_SIMS = 4000
OUT_FILE = C.PROCESSED / "pressure_tsp.parquet"

# P(title | final league position), assuming 50/50 playoff games
IPL_TITLE_BY_RANK = {1: 0.375, 2: 0.375, 3: 0.125, 4: 0.125}   # top 2: two shots at the final; 3-4: must win 3
TOP2_FINAL_BY_RANK = {1: 0.5, 2: 0.5}                             # league then final between top two
LEAGUE_ONLY_BY_RANK = {1: 1.0}                                    # table-topper wins


# ---------------------------------------------------------------- standings helpers
def match_results(matches: pd.DataFrame) -> pd.DataFrame:
    """Points-table result of each match from the batting/fielding teams' view.
    A Super Over winner takes the win (as in the IPL table); no result / abandoned = shared."""
    m = matches.copy()
    res = m["result"].fillna("").str.lower()
    m["shared"] = m["win_team_id"].isna() | res.str.contains("no result|abandon")
    return m


def net_run_rate_before(state: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """Team NRR within a competition using only matches before each match (all-out = full quota)."""
    last = state.groupby(["match_id", "innings"]).tail(1)
    inn = last[["match_id", "innings", "batting_team_id", "bowling_team_id", "score_after", "wickets_after",
                "legal_balls_after", "innings_limit_balls"]].copy()
    inn["overs"] = np.where(inn["wickets_after"] >= 10, inn["innings_limit_balls"], inn["legal_balls_after"]) / 6
    rows = pd.concat([
        inn.rename(columns={"batting_team_id": "team_id"}).assign(rf=inn["score_after"], of=inn["overs"], ra=0.0, ob=0.0),
        inn.rename(columns={"bowling_team_id": "team_id"}).assign(rf=0.0, of=0.0, ra=inn["score_after"], ob=inn["overs"])])
    rows = rows.merge(matches[["match_id", "comp_id", "match_date", "match_number"]], on="match_id")
    t = rows.groupby(["comp_id", "team_id", "match_id", "match_date", "match_number"])[["rf", "of", "ra", "ob"]].sum()
    t = t.reset_index().sort_values(["comp_id", "team_id", "match_date", "match_number"])
    cum = t.groupby(["comp_id", "team_id"])[["rf", "of", "ra", "ob"]].cumsum() - t[["rf", "of", "ra", "ob"]].values
    t["nrr_before"] = (cum["rf"] / cum["of"].replace(0, np.nan) - cum["ra"] / cum["ob"].replace(0, np.nan)).fillna(0)
    return t[["match_id", "team_id", "nrr_before"]]


# ---------------------------------------------------------------- simulation engine
def title_probability(points: np.ndarray, tiebreak: np.ndarray, rank_value: dict, split_ties: bool) -> np.ndarray:
    """points: sims x teams. Returns sims x teams P(title) (0/1 or shared), from final positions."""
    if split_ties:  # bilateral: equal top points share the series
        top = points == points.max(axis=1, keepdims=True)
        return top / top.sum(axis=1, keepdims=True) * rank_value.get(1, 1.0)
    key = points + 1e-3 * tiebreak
    rank = (-key).argsort(axis=1).argsort(axis=1) + 1
    out = np.zeros_like(points, dtype=float)
    for r, v in rank_value.items():
        out[rank == r] = v
    return out


def league_stakes(comp: pd.DataFrame, nrr: pd.DataFrame, rank_value: dict, split_ties: bool, seed: int) -> pd.DataFrame:
    """TSP for each team in each league match of one competition."""
    comp = comp.sort_values(["match_date", "match_number"]).reset_index(drop=True)
    teams = pd.unique(comp[["home_team_id", "away_team_id"]].values.ravel())
    ix = {t: i for i, t in enumerate(teams)}
    a = comp["home_team_id"].map(ix).values
    b = comp["away_team_id"].map(ix).values
    rng = np.random.default_rng(seed)
    out = []
    for i in range(len(comp)):
        base = np.zeros(len(teams))
        for j in range(i):  # results already known before match i
            if comp.at[j, "shared"]:
                base[a[j]] += 1; base[b[j]] += 1
            else:
                base[ix[comp.at[j, "win_team_id"]]] += 2
        rem_a, rem_b = a[i + 1:], b[i + 1:]
        coin = rng.random((N_SIMS, len(rem_a))) < 0.5
        pts = np.tile(base, (N_SIMS, 1))
        np.add.at(pts, (np.arange(N_SIMS)[:, None], np.where(coin, rem_a, rem_b)), 2)
        nrr_i = nrr[nrr["match_id"] == comp.at[i, "match_id"]].set_index("team_id")["nrr_before"]
        tb = np.array([nrr_i.get(t, 0.0) for t in teams]) + rng.normal(0, 0.5, (N_SIMS, len(teams)))
        res = {}
        for winner, loser in [(a[i], b[i]), (b[i], a[i])]:
            p = pts.copy()
            p[:, winner] += 2
            res[winner] = title_probability(p, tb, rank_value, split_ties).mean(axis=0)
        for me, opp in [(a[i], b[i]), (b[i], a[i])]:
            p_win, p_lose = res[me][me], res[opp][me]
            out.append({"match_id": comp.at[i, "match_id"], "team_id": teams[me], "p_title_if_win": p_win,
                        "p_title_if_lose": p_lose, "tsp": p_win - p_lose,
                        "points_before": base[me], "rank_before": int((base > base[me]).sum() + 1)})
    return pd.DataFrame(out)


# ---------------------------------------------------------------- knockouts
def knockout_value(stage: str, order: int, fmt: str) -> float:
    """Exact stakes of a knockout game under 50/50 matches (Final 1.0, Semi/Q2 0.5, Q1/Eliminator 0.25)."""
    if stage == "Final":
        return 1.0
    if stage == "Semi Final":
        return 0.5
    if stage == "Eliminator":
        return 0.25                           # win -> Q2 -> Final: 0.5 x 0.5 ; lose -> out
    if stage == "Qualifier" and fmt == "ipl":
        return 0.25 if order == 1 else 0.5    # Q1: win -> final (0.5), lose -> Q2 (0.25). Q2: loser out
    return np.nan


def competition_format(g: pd.DataFrame) -> str:
    """Detect the format: 'ipl', 'bilateral', 'round_robin', 'round_robin_final' or 'knockouts_only'."""
    n_teams = len(pd.unique(g[["home_team_id", "away_team_id"]].values.ravel()))
    stages = set(g["stage"])
    if g["competition_group"].iat[0] == "IPL":
        return "ipl"
    if n_teams == 2:
        return "bilateral"
    if n_teams <= 4 and stages <= {"League", "Others", "Final"}:
        return "round_robin_final" if "Final" in stages else "round_robin"
    return "knockouts_only"


def main():
    """Compute stakes for every team in every match of every competition and save pressure_tsp.parquet."""
    matches = match_results(pd.read_parquet(C.PROCESSED / "matches.parquet"))
    state = pd.read_parquet(C.PROCESSED / "match_state.parquet")
    nrr = net_run_rate_before(state, matches)
    rows = []
    for k, (cid, g) in enumerate(matches.groupby("comp_id")):
        fmt = competition_format(g)
        league_mask = g["stage"].isin(["League", "Others"])
        if fmt in ("ipl", "bilateral", "round_robin", "round_robin_final"):
            rv = {"ipl": IPL_TITLE_BY_RANK, "bilateral": {1: 1.0}, "round_robin": LEAGUE_ONLY_BY_RANK,
                  "round_robin_final": TOP2_FINAL_BY_RANK}[fmt]
            lg = league_stakes(g[league_mask], nrr, rv, split_ties=(fmt == "bilateral"), seed=int(cid))
            rows.append(lg.assign(tsp_method=f"simulated_{fmt}"))
        ko = g[~league_mask].sort_values(["match_date", "match_number"])
        q_order = ko["stage"].eq("Qualifier").cumsum()
        for (_, r), qo in zip(ko.iterrows(), q_order):
            v = knockout_value(r["stage"], qo, fmt)
            for t in (r["home_team_id"], r["away_team_id"]):
                rows.append(pd.DataFrame([{"match_id": r["match_id"], "team_id": t, "tsp": v,
                                           "tsp_method": "knockout_exact" if not np.isnan(v) else "structure_unknown"}]))
        if fmt == "knockouts_only":
            for _, r in g[league_mask].iterrows():
                for t in (r["home_team_id"], r["away_team_id"]):
                    rows.append(pd.DataFrame([{"match_id": r["match_id"], "team_id": t, "tsp": np.nan,
                                               "tsp_method": "structure_unknown"}]))
    tsp = pd.concat(rows, ignore_index=True)
    tsp["tsp"] = tsp["tsp"].clip(lower=0)  # MC noise can give tiny negatives
    tsp["tsp_100"] = tsp["tsp"] * 100
    tsp = tsp.merge(matches[["match_id", "comp_name", "competition_group", "stage", "match_date", "match_number"]], on="match_id")
    teams = pd.concat([matches[["home_team_id", "home_team"]].set_axis(["team_id", "team"], axis=1),
                       matches[["away_team_id", "away_team"]].set_axis(["team_id", "team"], axis=1)]).drop_duplicates("team_id")
    tsp = tsp.merge(teams, on="team_id", how="left")
    tsp.to_parquet(OUT_FILE, index=False)
    report(tsp)


def report(tsp: pd.DataFrame):
    """Write outputs/tsp_report.md: coverage, stakes through an IPL season, knockouts and examples."""
    r = ["# Tournament Stakes Pressure\n",
         "TSP = P(win competition | win match) - P(win competition | lose match), 0-1 (x100 for 0-100).\n",
         "## Coverage", tsp.groupby(["competition_group", "tsp_method"]).size().unstack(fill_value=0).to_markdown()]
    ipl = tsp[tsp["competition_group"] == "IPL"].copy()
    lg = ipl[ipl["stage"] == "League"].copy()
    lg["block"] = pd.cut(lg.groupby("comp_name")["match_number"].rank(), [0, 14, 28, 42, 56, 71],
                         labels=["games 1-14", "15-28", "29-42", "43-56", "57-71"])
    r += ["\n## IPL league: TSP by stage of season (stakes should spread out late: must-wins up, dead rubbers to 0)",
          lg.groupby("block", observed=True)["tsp_100"].describe()[["mean", "min", "25%", "50%", "75%", "max"]].round(1).to_markdown(),
          f"\nIPL league games that were dead rubbers for a team (TSP < 0.5): {(lg['tsp_100'] < 0.5).sum()} team-games"]
    ko = ipl[ipl["stage"] != "League"].groupby("stage")["tsp_100"].mean().round(1)
    r += ["\nIPL knockouts (exact):", ko.to_markdown(),
          "\nHighest-stakes IPL league games:",
          lg.nlargest(10, "tsp")[["comp_name", "match_number", "team", "points_before", "rank_before",
                                  "p_title_if_win", "p_title_if_lose", "tsp_100"]].round(3).to_markdown(index=False),
          "\nRajasthan Royals, last 4 league games each season:",
          lg[lg["team"] == "Rajasthan Royals"].sort_values("match_date").groupby("comp_name").tail(4)
            [["comp_name", "match_number", "points_before", "rank_before", "p_title_if_win", "p_title_if_lose", "tsp_100"]]
            .round(3).to_markdown(index=False)]
    bil = tsp[tsp["tsp_method"] == "simulated_bilateral"]
    r += ["\n## Bilateral T20I series: mean TSP by match number in series",
          bil.assign(n=bil.groupby("comp_name")["match_date"].rank(method="dense"))
             .groupby("n")["tsp_100"].agg(["mean", "count"]).round(1).to_markdown()]
    txt = "\n".join(r)
    print(txt)
    (C.OUTPUTS / "tsp_report.md").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
