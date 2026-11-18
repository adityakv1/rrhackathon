"""Consistency Under Pressure (CUP) and player rankings.  Run:  python -m src.cup

1. Combined pressure index for every ball, per role (batter's view and bowler's view):
       CPI = W_MSP * MSP + W_TSP * TSP_pct + W_IPP * IPP          (each 0-100)
   MSP     ball-level match-situation pressure (leverage percentile)
   TSP_pct tournament stakes of the player's TEAM, as a percentile WITHIN its competition group
           (bilateral-series and IPL stakes are on different scales; never pooled raw)
   IPP     the player's own pre-match form pressure (batting IPP for batters, bowling IPP for bowlers)
   Missing parts (unknown tournament structure, short history, non-role player) = neutral 50.
   A ball is HIGH PRESSURE if its CPI is in the top PRESSURE_SHARE of balls in its competition group.

2. Competition-aware per-ball performance measures:
   * every ball belongs to a competition TIER: IPL, T20I between ICC full members, T20I involving an
     associate nation, Other T20 (A-team events).
   * runs / dismissals / wickets are measured RELATIVE to the average player on balls of the same
     tier x phase x pressure level, so tiers can be pooled without blind mixing; WPA is already on a
     common (win-probability) scale.
   * ball weight = tier weight (TIER_WEIGHT): top-level cricket (IPL, full-member T20I) counts fully,
     associate T20Is and A-team games count less. All seasons count equally (2022-26 is the brief's
     window); a recency-weighted variant is a sensitivity check.

3. Player metrics under pressure (and under normal conditions, for the uplift), each shrunk towards
   the population mean by empirical Bayes (shrinkage strength estimated from the data).

4. CUP score = weighted sum of z-scored components (weights in CUP_WEIGHTS, sensitivity-tested):
   impact (WPA/ball under pressure), scoring/economy, survival/wickets, reliability (share of pressure
   innings/spells that ADDED win probability) and uplift (pressure vs normal).
"""
import numpy as np
import pandas as pd

from . import config as C

PRESSURE_SHARE = 0.30      # alternatives 0.20 / 0.40 compared out of sample in src/select_pressure.py
RECENCY_HALFLIFE = None    # None = all seasons equal; a number = weight halves every N seasons back
FULL_MEMBERS = {"India", "Australia", "England", "New Zealand", "South Africa", "Pakistan", "Sri Lanka",
                "West Indies", "Bangladesh", "Afghanistan", "Ireland", "Zimbabwe"}
TIER_WEIGHT = {"IPL": 1.0, "T20I (full members)": 1.0, "T20I (associate)": 0.4, "Other T20": 0.3}
DATA_VARIANTS = {"baseline: tiers 1/1/0.4/0.3, equal seasons": (TIER_WEIGHT, None),
                 "IPL-primary: IPL 1, all T20I 0.5, other 0.3": ({"IPL": 1.0, "T20I (full members)": 0.5,
                                                                  "T20I (associate)": 0.5, "Other T20": 0.3}, None),
                 "all balls equal": ({k: 1.0 for k in TIER_WEIGHT}, None),
                 "recency-weighted (half-life 2 seasons)": (TIER_WEIGHT, 2.0)}
# Pressure definition used for the main ranking. Alternative weightings and cut-offs are compared out of sample
# in src/select_pressure.py (outputs/pressure_selection.md); the comparison was too noisy to justify a change
# (see the methodology notes), so the original definition is retained.
CPI_WEIGHTS = {"msp": 0.5, "tsp": 0.3, "ipp": 0.2}
BASE_CPI = "baseline 0.5/0.3/0.2"          # key of the pressure definition used for the main ranking
CPI_VARIANTS = {BASE_CPI: (CPI_WEIGHTS["msp"], CPI_WEIGHTS["tsp"], CPI_WEIGHTS["ipp"]), "equal 1/3 each": (1 / 3, 1 / 3, 1 / 3),
                "situation only": (1.0, 0.0, 0.0), "situation + stakes 0.6/0.4": (0.6, 0.4, 0.0)}
CUP_WEIGHTS = {"bat": {"impact": 0.35, "scoring": 0.20, "survival": 0.15, "reliability": 0.20, "uplift": 0.10},
               "bowl": {"impact": 0.35, "economy": 0.20, "wickets": 0.15, "reliability": 0.20, "uplift": 0.10}}
CUP_VARIANTS = {"impact only": {"impact": 1.0}, "equal weights": None}
MIN_PRESSURE_BALLS_INNINGS = 5         # an innings/spell counts as a "pressure innings" with >= this many high-pressure balls
# eligibility: enough HIGH-PRESSURE evidence (all competitions, raw counts)
ELIGIBLE = {"bat": {"p_balls": 200, "p_innings": 15}, "bowl": {"p_balls": 240, "p_innings": 20}}
CONFIDENCE = {"bat": (300, 500), "bowl": (360, 600)}   # pressure balls for Medium / High confidence
ACTIVE_FROM = pd.Timestamp("2026-01-01")   # informational only (not used for ranking)


# ---------------------------------------------------------------- data assembly
def load() -> pd.DataFrame:
    """Every reliable ball joined to its pressure inputs: MSP and WPA, both teams' tournament stakes (percentile
    within competition group), striker's batting IPP and bowler's bowling IPP; adds tier and ball weights.
    """
    s = pd.read_parquet(C.PROCESSED / "match_state.parquet")
    s = s[s["state_reliable"]].copy()
    msp = pd.read_parquet(C.PROCESSED / "pressure_msp.parquet")
    s = s.merge(msp[["match_id", "innings", "innings_ball_num", "wpa", "msp"]], on=["match_id", "innings", "innings_ball_num"], how="left")

    tsp = pd.read_parquet(C.PROCESSED / "pressure_tsp.parquet")
    tsp["tsp_pct"] = tsp.groupby("competition_group")["tsp"].rank(pct=True) * 100
    t = tsp.set_index(["match_id", "team_id"])["tsp_pct"]
    s["tsp_bat"] = t.reindex(pd.MultiIndex.from_arrays([s["match_id"], s["batting_team_id"]])).values
    s["tsp_bowl"] = t.reindex(pd.MultiIndex.from_arrays([s["match_id"], s["bowling_team_id"]])).values

    ipp = pd.read_parquet(C.PROCESSED / "pressure_ipp.parquet")
    ipp["player_id"] = ipp["player_id"].astype("int64")
    for role, col in [("bat", "striker_id"), ("bowl", "bowler_id")]:
        x = ipp[ipp["role"] == role].drop_duplicates(["match_id", "innings", "player_id"]).set_index(["match_id", "innings", "player_id"])["ipp"]
        s[f"ipp_{role}"] = x.reindex(pd.MultiIndex.from_arrays([s["match_id"], s["innings"], s[col]])).values

    s["striker_out"] = s["batter_out"] & (s["dismissed_player_id"] == s["striker_id"])
    s["tier"] = competition_tier(s)
    set_weights(s, TIER_WEIGHT, RECENCY_HALFLIFE)
    return s


def competition_tier(s: pd.DataFrame) -> pd.Series:
    """IPL / T20I between ICC full members / T20I involving an associate / Other T20 (A-team events)."""
    m = pd.read_parquet(C.PROCESSED / "matches.parquet")
    both_full = (m["home_team"].isin(FULL_MEMBERS) & m["away_team"].isin(FULL_MEMBERS)).set_axis(m["match_id"])
    full = s["match_id"].map(both_full).fillna(False).astype(bool)
    return pd.Series(np.select([s["competition_group"].eq("IPL"), s["competition_group"].eq("T20I") & full,
                                s["competition_group"].eq("T20I")],
                               ["IPL", "T20I (full members)", "T20I (associate)"], "Other T20"), index=s.index)


def set_weights(s: pd.DataFrame, tier_w: dict, halflife) -> None:
    """Ball weight w = tier weight x (optional) recency weight that halves every `halflife` seasons."""
    year = s["match_date"].dt.year
    rec = 1.0 if halflife is None else 0.5 ** ((year.max() - year) / halflife)
    s["w"] = s["tier"].map(tier_w) * rec


def add_pressure(s: pd.DataFrame, wm: float, wt: float, wi: float) -> pd.DataFrame:
    """Combined pressure CPI = wm*MSP + wt*TSP + wi*IPP for the batter's and bowler's view (missing part = 50);
    hp_bat / hp_bowl flag the top PRESSURE_SHARE of balls within each competition group.
    """
    for role in ["bat", "bowl"]:
        cpi = wm * s["msp"] + wt * s[f"tsp_{role}"].fillna(50) + wi * s[f"ipp_{role}"].fillna(50)
        s[f"cpi_{role}"] = cpi
        cut = cpi.groupby(s["competition_group"]).transform(lambda x: x.quantile(1 - PRESSURE_SHARE))
        s[f"hp_{role}"] = cpi >= cut
    return s


# ---------------------------------------------------------------- empirical Bayes shrinkage
# Shrinkage settings (k, tau2) are estimated on the full data and REMEMBERED by key. In the match bootstrap
# they are held FIXED (SHRINK["mode"] = "fixed"): resampling duplicates matches, which makes duplicated
# balls look like consistent player differences and would bias the estimated shrinkage towards too little.
SHRINK = {"mode": "estimate", "params": {}}


def eb_shrink(x: pd.Series, w: pd.Series, player: pd.Series, min_n: float = 30, key: str | None = None) -> tuple[pd.Series, float]:
    """Shrink each player's weighted mean of x towards the population mean.

    k (noise-to-signal ratio, in balls or innings) is a property of the METRIC, so it is estimated by
    method of moments on UNWEIGHTED data: k = within-player variance / between-player variance.
    It is then applied to the recency/competition-weighted mean using the effective sample size
    n_eff = (sum w)^2 / sum w^2:   shrunk = mu + (mean - mu) * n_eff / (n_eff + k).
    Returns k = inf (everything shrunk to the mean) if no between-player signal is detectable."""
    df = pd.DataFrame({"x": x.values, "w": w.values, "p": player.values})
    # --- k from unweighted moments
    g0 = df.groupby("p")["x"].agg(["mean", "var", "size"])
    mu0 = df["x"].mean()
    within = np.average(g0["var"].fillna(0), weights=g0["size"])
    big = g0["size"] >= min_n
    tau2 = np.average((g0.loc[big, "mean"] - mu0) ** 2, weights=g0.loc[big, "size"]) - \
        np.average(within / g0.loc[big, "size"], weights=g0.loc[big, "size"])
    k = within / tau2 if tau2 > 0 else np.inf
    if key is not None:
        if SHRINK["mode"] == "fixed" and key in SHRINK["params"]:
            k = SHRINK["params"][key]
        else:
            SHRINK["params"][key] = k
    # --- apply to weighted means
    df["wx"], df["ww"] = df["w"] * df["x"], df["w"] ** 2
    g = df.groupby("p")[["w", "wx", "ww"]].sum()
    m = g["wx"] / g["w"].replace(0, np.nan)
    n_eff = g["w"] ** 2 / g["ww"].replace(0, np.nan)
    mu = df["wx"].sum() / df["w"].sum()
    shr = mu + (m.fillna(mu) - mu) * (n_eff / (n_eff + k) if np.isfinite(k) else 0)
    return shr, k


def split_half(x: pd.Series, player: pd.Series, min_n: int) -> float:
    """Repeatability of a per-player mean: correlation between odd- and even-numbered observations
    across players with >= min_n observations (raw, unweighted)."""
    df = pd.DataFrame({"x": x.values, "p": player.values})
    df["half"] = df.groupby("p").cumcount() % 2
    n = df.groupby("p").size()
    h = df[df["p"].isin(n[n >= min_n].index)].groupby(["p", "half"])["x"].mean().unstack()
    return h.corr().iloc[0, 1] if len(h) > 10 else np.nan


def split_half_diff(xp: pd.Series, pp: pd.Series, xn: pd.Series, pn: pd.Series, min_n: int) -> float:
    """Repeatability of (pressure mean - normal mean): halves built separately in both subsets."""
    def halves(x, p):
        """Per-player means of odd- and even-numbered observations (players with >= min_n only)."""
        df = pd.DataFrame({"x": x.values, "p": p.values})
        df["half"] = df.groupby("p").cumcount() % 2
        n = df.groupby("p").size()
        return df[df["p"].isin(n[n >= min_n].index)].groupby(["p", "half"])["x"].mean().unstack()
    d = (halves(xp, pp) - halves(xn, pn)).dropna()
    return d.corr().iloc[0, 1] if len(d) > 10 else np.nan


MIN_SPLIT = {"bat": (200, 16), "bowl": (240, 16)}   # (pressure balls, pressure innings) for repeatability tests


def _wmean(x: pd.Series, w: pd.Series, p: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Per-player weighted mean and effective sample size n_eff = (sum w)^2 / sum w^2."""
    df = pd.DataFrame({"wx": (w * x).values, "w": w.values, "ww": (w ** 2).values, "p": p.values})
    g = df.groupby("p")[["wx", "w", "ww"]].sum()
    return g["wx"] / g["w"].replace(0, np.nan), g["w"] ** 2 / g["ww"].replace(0, np.nan)


def eb_two_level(xp, wp, pp, xn, wn, pn, min_n: int = 30, key: str | None = None) -> tuple[pd.Series, pd.Series, pd.Series, dict]:
    """Pressure performance estimated RELATIVE TO THE PLAYER'S OWN USUAL LEVEL (two-level empirical Bayes).

    level  = the player's normal-situation mean, shrunk towards the population (eb_shrink, uses all normal balls)
    diff   = pressure mean - normal mean, shrunk towards the average difference by
             lambda = tau2 / (tau2 + noise_i), where tau2 is the TRUE between-player variance of the
             difference (method of moments on unweighted data) and noise_i its sampling variance.
    pressure estimate = level + shrunk diff.
    If differences are mostly noise (tau2 ~ 0) the estimate falls back on the player's usual level;
    if they are a real, persistent trait, they are kept. The data decides.
    Returns (pressure estimate, shrunk diff, normal level, info)."""
    level, k_n = eb_shrink(xn, wn, pn, key=None if key is None else f"{key}_level")
    mp, nep = _wmean(xp, wp, pp)
    mn, nen = _wmean(xn, wn, pn)
    # --- tau2 of the difference from unweighted moments
    gp = xp.groupby(pp.values).agg(["mean", "var", "size"])
    gn = xn.groupby(pn.values).agg(["mean", "var", "size"])
    vp = np.average(gp["var"].fillna(0), weights=gp["size"])
    vn = np.average(gn["var"].fillna(0), weights=gn["size"])
    j = gp.index.intersection(gn.index)
    j = j[(gp.loc[j, "size"] >= min_n) & (gn.loc[j, "size"] >= min_n)]
    d0 = gp.loc[j, "mean"] - gn.loc[j, "mean"]
    noise0 = vp / gp.loc[j, "size"] + vn / gn.loc[j, "size"]
    wts = gp.loc[j, "size"]
    mu_d = np.average(d0, weights=wts)
    tau2 = max(np.average((d0 - mu_d) ** 2, weights=wts) - np.average(noise0, weights=wts), 0.0)
    if key is not None:
        if SHRINK["mode"] == "fixed" and f"{key}_tau2" in SHRINK["params"]:
            tau2 = SHRINK["params"][f"{key}_tau2"]
        else:
            SHRINK["params"][f"{key}_tau2"] = tau2
    # --- per-player shrinkage of the weighted difference
    idx = level.index
    d = (mp.reindex(idx) - mn.reindex(idx))
    noise = vp / nep.reindex(idx) + vn / nen.reindex(idx)
    lam = (tau2 / (tau2 + noise)).fillna(0) if tau2 > 0 else pd.Series(0.0, index=idx)
    diff = mu_d + lam * (d.fillna(mu_d) - mu_d)
    info = {"k_normal": k_n, "k_diff": (vp / tau2) if tau2 > 0 else np.inf,
            "median_lambda": float(lam[nep.reindex(idx) >= min_n].median()) if tau2 > 0 else 0.0}
    return level + diff, diff, level, info


# ---------------------------------------------------------------- player tables
def batting_table(s: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Per-batter metrics: shrunk pressure impact, scoring, survival, normal scoring, pressure-innings
    reliability, component repeatability and descriptive pressure/normal stats.
    """
    b = s[s["ball_faced"]].copy()
    # expectation = average batter on balls of the same competition group x phase x pressure tier,
    # so "above expected" compares a player with peers facing the same kind of situation
    peer = b.groupby(["tier", "innings_phase", "hp_bat"])
    b["runs_ae"] = b["batter_runs"] - peer["batter_runs"].transform("mean")
    b["out_ae"] = b["striker_out"].astype(float) - peer["striker_out"].transform("mean")
    b["dot"] = (b["batter_runs"] == 0).astype(float)
    b["boundary"] = (b["is_four"] | b["is_six"]).astype(float)
    hp, pid = b["hp_bat"], b["striker_id"]
    P, N = b[hp], b[~hp]
    ks = {}
    out = pd.DataFrame(index=pd.Index(b["striker_id"].unique(), name="player_id"))
    out["p_wpa"], ks["p_wpa"] = eb_shrink(P["wpa"], P["w"], P["striker_id"], key="bat_p_wpa")
    for m in ["runs_ae", "out_ae"]:
        est, diff, level, info = eb_two_level(P[m], P["w"], P["striker_id"], N[m], N["w"], N["striker_id"], key=f"bat_{m}")
        out[f"p_{m}"], out[f"d_{m}"], out[f"n_{m}"] = est, diff, level          # pressure, pressure-vs-usual, usual
        out[f"p_{m}_pop"] = eb_shrink(P[m], P["w"], P["striker_id"], key=f"bat_{m}_pop")[0]         # old estimator (pressure balls only)
        out[f"p_{m}_raw"] = _wmean(P[m], P["w"], P["striker_id"])[0]            # unshrunk, for validation
        ks[f"p_{m}"], ks[f"d_{m}"], ks[f"lambda_{m}"] = info["k_normal"], info["k_diff"], info["median_lambda"]
    # innings-level reliability: share of pressure innings in which the batter ADDED win probability
    inn = b.groupby(["striker_id", "match_id", "innings"]).agg(
        wpa=("wpa", "sum"), hp_balls=("hp_bat", "sum"), w=("w", "mean")).reset_index()
    pin = inn[inn["hp_balls"] >= MIN_PRESSURE_BALLS_INNINGS]
    out["reliability"], ks["reliability"] = eb_shrink((pin["wpa"] > 0).astype(float), pin["w"], pin["striker_id"], min_n=3, key="bat_rel")
    out["pressure_innings"] = pin.groupby("striker_id").size()
    out["pressure_innings_wpa_sd"] = pin.groupby("striker_id")["wpa"].std()
    nb, ni = MIN_SPLIT["bat"]
    rel = {"impact": split_half(P["wpa"], P["striker_id"], nb),
           "scoring": split_half(P["runs_ae"], P["striker_id"], nb),
           "survival": split_half(P["out_ae"], P["striker_id"], nb),
           "reliability": split_half((pin["wpa"] > 0).astype(float), pin["striker_id"], ni),
           "uplift": split_half_diff(P["runs_ae"], P["striker_id"], N["runs_ae"], N["striker_id"], nb)}

    # descriptive, unshrunk, IPL-only and all-comp numbers for the profile
    def desc(sub, tag):
        """Plain descriptive batting stats (balls, runs, SR, average, dot %, boundary %, WPA) for a subset."""
        g = sub.groupby("striker_id")
        d = pd.DataFrame({f"{tag}_balls": g.size(), f"{tag}_runs": g["batter_runs"].sum(),
                          f"{tag}_outs": g["striker_out"].sum(), f"{tag}_dot_pct": g["dot"].mean() * 100,
                          f"{tag}_boundary_pct": g["boundary"].mean() * 100, f"{tag}_wpa": g["wpa"].sum()})
        d[f"{tag}_sr"] = d[f"{tag}_runs"] / d[f"{tag}_balls"] * 100
        d[f"{tag}_avg"] = d[f"{tag}_runs"] / d[f"{tag}_outs"].replace(0, np.nan)
        return d
    ipl = b["competition_group"] == "IPL"
    for sub, tag in [(b[hp], "all_p"), (b[~hp], "all_n"), (b[ipl & hp], "ipl_p"), (b[ipl & ~hp], "ipl_n"), (b[ipl], "ipl"),
                     (b[b["competition_group"] == "T20I"], "t20i"), (b[(b["competition_group"] == "T20I") & hp], "t20i_p")]:
        out = out.join(desc(sub, tag))
    out["sr_uplift"] = out["all_p_sr"] - out["all_n_sr"]
    return out, ks, rel


def bowling_table(s: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Per-bowler metrics: shrunk pressure impact, economy, wickets, normal economy, pressure-spell
    reliability, component repeatability and descriptive pressure/normal stats.
    """
    b = s.copy()
    b["wpa_bowl"] = -b["wpa"]
    peer = b.groupby(["tier", "innings_phase", "hp_bowl"])   # same-situation peers (see batting_table)
    b["runs_ae"] = b["bowler_runs"] - peer["bowler_runs"].transform("mean")
    b["wkt_ae"] = b["bowler_wicket"].astype(float) - peer["bowler_wicket"].transform("mean")
    b["dot"] = ((b["total_runs"] == 0) & b["legal_ball"]).astype(float)
    b["boundary"] = (b["is_four"] | b["is_six"]).astype(float)
    hp = b["hp_bowl"]
    P, N = b[hp], b[~hp]
    ks = {}
    out = pd.DataFrame(index=pd.Index(b["bowler_id"].unique(), name="player_id"))
    out["p_wpa"], ks["p_wpa"] = eb_shrink(P["wpa_bowl"], P["w"], P["bowler_id"], key="bowl_p_wpa")
    for m in ["runs_ae", "wkt_ae"]:
        est, diff, level, info = eb_two_level(P[m], P["w"], P["bowler_id"], N[m], N["w"], N["bowler_id"], key=f"bowl_{m}")
        out[f"p_{m}"], out[f"d_{m}"], out[f"n_{m}"] = est, diff, level
        out[f"p_{m}_pop"] = eb_shrink(P[m], P["w"], P["bowler_id"], key=f"bowl_{m}_pop")[0]
        out[f"p_{m}_raw"] = _wmean(P[m], P["w"], P["bowler_id"])[0]
        ks[f"p_{m}"], ks[f"d_{m}"], ks[f"lambda_{m}"] = info["k_normal"], info["k_diff"], info["median_lambda"]
    sp = b.groupby(["bowler_id", "match_id", "innings"]).agg(
        wpa=("wpa_bowl", "sum"), hp_balls=("hp_bowl", "sum"), w=("w", "mean")).reset_index()
    psp = sp[sp["hp_balls"] >= MIN_PRESSURE_BALLS_INNINGS]
    out["reliability"], ks["reliability"] = eb_shrink((psp["wpa"] > 0).astype(float), psp["w"], psp["bowler_id"], min_n=3, key="bowl_rel")
    out["pressure_spells"] = psp.groupby("bowler_id").size()
    out["pressure_spells_wpa_sd"] = psp.groupby("bowler_id")["wpa"].std()
    nb, ni = MIN_SPLIT["bowl"]
    rel = {"impact": split_half(P["wpa_bowl"], P["bowler_id"], nb),
           "economy": split_half(-P["runs_ae"], P["bowler_id"], nb),
           "wickets": split_half(P["wkt_ae"], P["bowler_id"], nb),
           "reliability": split_half((psp["wpa"] > 0).astype(float), psp["bowler_id"], ni),
           "uplift": split_half_diff(-P["runs_ae"], P["bowler_id"], -N["runs_ae"], N["bowler_id"], nb)}

    def desc(sub, tag):
        """Plain descriptive bowling stats (balls, runs, wickets, economy, wkts/24, dot %, WPA) for a subset."""
        g = sub.groupby("bowler_id")
        d = pd.DataFrame({f"{tag}_balls": g["legal_ball"].sum(), f"{tag}_runs": g["bowler_runs"].sum(),
                          f"{tag}_wkts": g["bowler_wicket"].sum(), f"{tag}_dot_pct": g["dot"].mean() * 100,
                          f"{tag}_boundary_pct": g["boundary"].mean() * 100, f"{tag}_wpa": g["wpa_bowl"].sum()})
        d[f"{tag}_econ"] = d[f"{tag}_runs"] / d[f"{tag}_balls"].replace(0, np.nan) * 6
        d[f"{tag}_wkts_per24"] = d[f"{tag}_wkts"] / d[f"{tag}_balls"].replace(0, np.nan) * 24
        return d
    ipl = b["competition_group"] == "IPL"
    for sub, tag in [(b[hp], "all_p"), (b[~hp], "all_n"), (b[ipl & hp], "ipl_p"), (b[ipl & ~hp], "ipl_n"), (b[ipl], "ipl"),
                     (b[b["competition_group"] == "T20I"], "t20i"), (b[(b["competition_group"] == "T20I") & hp], "t20i_p")]:
        out = out.join(desc(sub, tag))
    out["econ_uplift"] = out["all_n_econ"] - out["all_p_econ"]   # + = tighter under pressure
    return out, ks, rel


# ---------------------------------------------------------------- roles, activity, squad
def player_context(s: pd.DataFrame) -> pd.DataFrame:
    """Descriptive player info: name, last match, batting role, keeper flag, pace/spin, bowling phase role, IPL team."""
    raw = {n: pd.read_csv(C.RAW / f"{n}.csv") for n in ["playing_eleven", "competition_team_player_mapping"]}
    names = pd.concat([s[["striker_id", "striker_name"]].set_axis(["player_id", "player_name"], axis=1),
                       s[["bowler_id", "bowler_name"]].set_axis(["player_id", "player_name"], axis=1)]).drop_duplicates("player_id").set_index("player_id")
    ctx = names.copy()
    last = pd.concat([s[["striker_id", "match_date"]].set_axis(["player_id", "d"], axis=1),
                      s[["bowler_id", "match_date"]].set_axis(["player_id", "d"], axis=1)]).groupby("player_id")["d"].max()
    ctx["last_match"] = last
    ipl_last = s[s["competition_group"] == "IPL"].groupby("striker_id")["match_date"].max()
    ctx["last_ipl_match"] = pd.concat([ipl_last, s[s["competition_group"] == "IPL"].groupby("bowler_id")["match_date"].max()]).groupby(level=0).max()

    # batting position: median over the most recent 2 seasons of innings (all comps)
    inn = s.groupby(["striker_id", "match_id"]).agg(pos=("batting_order", "min"), d=("match_date", "first")).reset_index()
    recent = inn[inn["d"] >= inn.groupby("striker_id")["d"].transform("max") - pd.Timedelta(days=730)]
    pos = recent.groupby("striker_id")["pos"].median()
    ctx["usual_position"] = pos
    ctx["batting_role"] = pd.cut(pos, [0, 2, 3, 5, 7, 99], labels=["Opener", "Top order (3)", "Middle order (4-5)", "Finisher (6-7)", "Lower order"]).astype(str)
    pe = raw["playing_eleven"]
    pe = pe[pe["is_played"] == True]
    wk = pe["is_wk"].astype(float).groupby(pe["player_id"]).mean()
    ctx["keeper"] = wk.reindex(ctx.index).fillna(0) >= 0.3

    # bowling: pace/spin and phase specialism (share of legal balls)
    lb = s[s["legal_ball"]]
    ps = lb.groupby("bowler_id")["pace_or_spin"].agg(lambda x: x.mode().iat[0] if x.notna().any() else np.nan)
    ctx["pace_or_spin"] = ps
    # phase usage from IPL balls when a bowler has >= 120 of them (RR's use case), else all competitions.
    # Death overs are only 4 of 20 (~20% of balls), so >= 33% at the death is a strong specialism.
    share_all = pd.crosstab(lb["bowler_id"], lb["innings_phase"], normalize="index")
    ipl_lb = lb[lb["competition_group"] == "IPL"]
    share_ipl = pd.crosstab(ipl_lb["bowler_id"], ipl_lb["innings_phase"], normalize="index")
    enough = ipl_lb.groupby("bowler_id").size() >= 120
    share = share_all.copy()
    idx = enough[enough].index.intersection(share_ipl.index)
    share.loc[idx] = share_ipl.loc[idx, share.columns]
    role = np.select([share.get("Death", 0) >= 0.33, share.get("Powerplay", 0) >= 0.45, share.get("Middle", 0) >= 0.65],
                     ["Death specialist", "Powerplay specialist", "Middle-overs specialist"], "All-phase")
    ctx["bowling_role"] = pd.Series(role, index=share.index)
    for ph in ["Powerplay", "Middle", "Death"]:
        ctx[f"share_{ph.lower()}"] = share.get(ph)

    mp = raw["competition_team_player_mapping"]
    latest_ipl = mp[mp["comp_name"].str.contains(r"\bIPL\b", na=False)]["comp_name"].max()
    squad = mp[mp["comp_name"] == latest_ipl]
    ctx["ipl_team_latest"] = squad.drop_duplicates("player_id").set_index("player_id")["team_name"]
    ctx["current_rr"] = ctx["ipl_team_latest"].eq("Rajasthan Royals")
    # active for a 2027 auction: played any T20 in the latest season, or named in the latest IPL squad
    ctx["active"] = (ctx["last_match"] >= ACTIVE_FROM) | ctx["ipl_team_latest"].notna()
    return ctx


# ---------------------------------------------------------------- scoring
def zscore(x: pd.Series) -> pd.Series:
    """Standardise across the eligible players (mean 0, sd 1)."""
    return (x - x.mean()) / x.std()


def cup_score(t: pd.DataFrame, role: str, weights: dict | None) -> pd.Series:
    """Weighted sum of z-scored rating components (impact, scoring/economy, survival/wickets, reliability, uplift)."""
    if role == "bat":
        comps = {"impact": t["p_wpa"], "scoring": t["p_runs_ae"], "survival": -t["p_out_ae"],
                 "reliability": t["reliability"], "uplift": t["d_runs_ae"]}       # d_ = shrunk pressure - own usual level
    else:
        comps = {"impact": t["p_wpa"], "economy": -t["p_runs_ae"], "wickets": t["p_wkt_ae"],
                 "reliability": t["reliability"], "uplift": -t["d_runs_ae"]}
    if weights is None:
        weights = {k: 1 / len(comps) for k in comps}
    z = {k: zscore(v) for k, v in comps.items()}
    for k, v in z.items():
        t[f"z_{k}"] = v
    return sum(weights.get(k, 0) * z[k].fillna(0) for k in comps)


def build_table(s: pd.DataFrame, ctx: pd.DataFrame, role: str):
    """Player metrics + context + eligibility for one role under the CURRENT pressure and weights."""
    t, ks, rel = (batting_table if role == "bat" else bowling_table)(s)
    t = t.join(ctx)
    n_inn = t["pressure_innings" if role == "bat" else "pressure_spells"].fillna(0)
    e = ELIGIBLE[role]
    t["eligible"] = (t["all_p_balls"].fillna(0) >= e["p_balls"]) & (n_inn >= e["p_innings"])
    return t[t["eligible"]].copy(), ks, rel


def data_weights(rel: dict) -> dict:
    """CUP weights proportional to each component's split-half repeatability (negatives -> 0)."""
    r = {k: max(v, 0) if pd.notna(v) else 0 for k, v in rel.items()}
    tot = sum(r.values())
    return {k: v / tot for k, v in r.items()}


def score_pool(pool: pd.DataFrame, role: str, weights: dict) -> pd.DataFrame:
    """Rate, convert to a 0-100 percentile, assign confidence tier, sort and rank the eligible players."""
    pool = pool.copy()
    pool["cup"] = cup_score(pool, role, weights)
    pool["cup_100"] = pool["cup"].rank(pct=True) * 100
    lo, hi = CONFIDENCE[role]
    n_p = pool["all_p_balls"].fillna(0)
    pool["confidence"] = np.select([n_p >= hi, n_p >= lo], ["High", "Medium"], "Low")
    pool = pool.sort_values("cup", ascending=False)
    pool["rank"] = np.arange(1, len(pool) + 1)
    return pool


def weight_variants(role: str, rel: dict) -> dict:
    """Alternative rating weightings used in the sensitivity analysis."""
    comps = list(CUP_WEIGHTS[role])
    dw = data_weights(rel)
    # "rise above own usual level" framing: half the weight on uplift, the rest as in the data-driven weights
    rise = {k: (0.5 if k == "uplift" else 0.5 * v / (1 - dw["uplift"])) for k, v in dw.items()}
    return {"data-driven (repeatability)": dw, "expert 0.35/0.2/0.15/0.2/0.1": CUP_WEIGHTS[role],
            "equal weights": {k: 1 / len(comps) for k in comps}, "impact only": {"impact": 1.0},
            "rise above own usual (uplift 50%)": rise}


# ---------------------------------------------------------------- report
def compare(base: pd.DataFrame, other: pd.DataFrame, label: str) -> dict:
    """Top-10 overlap, same #1 and Spearman correlation between a ranking and the baseline."""
    j = base[["cup"]].join(other[["cup"]], rsuffix="_v").dropna()
    top_b, top_o = list(base.head(10).index), list(other.head(10).index)
    return {"variant": label, "top-10 overlap": len(set(top_b) & set(top_o)),
            "same #1": top_b[0] == top_o[0], "spearman (all eligible)": j.corr(method="spearman").iloc[0, 1]}


def run_all():
    """Score the baseline and every sensitivity variant. Returns (baseline rankings, variant rankings, diagnostics)."""
    s = load()
    ctx = player_context(s)
    base_cpi = CPI_VARIANTS[BASE_CPI]
    tables = {}
    for dlabel, (tw, hl) in DATA_VARIANTS.items():           # competition weighting / recency variants
        set_weights(s, tw, hl)
        add_pressure(s, *base_cpi)
        tables[("data", dlabel)] = {r: build_table(s, ctx, r) for r in ["bat", "bowl"]}
    set_weights(s, TIER_WEIGHT, RECENCY_HALFLIFE)
    for clabel, cw in CPI_VARIANTS.items():                    # pressure-definition variants
        add_pressure(s, *cw)
        tables[("cpi", clabel)] = {r: build_table(s, ctx, r) for r in ["bat", "bowl"]}
    add_pressure(s, *base_cpi)
    base_key = ("cpi", BASE_CPI)
    out, variants, diag = {}, {}, {}
    for r in ["bat", "bowl"]:
        pool, ks, rel = tables[base_key][r]
        wv = weight_variants(r, rel)
        out[r] = score_pool(pool, r, wv["data-driven (repeatability)"])
        diag[r] = {"ks": ks, "rel": rel, "weights": wv["data-driven (repeatability)"]}
        v = {f"rating weights: {n}": score_pool(pool, r, w) for n, w in wv.items()}
        for (kind, label), tb in tables.items():
            if (kind, label) == base_key:
                continue
            p2, _, rel2 = tb[r]
            v[("competition weighting: " if kind == "data" else "pressure definition: ") + label] = score_pool(p2, r, data_weights(rel2))
        variants[r] = v
    return s, out, variants, diag


def save_profiles(s: pd.DataFrame) -> None:
    """Save every player's metrics (eligible or not) and a profile of where high-pressure balls come from.

    outputs/players_all_batting.csv / players_all_bowling.csv: like rankings_*.csv but for ALL players
    (used for squad views, e.g. players just below the eligibility threshold).
    outputs/pressure_profile.json: share of high-pressure balls in nearly-decided games and by over band."""
    import json
    ctx = player_context(s)
    for name, f in [("batting", batting_table), ("bowling", bowling_table)]:
        t, _, _ = f(s)
        t.join(ctx).to_csv(C.OUTPUTS / f"players_all_{name}.csv")
    wp = pd.read_parquet(C.PROCESSED / "pressure_msp.parquet", columns=["match_id", "innings", "innings_ball_num", "wp_before"])
    x = s[s["ball_faced"] & s["hp_bat"]][["match_id", "innings", "innings_ball_num", "overid"]].merge(
        wp, on=["match_id", "innings", "innings_ball_num"], how="left")
    prof = {"hp_balls": int(len(x)),
            "share_nearly_decided (WP<15% or >85%)": float(((x["wp_before"] < 0.15) | (x["wp_before"] > 0.85)).mean()),
            "share_overs_1_3": float((x["overid"] <= 3).mean()),
            "share_overs_7_16": float(x["overid"].between(7, 16).mean()),
            "share_overs_17_20": float((x["overid"] >= 17).mean())}
    (C.OUTPUTS / "pressure_profile.json").write_text(json.dumps(prof, indent=2), encoding="utf-8")


BAT_COLS = ["player_name", "batting_role", "keeper", "cup_100", "confidence", "all_p_balls", "all_p_sr", "all_n_sr",
            "all_p_avg", "all_n_avg", "all_p_dot_pct", "pressure_innings", "reliability", "ipl_p_balls", "t20i_p_balls"]
BOWL_COLS = ["player_name", "bowling_role", "pace_or_spin", "cup_100", "confidence", "all_p_balls", "all_p_econ", "all_n_econ",
             "all_p_wkts_per24", "all_n_wkts_per24", "all_p_dot_pct", "pressure_spells", "reliability", "ipl_p_balls", "t20i_p_balls"]


def main():
    """Run the baseline and all variants, save rankings_*.csv and write outputs/cup_rankings_report.md."""
    s, out, variants, diag = run_all()
    C.OUTPUTS.mkdir(exist_ok=True)
    tops = {}
    save_profiles(s)
    rep = ["# Consistency Under Pressure — rankings\n",
           f"High pressure = top {PRESSURE_SHARE:.0%} of balls by combined pressure (CPI) within each competition group; "
           f"CPI weights {CPI_WEIGHTS}. Ball weight by tier {TIER_WEIGHT}; all seasons equal. "
           f"Eligible: batters >= {ELIGIBLE['bat']['p_balls']} high-pressure balls faced and >= {ELIGIBLE['bat']['p_innings']} pressure innings; "
           f"bowlers >= {ELIGIBLE['bowl']['p_balls']} high-pressure balls and >= {ELIGIBLE['bowl']['p_innings']} pressure spells.\n"]
    for r, cols, title in [("bat", BAT_COLS, "Batters"), ("bowl", BOWL_COLS, "Bowlers")]:
        base = out[r]
        base.to_csv(C.OUTPUTS / f"rankings_{'batting' if r == 'bat' else 'bowling'}.csv")
        d = diag[r]
        rep += [f"\n# {title} ({len(base)} eligible)",
                "Component repeatability (split-half r under pressure) -> rating weight; shrinkage k:",
                pd.DataFrame({"split-half r": d["rel"], "weight": d["weights"]}).join(
                    pd.Series(d["ks"], name="shrinkage k").rename({"p_wpa": "impact", "p_runs_ae": "scoring" if r == "bat" else "economy",
                                                                   "p_out_ae": "survival", "p_wkt_ae": "wickets"})).round(3).to_markdown(),
                f"\n## Top 10 {title}", base[["rank"] + cols].head(10).round(2).to_markdown(index=False),
                "\n### Ranks 11-20", base[["rank"] + cols].iloc[10:20].round(2).to_markdown(index=False)]
        rows = [compare(base, v, label) for label, v in variants[r].items()]
        rep += [f"\n## Sensitivity of the {title.lower()} top 10", pd.DataFrame(rows).round(3).to_markdown(index=False)]
        rise = variants[r]["rating weights: rise above own usual (uplift 50%)"]
        rep += [f"\n### Alternative framing — {title.lower()} who rise most above their own usual level (uplift weight 50%)",
                rise[["rank"] + cols[:4] + (["all_p_sr", "all_n_sr"] if r == "bat" else ["all_p_econ", "all_n_econ"])]
                .head(10).round(2).to_markdown(index=False)]
        tops[r] = pd.DataFrame({label: v["player_name"].head(10).values for label, v in
                                [("baseline", base)] + list(variants[r].items())}, index=range(1, 11))
        tops[r].to_csv(C.OUTPUTS / f"sensitivity_top10_{'batting' if r == 'bat' else 'bowling'}.csv", index_label="rank")
    txt = "\n".join(rep)
    print(txt)
    (C.OUTPUTS / "cup_rankings_report.md").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
