"""Validation evidence for the rankings + report charts.  Run:  python -m src.validate_rankings

1. Pressure separation: does the combined pressure index actually pick out different situations?
   (scoring, dismissals, dot balls, boundaries and win-probability swings by pressure decile)
2. Rank uncertainty: match-level bootstrap (resample whole matches with replacement, B draws),
   re-rate every eligible player with the baseline weights -> median rank, 90% interval, P(top 10).
3. Temporal stability: rate players on 2022-24 and on 2025-26 separately; do early pressure ratings
   predict later pressure performance, and do they add anything beyond general (normal-situation) ability?
Charts are written to outputs/figures/.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as C
from .cup import (SHRINK, BAT_COLS, BOWL_COLS, CPI_VARIANTS, ELIGIBLE, add_pressure, batting_table, bowling_table,
                  build_table, cup_score, data_weights, eb_shrink, load, player_context, score_pool)

B = 100
FIG = C.OUTPUTS / "figures"
INK, MUTED, ACCENT, ACCENT2, GRID = "#1f2937", "#6b7280", "#2563eb", "#ea580c", "#e5e7eb"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": GRID, "grid.linewidth": 0.6, "figure.dpi": 150})


# ---------------------------------------------------------------- 1. pressure separation
def pressure_separation(s: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Outcomes by pressure decile (WP swing, dismissals, SR, death/knockout share) + chart."""
    b = s[s["ball_faced"]].copy()
    b["decile"] = b.groupby("competition_group")["cpi_bat"].transform(lambda x: pd.qcut(x.rank(method="first"), 10, labels=False) + 1)
    g = b.groupby("decile")
    t = pd.DataFrame({"balls": g.size(), "strike_rate": g["batter_runs"].mean() * 100,
                      "dismissal_%": g["striker_out"].mean() * 100, "dot_%": (g["batter_runs"].apply(lambda x: (x == 0).mean())) * 100,
                      "boundary_%": g.apply(lambda x: (x["is_four"] | x["is_six"]).mean()) * 100,
                      "mean_|WPA|": g["wpa"].apply(lambda x: x.abs().mean()),
                      "death_overs_%": g["innings_phase"].apply(lambda x: (x == "Death").mean()) * 100,
                      "knockout_%": g["knock_out"].mean() * 100})
    hp = b.groupby("hp_bat").agg(strike_rate=("batter_runs", "mean"), dismissal=("striker_out", "mean"),
                                 abs_wpa=("wpa", lambda x: x.abs().mean()))
    note = (f"High-pressure balls (top 30%) carry {hp.loc[True, 'abs_wpa'] / hp.loc[False, 'abs_wpa']:.1f}x the average win-probability "
            f"swing of ordinary balls; dismissal rate {hp.loc[True, 'dismissal'] * 100:.1f}% vs {hp.loc[False, 'dismissal'] * 100:.1f}%.")
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.6))
    for a, col, title in zip(ax, ["mean_|WPA|", "dismissal_%", "strike_rate"],
                             ["Win-probability swing per ball", "Dismissal rate (%)", "Strike rate"]):
        a.plot(t.index, t[col], marker="o", color=ACCENT, lw=2)
        a.axvspan(7.5, 10.5, color=ACCENT2, alpha=0.08, lw=0)
        a.set_title(title, color=INK, fontsize=10, loc="left")
        a.set_xlabel("Pressure decile (1 = calm, 10 = highest)")
        a.set_xticks(range(1, 11))
    ax[0].text(0.03, 0.92, "shaded = high-pressure zone (top 30%)", transform=ax[0].transAxes, color=ACCENT2, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "pressure_separation.png")
    plt.close(fig)
    return t, note


# ---------------------------------------------------------------- 2. bootstrap
def bootstrap(s: pd.DataFrame, ctx: pd.DataFrame, base: dict, weights: dict, rng) -> dict:
    """Resample whole matches B times, re-rate eligible players; median rank, 90% interval, P(top 10)."""
    mids = s["match_id"].unique()
    for r in base:                                    # (re)estimate and remember shrinkage settings on the full data
        (batting_table if r == "bat" else bowling_table)(s)
    SHRINK["mode"] = "fixed"                          # ... and hold them fixed while resampling
    ranks = {r: [] for r in base}
    cups = {r: [] for r in base}
    for i in range(B):
        draw = pd.DataFrame({"match_id": rng.choice(mids, len(mids), replace=True)})
        draw["boot_id"] = np.arange(len(draw))
        sb = draw.merge(s, on="match_id").drop(columns="match_id").rename(columns={"boot_id": "match_id"})
        for r in base:
            t, _, _ = (batting_table if r == "bat" else bowling_table)(sb)
            t = t.reindex(base[r].index)              # same eligible set as the baseline
            cup = cup_score(t, r, weights[r])
            ranks[r].append(cup.rank(ascending=False))
            cups[r].append(cup)
        if (i + 1) % 20 == 0:
            print(f"  bootstrap {i + 1}/{B}")
    SHRINK["mode"] = "estimate"
    out = {}
    for r in base:
        R = pd.concat(ranks[r], axis=1)
        out[r] = pd.DataFrame({"median_rank": R.median(axis=1), "rank_p05": R.quantile(0.05, axis=1),
                               "rank_p95": R.quantile(0.95, axis=1), "p_top10": (R <= 10).mean(axis=1),
                               # B: bagged rating = average rating over the resampled datasets (smooths sampling noise)
                               "bagged_cup": pd.concat(cups[r], axis=1).mean(axis=1)})
    return out


def rank_chart(df: pd.DataFrame, title: str, fname: str):
    """Chart the top 10 with bootstrap rank intervals."""
    top = df.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    y = np.arange(len(top))
    ax.hlines(y, top["rank_p05"], top["rank_p95"], color=ACCENT, alpha=0.35, lw=6)
    ax.plot(top["median_rank"], y, "o", color=ACCENT, label="bootstrap median rank")
    ax.plot(top["final_rank"], y, "D", color=ACCENT2, ms=5, label="final rank (bagged rating)")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{n}  (P top-10 {p:.0%})" for n, p in zip(top["player_name"], top["p_top10"])])
    ax.set_xlabel("Rank (90% bootstrap interval; resampling whole matches)")
    ax.set_title(title, color=INK, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / fname)
    plt.close(fig)


# ---------------------------------------------------------------- 3. temporal stability
def temporal(s: pd.DataFrame, ctx: pd.DataFrame, weights: dict) -> tuple[pd.DataFrame, list]:
    """Rate on 2022-24, test against UNSHRUNK 2025-26 pressure performance.

    Compares predictors from the early period: the pressure-balls-only estimate (old), the
    own-usual-level estimate (A), the normal-situation level alone, and the full CUP rating built
    each way. Higher correlation = better prediction of how the player actually performed under
    pressure later. Also reports the partial correlation of the raw pressure record with later
    pressure performance after controlling for normal ability (is there a pressure-specific trait?)."""
    early, late = s[s["match_date"].dt.year <= 2024], s[s["match_date"].dt.year >= 2025]
    rows = []
    for r in ["bat", "bowl"]:
        f = batting_table if r == "bat" else bowling_table
        te, _, _ = f(early)
        tl, _, _ = f(late)
        both = te.index.intersection(tl.index)
        half = ELIGIBLE[r]["p_balls"] / 2
        both = [p for p in both if te.at[p, "all_p_balls"] >= half and tl.at[p, "all_p_balls"] >= half]
        te, tl = te.loc[both].copy(), tl.loc[both].copy()
        sign = 1 if r == "bat" else -1               # bowlers: fewer runs conceded is better
        sec = "p_out_ae" if r == "bat" else "p_wkt_ae"
        sec_sign = -1 if r == "bat" else 1
        target = sign * tl["p_runs_ae_raw"]          # later pressure scoring / economy vs peers, unshrunk
        target2 = sec_sign * tl[f"{sec}_raw"]        # later pressure survival / wickets vs peers, unshrunk
        old = te.copy()
        old["p_runs_ae"], old[sec] = old["p_runs_ae_pop"], old[f"{sec}_pop"]
        old["d_runs_ae"] = old["p_runs_ae_pop"] - old["n_runs_ae"]
        cup_old, cup_new = cup_score(old, r, weights[r]), cup_score(te, r, weights[r])
        corr = lambda x, y: np.corrcoef(x.astype(float), y.astype(float))[0, 1]
        X = np.c_[np.ones(len(both)), te["n_runs_ae"].values]
        res = lambda v: v - X @ np.linalg.lstsq(X, v, rcond=None)[0]
        rows.append({
            "role": "batters" if r == "bat" else "bowlers", "players": len(both),
            "old estimate -> later pressure scoring/economy": corr(sign * te["p_runs_ae_pop"], target),
            "A (own level) -> later pressure scoring/economy": corr(sign * te["p_runs_ae"], target),
            "normal level only -> later": corr(sign * te["n_runs_ae"], target),
            "old CUP -> later": corr(cup_old, target),
            "A CUP -> later": corr(cup_new, target),
            "old CUP -> later survival/wickets": corr(cup_old, target2),
            "A CUP -> later survival/wickets": corr(cup_new, target2),
            "partial r: raw pressure record | normal": corr(pd.Series(res((sign * te["p_runs_ae_raw"]).values)),
                                                            pd.Series(res(target.values))),
            "CUP 2022-24 vs CUP 2025-26 (spearman)": pd.Series(cup_new).corr(pd.Series(cup_score(tl, r, weights[r])), method="spearman"),
        })
    return pd.DataFrame(rows).set_index("role").T, []


def scatter(base: pd.DataFrame, role: str, fname: str):
    """Chart: pressure vs usual (SR for batters, economy for bowlers) with the top 10 highlighted."""
    if role == "bat":
        x, y, xl, yl, title = "all_n_sr", "all_p_sr", "Strike rate in ordinary situations", "Strike rate under high pressure", "Batters: pressure vs usual"
    else:
        x, y, xl, yl, title = "all_n_econ", "all_p_econ", "Economy in ordinary situations", "Economy under high pressure", "Bowlers: pressure vs usual (lower is better)"
    fig, ax = plt.subplots(figsize=(6, 5))
    rest, top = base.iloc[10:], base.head(10)
    ax.scatter(rest[x], rest[y], s=18, color=MUTED, alpha=0.5, label="other eligible players")
    ax.scatter(top[x], top[y], s=36, color=ACCENT2, label="top 10", zorder=3)
    for _, p in top.iterrows():
        ax.annotate(p["player_name"], (p[x], p[y]), fontsize=7, color=INK, xytext=(4, 2), textcoords="offset points")
    lo, hi = min(base[x].min(), base[y].min()), max(base[x].max(), base[y].max())
    ax.plot([lo, hi], [lo, hi], color=MUTED, lw=1, ls="--")
    ax.text(hi, hi, " same as usual", color=MUTED, fontsize=8, va="bottom", ha="right")
    ax.set_xlabel(xl); ax.set_ylabel(yl); ax.set_title(title, color=INK, loc="left")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / fname)
    plt.close(fig)


def main():
    """Run all ranking validations and write outputs/validation_rankings_report.md and figures."""
    FIG.mkdir(parents=True, exist_ok=True)
    s = load()
    ctx = player_context(s)
    add_pressure(s, *CPI_VARIANTS["baseline 0.5/0.3/0.2"])
    base, weights = {}, {}
    for r in ["bat", "bowl"]:
        pool, _, rel = build_table(s, ctx, r)
        weights[r] = data_weights(rel)
        base[r] = score_pool(pool, r, weights[r])

    rep = ["# Validation evidence\n", "## 1. Does the pressure index separate pressure from ordinary situations? (batting view, all balls)"]
    sep, note = pressure_separation(s)
    rep += [sep.round(3).to_markdown(), f"\n{note}", "Chart: figures/pressure_separation.png"]

    print("bootstrap ...")
    boot = bootstrap(s, ctx, base, weights, np.random.default_rng(7))
    for r, title in [("bat", "Batters"), ("bowl", "Bowlers")]:
        df = base[r].join(boot[r])
        df["final_rank"] = df["bagged_cup"].rank(ascending=False, method="first").astype(int)
        df = df.sort_values("final_rank")
        df.to_csv(C.OUTPUTS / f"rankings_{'batting' if r == 'bat' else 'bowling'}_with_uncertainty.csv")
        rank_chart(df, f"{title}: top 10 with rank uncertainty", f"rank_uncertainty_{r}.png")
        scatter(df, r, f"pressure_vs_usual_{r}.png")       # df is sorted by the FINAL (bagged) rank
        rep += [f"\n## 2. {title}: rank uncertainty ({B} match-level bootstrap draws)",
                df[["final_rank", "rank", "player_name", "confidence", "bagged_cup", "median_rank", "rank_p05", "rank_p95", "p_top10"]].head(15)
                .round(2).to_markdown(index=False)]

    tmp, _ = temporal(s, ctx, weights)
    rep += ["\n## 3. Temporal stability: rate on 2022-24, check against 2025-26",
            tmp.round(3).to_markdown(),
            "\nPartial r > 0 means pressure performance carries information about future pressure performance beyond general ability."]
    txt = "\n".join(rep)
    print(txt)
    (C.OUTPUTS / "validation_rankings_report.md").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
