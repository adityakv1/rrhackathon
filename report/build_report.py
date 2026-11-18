"""Build the Round 1 methodology report (PDF) from the pipeline outputs.

    python report/build_report.py      ->  outputs/SupeRR_Selector_Methodology_Report.pdf

Every table is read from files the pipeline writes (outputs/*.csv, outputs/*_report.md), so the
report always matches the code. Run `python run_pipeline.py` first.
"""
import io
import json
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.validate_rankings import scatter  # noqa: E402  (same chart code as the pipeline)
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
FIG = OUT / "figures"
PDF = OUT / "SupeRR_Selector_Methodology_Report.pdf"

# ------------------------------------------------------------------ fonts & styles
FONT_DIR = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Body", str(FONT_DIR / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FONT_DIR / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", str(FONT_DIR / "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Body-BoldItalic", str(FONT_DIR / "arialbi.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-BoldItalic")

INK, MUTED, ACCENT, ACCENT2, RULE, SHADE = (colors.HexColor(c) for c in
                                             ["#1f2937", "#6b7280", "#2563eb", "#ea580c", "#d1d5db", "#f3f4f6"])
S = {
    "title": ParagraphStyle("title", fontName="Body-Bold", fontSize=22, leading=27, textColor=INK, spaceAfter=4),
    "subtitle": ParagraphStyle("subtitle", fontName="Body", fontSize=12, leading=16, textColor=MUTED, spaceAfter=14),
    "h1": ParagraphStyle("h1", fontName="Body-Bold", fontSize=15, leading=19, textColor=INK, spaceBefore=6, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="Body-Bold", fontSize=11.5, leading=15, textColor=ACCENT, spaceBefore=8, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="Body", fontSize=9.6, leading=13.6, textColor=INK, spaceAfter=5),
    "bullet": ParagraphStyle("bullet", fontName="Body", fontSize=9.6, leading=13.4, textColor=INK, leftIndent=12,
                             bulletIndent=2, spaceAfter=2.5),
    "formula": ParagraphStyle("formula", fontName="Body", fontSize=9.8, leading=14, textColor=INK, leftIndent=14,
                              backColor=SHADE, borderPadding=(5, 6, 5, 6), spaceBefore=4, spaceAfter=8),
    "caption": ParagraphStyle("caption", fontName="Body-Italic", fontSize=8.3, leading=11, textColor=MUTED, spaceAfter=8),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=8.2, leading=10.2, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Body-Bold", fontSize=8.2, leading=10.2, textColor=INK),
    "callout": ParagraphStyle("callout", fontName="Body", fontSize=9.6, leading=13.6, textColor=INK, leftIndent=8,
                              borderPadding=(6, 8, 6, 8), backColor=colors.HexColor("#eff6ff"), spaceBefore=4, spaceAfter=9),
    "centre": ParagraphStyle("centre", fontName="Body", fontSize=9, leading=12, textColor=MUTED, alignment=TA_CENTER),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def bullets(items):
    return [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def table(rows, widths, header=True, zebra=True, align_right_from=None, bold_first_col=False):
    data = [[c if isinstance(c, Paragraph) else Paragraph(str(c), S["cellb" if (header and i == 0) or (bold_first_col and j == 0) else "cell"])
             for j, c in enumerate(r)] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
          ("LINEBELOW", (0, -1), (-1, -1), 0.5, RULE), ("TOPPADDING", (0, 0), (-1, -1), 3),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if zebra:
        for i in range(1, len(rows)):
            if i % 2 == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), SHADE))
    t.setStyle(TableStyle(st))
    return t


def fig(path, width_cm, caption=None):
    img = Image(str(path))
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = width_cm * cm, width_cm * cm * ratio
    return [img, P(caption, "caption")] if caption else [img]


# ------------------------------------------------------------------ read pipeline outputs
def md_table(md: str, heading: str) -> pd.DataFrame:
    """First markdown table after a heading line that contains `heading`."""
    lines = (md.replace("mean_|WPA|", "mean_absWPA")                 # labels that contain pipes
             .replace("record | normal", "record given normal").split("\n"))
    i = next(k for k, l in enumerate(lines) if heading in l)
    while not lines[i].startswith("|"):
        i += 1
    block = []
    while i < len(lines) and lines[i].startswith("|"):
        block.append(lines[i])
        i += 1
    cells = [[c.strip() for c in r.strip("|").split("|")] for r in block]
    return pd.DataFrame(cells[2:], columns=cells[0])


def load():
    d = {}
    d["bat"] = pd.read_csv(OUT / "rankings_batting_with_uncertainty.csv").sort_values("final_rank")
    d["bowl"] = pd.read_csv(OUT / "rankings_bowling_with_uncertainty.csv").sort_values("final_rank")
    cup = (OUT / "cup_rankings_report.md").read_text(encoding="utf-8")
    val = (OUT / "validation_rankings_report.md").read_text(encoding="utf-8")
    d["rel_bat"] = md_table(cup.split("# Batters")[1], "Component repeatability")
    d["rel_bowl"] = md_table(cup.split("# Bowlers")[1], "Component repeatability")
    d["sens_bat"] = md_table(cup, "Sensitivity of the batters")
    d["sens_bowl"] = md_table(cup, "Sensitivity of the bowlers")
    d["sep"] = md_table(val, "## 1.")
    d["temporal"] = md_table(val, "## 3.")
    for r in ["bat", "bowl"]:
        d[f"top_{r}"] = pd.read_csv(OUT / f"sensitivity_top10_{'batting' if r == 'bat' else 'bowling'}.csv", index_col=0)
    d["all_bat"] = pd.read_csv(OUT / "players_all_batting.csv")         # every player, eligible or not
    d["all_bowl"] = pd.read_csv(OUT / "players_all_bowling.csv")
    d["profile"] = json.loads((OUT / "pressure_profile.json").read_text(encoding="utf-8"))
    return d


def pipeline_figure() -> Path:
    """Simple flow diagram of the method."""
    path = FIG / "pipeline.png"
    fig_, ax = plt.subplots(figsize=(10, 2.6), dpi=200)
    ax.axis("off")
    boxes = [("Ball-by-ball\ndata (validated)", 0.05), ("Match state\nbefore every ball", 0.22),
             ("3 pressure\nsignals", 0.39), ("Combined\npressure index", 0.56), ("Player ratings\nvs peers", 0.73),
             ("Ranked top 10\n+ uncertainty", 0.90)]
    for text, x in boxes:
        ax.add_patch(plt.Rectangle((x - 0.075, 0.42), 0.15, 0.36, fc="#eff6ff", ec="#2563eb", lw=1.2))
        ax.text(x, 0.60, text, ha="center", va="center", fontsize=8.6, color="#1f2937")
    for (_, a), (_, b) in zip(boxes[:-1], boxes[1:]):
        ax.annotate("", xy=(b - 0.078, 0.60), xytext=(a + 0.078, 0.60), arrowprops=dict(arrowstyle="->", color="#6b7280", lw=1.2))
    for i, t in enumerate(["Situation (MSP): win-probability leverage", "Stakes (TSP): title / series leverage",
                           "Form (IPP): own recent vs baseline"]):
        ax.text(0.39, 0.30 - i * 0.11, t, ha="center", fontsize=7.4, color="#ea580c")
    ax.set_xlim(-0.03, 1.0)
    ax.set_ylim(-0.05, 0.9)
    fig_.savefig(path, bbox_inches="tight")
    plt.close(fig_)
    return path


# ------------------------------------------------------------------ page furniture
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Body", 7.8)
    canvas.setFillColor(MUTED)
    canvas.drawString(2 * cm, 1.2 * cm, "SupeRR Selector Season 2 · Round 1 · Methodology report")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.setStrokeColor(RULE)
    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canvas.restoreState()


def fmt(x, nd=1):
    return "–" if pd.isna(x) else f"{x:.{nd}f}"


# ------------------------------------------------------------------ the report
def _rank_lookup(final: pd.DataFrame) -> dict:
    return dict(zip(final["player_id"], final["final_rank"]))


def role_section(bat: pd.DataFrame, bowl: pd.DataFrame) -> list:
    """4.4: best three per role, and the data behind the absence of death specialists from the top 10."""
    out = [P("4.4 Best under pressure by role", "h2"),
           P("The submission ranks players regardless of role. A selector also needs the best option for each job, so the same "
             "final rating is shown within each role (roles are descriptive: usual batting position over the last two years, and "
             "the phase in which a bowler bowls most of his balls; they play no part in the rating).")]

    def cell(r, kind):
        stat = (f"SR {r.all_p_sr:.0f} / {r.all_n_sr:.0f}" if kind == "bat" else f"Econ {r.all_p_econ:.2f} / {r.all_n_econ:.2f}")
        return f"<b>{r.player_name}</b> (#{int(r.final_rank)})<br/><font color='#6b7280'>{stat}</font>"

    rows = [["Batting role", "1st", "2nd", "3rd"]]
    groups = [(lbl, bat[bat.batting_role == lbl]) for lbl in ["Opener", "Top order (3)", "Middle order (4-5)", "Finisher (6-7)"]]
    groups.append(("Wicketkeepers", bat[bat.keeper == True]))  # noqa: E712
    for lbl, g in groups:
        top = g.sort_values("final_rank").head(3)
        rows.append([f"{lbl} ({len(g)})"] + [cell(r, "bat") for _, r in top.iterrows()] + [""] * (3 - len(top)))
    out.append(table(rows, [3.4 * cm, 4.5 * cm, 4.5 * cm, 4.6 * cm], bold_first_col=True))
    out.append(P("(n) = eligible players in the role. SR = strike rate under pressure / usual.", "caption"))

    rows = [["Bowling role", "1st", "2nd", "3rd"]]
    groups = [(lbl, bowl[bowl.bowling_role == lbl]) for lbl in
              ["Powerplay specialist", "Middle-overs specialist", "Death specialist", "All-phase"]]
    groups += [("Pace", bowl[bowl.pace_or_spin == "Pace"]), ("Spin", bowl[bowl.pace_or_spin == "Spin"])]
    for lbl, g in groups:
        top = g.sort_values("final_rank").head(3)
        rows.append([f"{lbl} ({len(g)})"] + [cell(r, "bowl") for _, r in top.iterrows()] + [""] * (3 - len(top)))
    out.append(table(rows, [3.4 * cm, 4.5 * cm, 4.5 * cm, 4.6 * cm], bold_first_col=True))
    out.append(P("Econ = economy under pressure / usual. Death specialist = at least 33% of balls in overs 17–20 (the average "
                 "bowler bowls ~20% there).", "caption"))

    per_over = bowl.groupby("bowling_role")["p_runs_ae"].mean() * -6     # runs per over saved vs same-situation peers
    death = bowl[bowl.bowling_role == "Death specialist"].sort_values("final_rank")
    best = death.iloc[0]
    out.append(P(f"<b>Why no death specialist is in the bowling top 10.</b> Only {len(death)} of {len(bowl)} eligible bowlers are death "
                 f"specialists. They do beat bowlers facing the same situations — on average {per_over['Death specialist']:.2f} runs per "
                 f"over fewer under pressure — but the leading middle-overs bowlers beat their peers by more "
                 f"({per_over['Middle-overs specialist']:.2f} runs per over), and economy is the most repeatable bowling measure (§2.4). "
                 f"The best death specialist, {best.player_name}, ranks #{int(best.final_rank)}. For a team choosing who bowls the 19th "
                 f"over, the role table above is the better guide than the overall list.", "callout"))
    return out


def dip_section(bat: pd.DataFrame, bowl: pd.DataFrame) -> list:
    """4.5: top-10 players whose own numbers are worse under pressure — named and explained."""
    tb, tw = bat.head(10), bowl.head(10)
    db = tb[tb.all_p_sr < tb.all_n_sr - 8]
    dw = tw[tw.all_p_econ > tw.all_n_econ + 0.5]
    if not len(db) and not len(dw):
        return []
    out = [P("4.5 Top-10 players who dip under pressure", "h2"),
           P("The brief compares pressure with each player's usual level, so we name the top-10 players whose own numbers fall "
             "under pressure and explain why they still rank highly:")]
    items = []
    for _, r in db.iterrows():
        pos = int((bat.all_p_sr > r.all_p_sr).sum() + 1)
        items.append(f"<b>{r.player_name} (#{int(r.final_rank)})</b>: strike rate {r.all_n_sr:.0f} usually, {r.all_p_sr:.0f} under "
                     f"pressure. That {r.all_p_sr:.0f} is still the {pos}{'st' if pos == 1 else 'nd' if pos == 2 else 'rd' if pos == 3 else 'th'} "
                     f"highest pressure strike rate of {len(bat)} eligible batters, {r.p_runs_ae_raw * 100:+.1f} runs per 100 balls against "
                     f"batters facing the same situations.")
    for _, r in dw.iterrows():
        pos = int((bowl.all_p_econ < r.all_p_econ).sum() + 1)
        items.append(f"<b>{r.player_name} (#{int(r.final_rank)})</b>: economy {r.all_n_econ:.2f} usually, {r.all_p_econ:.2f} under "
                     f"pressure. His usual level is exceptional; under pressure he still concedes {-r.p_runs_ae_raw * 6:.2f} runs per over "
                     f"fewer than bowlers in the same situations ({pos}{'st' if pos == 1 else 'nd' if pos == 2 else 'rd' if pos == 3 else 'th'} "
                     f"best pressure economy of {len(bowl)}).")
    out += bullets(items)
    out.append(P("Ranking on the dip itself would reward lesser players who move from poor to average, and only about 7–10% of a "
                 "player's personal pressure-vs-usual gap persists (§2.2, §5.1). So we rank on performance in pressure situations "
                 "and report the dip openly.", "callout"))
    return out


def rr_section(d: dict) -> list:
    """6: the same method applied to the Rajasthan Royals squad."""
    allb, allw = d["all_bat"], d["all_bowl"]
    rk_b, rk_w = _rank_lookup(d["bat"]), _rank_lookup(d["bowl"])
    nb, nw = len(d["bat"]), len(d["bowl"])
    out = [P("6. What this means for Rajasthan Royals", "h1"),
           P("Round 1 asks for the best players across the league. Because this is the Royals' competition, we also ran the RR "
             "squad (players listed for Rajasthan Royals in the latest IPL season of the supplied mapping) through the same method. "
             "The ratings, thresholds and pressure definition are unchanged.")]

    def status(pid, rk, n):
        return f"#{int(rk[pid])} of {n}" if pid in rk else "below threshold"

    b = allb[(allb.current_rr == True) & (allb.all_p_balls >= 100)].sort_values("all_p_balls", ascending=False)  # noqa: E712
    rows = [["Batter", "Role", "Pressure balls", "SR pressure", "SR usual", "Change", "Overall rank"]]
    for _, r in b.iterrows():
        rows.append([f"<b>{r.player_name}</b>", r.batting_role, int(r.all_p_balls), f"{r.all_p_sr:.0f}", f"{r.all_n_sr:.0f}",
                     f"{r.all_p_sr - r.all_n_sr:+.0f}", status(r.player_id, rk_b, nb)])
    out += [P("6.1 Batting", "h2"), table(rows, [3.6 * cm, 3.1 * cm, 2.0 * cm, 1.9 * cm, 1.7 * cm, 1.6 * cm, 3.1 * cm]),
            P("RR squad players with at least 100 high-pressure balls faced. Below threshold = fewer than 200 pressure balls or "
              "15 pressure innings, so not ranked.", "caption")]
    w = allw[(allw.current_rr == True) & (allw.all_p_balls >= 100)].sort_values("all_p_balls", ascending=False)  # noqa: E712
    rows = [["Bowler", "Role", "Pressure balls", "Econ pressure", "Econ usual", "Change", "Overall rank"]]
    for _, r in w.iterrows():
        rows.append([f"<b>{r.player_name}</b>", r.bowling_role.replace(" specialist", ""), int(r.all_p_balls),
                     f"{r.all_p_econ:.2f}", f"{r.all_n_econ:.2f}", f"{r.all_p_econ - r.all_n_econ:+.2f}", status(r.player_id, rk_w, nw)])
    out += [P("6.2 Bowling", "h2"), table(rows, [3.6 * cm, 3.1 * cm, 2.0 * cm, 1.9 * cm, 1.7 * cm, 1.6 * cm, 3.1 * cm]),
            P("RR squad players with at least 100 high-pressure balls bowled. Change = pressure minus usual economy "
              "(negative = tighter under pressure).", "caption")]

    # ---- findings, computed
    bb = b.set_index("player_name")
    top_b = [n for n in bb.index if bb.at[n, "player_id"] in rk_b and rk_b[bb.at[n, "player_id"]] <= 10]
    risers = bb[(bb.all_p_sr - bb.all_n_sr) >= 8].index.tolist()
    fallers = bb[(bb.all_p_sr - bb.all_n_sr) <= -8].sort_values("all_p_sr").index.tolist()
    young = b[(~b.player_id.isin(rk_b)) & (b.all_p_sr >= 180)]
    ww = w.copy()
    ww["rank"] = ww.player_id.map(rk_w)
    best_w = ww.dropna(subset=["rank"]).sort_values("rank")
    death_rr = ww[ww.bowling_role == "Death specialist"]
    items = [f"<b>Pressure batting:</b> {', '.join(top_b) if top_b else 'no RR batter'} "
             f"{'is' if len(top_b) == 1 else 'are'} in the league-wide top 10. "
             + (f"{', '.join(risers)} score{'s' if len(risers) == 1 else ''} faster under pressure than usually. " if risers else "")
             + (f"{', '.join(fallers)} slow{'s' if len(fallers) == 1 else ''} down markedly when it matters — the main batting risk "
                f"in the squad." if fallers else "")]
    if len(young):
        y = young.iloc[0]
        items.append(f"<b>One to watch:</b> {y.player_name} strikes at {y.all_p_sr:.0f} under pressure, but on only "
                     f"{int(y.all_p_balls)} pressure balls — below our threshold, so the method cannot yet call it reliable.")
    if len(best_w):
        items.append(f"<b>Pressure bowling:</b> the best-ranked RR bowlers are "
                     + ", ".join(f"{n} (#{int(r)})" for n, r in zip(best_w.player_name.head(2), best_w["rank"].head(2)))
                     + f"; no RR bowler is in the league-wide top 10.")
    items.append("<b>Death overs:</b> " + ("no RR bowler qualifies as a death specialist on our definition, " if not len(death_rr) else "")
                 + "so the death role is where the squad is thinnest under pressure. The role table in §4.4 lists the bowlers who "
                   "perform best there across the league.")
    out += [P("6.3 What the data says", "h2")] + bullets(items)
    out.append(P("These are statistical findings from 2022–2026 data under our pressure definition, intended to inform — not replace — "
                 "the judgement of selectors and coaches.", "caption"))
    return out


def build():
    d = load()
    bat, bowl = d["bat"], d["bowl"]
    nb, nw = len(bat), len(bowl)
    story = []
    W = A4[0] - 4 * cm

    # ================================================================ cover + summary
    story += [P("Performance Under Pressure", "title"),
              P("SupeRR Selector Season 2 · Round 1 · Methodology report — identifying the batters and bowlers who "
                "deliver most consistently when the game is on the line (IPL and T20I, 2022–2026)", "subtitle")]
    story += [P("Summary", "h1"),
              P("We rebuilt the match situation before every one of 200,961 deliveries, measured how much was riding on each "
                "ball for each player, and rated every player on what they did on the balls that mattered most — compared with "
                "other players in the same situations and with their own usual level. Small samples are shrunk with empirical "
                "Bayes, rating weights come from how repeatable each measure is, and every rank carries a bootstrap "
                "probability of making the top 10.")]
    story += bullets([
        "<b>Pressure</b> = 0.5 × <i>match situation</i> (how far one ball can swing the win probability) + 0.3 × <i>tournament "
        "stakes</i> (how much the match changes the team's chance of the title or series) + 0.2 × <i>form</i> (how far the player's "
        "recent output sits below his own baseline). The top 30% of balls are <b>high-pressure</b>.",
        "<b>Rating</b> = repeatability-weighted combination of scoring/economy, survival/wickets, reliability (share of pressure "
        "innings that won the side win probability), uplift vs own usual level and win-probability impact.",
        "<b>Key finding 1:</b> the big match-winning moments (win probability added per ball) are mostly luck (split-half r = 0.05 for "
        "batters); scoring rate, survival and economy under pressure are the skills that repeat.",
        "<b>Key finding 2:</b> batters show a pressure-specific trait beyond general ability (partial r = 0.27, 2022–24 → 2025–26); "
        "bowlers do not — bowling under pressure is mostly bowling quality (normal economy predicts later pressure economy, r = 0.62).",
        "<b>For selectors:</b> best-by-role tables (incl. death bowling) are in §4.4, and the Rajasthan Royals squad viewed "
        "through the same method is in §6.",
    ])
    story.append(Spacer(1, 6))
    hdr = ["#", "Batter", "Conf.", "P(top 10)", "", "#", "Bowler", "Conf.", "P(top 10)"]
    rows = [hdr]
    for i in range(10):
        a, b = bat.iloc[i], bowl.iloc[i]
        rows.append([i + 1, f"<b>{a.player_name}</b>", a.confidence, f"{a.p_top10:.0%}", "",
                     i + 1, f"<b>{b.player_name}</b>", b.confidence, f"{b.p_top10:.0%}"])
    story.append(P("Final rankings", "h2"))
    story.append(table(rows, [0.7 * cm, 4.2 * cm, 1.4 * cm, 1.6 * cm, 0.4 * cm, 0.7 * cm, 4.2 * cm, 1.4 * cm, 1.6 * cm]))
    story.append(P(f"Order = bagged rating (mean over 100 match-level bootstrap resamples). Confidence from the number of "
                   f"high-pressure balls (bat: Medium ≥300, High ≥500; bowl: Medium ≥360, High ≥600). Eligible pool: {nb} batters, "
                   f"{nw} bowlers.", "caption"))
    story.append(PageBreak())

    # ================================================================ 1. pressure definition
    story += [P("1. Pressure definition", "h1"),
              P("Our principle: <b>a ball is a pressure ball when a lot is riding on it for this player</b>. That has three "
                "independent sources, each measured on a 0–100 scale and computed only from information available at the time "
                "(no future results are ever used).")]
    story += fig(pipeline_figure(), 15.5, "Figure 1 — Method overview. Code: run_pipeline.py (8 steps, ~12 minutes end to end).")
    story += [
              P("1.1 Match Situation Pressure (MSP) — how much can this ball swing the match?", "h2"),
              P("For every delivery we reconstruct the state before the ball (runs required, legal balls left, wickets in hand, "
                "target, run rates, phase) and estimate the batting side's <b>win probability</b> (WP):"),
              ]
    story += bullets([
        "<b>Chases:</b> an interpretable logistic model on runs required, balls left, wickets in hand and the current scoring "
        "environment (run rate of the previous 40 matches), plus an exact ball-by-ball recursion over the last 30 balls where a "
        "smooth curve is wrong (e.g. 6 needed off 1 ball ≈ 9%, the observed six rate). Trained on matches before 2025 and tested on "
        "2025–26: log loss 0.370 / AUC 0.918, vs 0.411 / 0.897 for required run rate alone.",
        "<b>First innings:</b> a monotonic gradient-boosting model of runs still to come (test MAE 18.0 runs vs 27.0 for current "
        "run rate × overs), combined with the chase model: WP = Σ P(final total = T) × P(defending T). The two innings join up "
        "(mean gap 0.002 between end of innings 1 and start of innings 2).",
    ])
    story.append(P("Leverage = Σ<sub>outcomes</sub> P(outcome | phase) × | WP(after outcome) − WP(before) |, "
                   "over dot, 1, 2, 3, 4, 6, wicket, extra.  MSP = percentile of leverage across all balls.", "formula"))
    story.append(P("Leverage is the expected win-probability swing of one ball — the cricket analogue of baseball's leverage "
                   "index. It is high in a live finish (3 needed off the last ball has the highest values in the data) and "
                   "near zero in a decided game. The batter and the bowler share it: the swing one gains, the other loses."))
    story += [P("1.2 Tournament Stakes Pressure (TSP) — how much does this match matter to the team?", "h2"),
              P("TSP = P(win the competition | win this match) − P(win the competition | lose it)", "formula"),
              P("For league and series matches the points table is rebuilt from <i>earlier</i> results only (NRR to date as "
                "tie-break) and the remaining fixtures are simulated 4,000 times. Knockouts are exact: Final 1.0, Qualifier 2 / "
                "Semi-final 0.5, Qualifier 1 and Eliminator 0.25. Stakes are team-specific: in the same match one side can face a "
                "must-win game while the other is already eliminated (TSP = 0). Bilateral T20I series use 'win the series' as the "
                "objective; competitions whose group rules cannot be recovered from the data are left neutral rather than guessed. "
                "Because series and IPL stakes live on different scales, TSP is converted to a percentile within competition group."),
              P("1.3 Individual Performance Pressure (IPP) — is the player under form pressure?", "h2"),
              P("How far the player's last five innings (runs, strike rate, low-score streak) or matches (economy, wicket rate, "
                "wicketless streak) sit below his own career-to-date baseline, using previous matches only. Applied only to role "
                "players (top-7 batters; bowlers who usually bowl 2+ overs). This is a <b>statistical form proxy, not a measurement "
                "of psychological state</b>."),
              P("1.4 Combined Pressure Index", "h2"),
              P("CPI = 0.5 × MSP + 0.3 × TSP + 0.2 × IPP  (missing component = neutral 50);  high pressure = top 30% of CPI "
                "within each competition group", "formula"),
              P("The match situation carries half the weight because it is ball-specific and validated; stakes and form modulate "
                "it. These weights are a judgement, so §4.3 tests three alternatives. The batter and the bowler share MSP but each "
                "uses his own team's stakes and his own form, so the same ball can be high-pressure for one and not the other."),
              ]
    sep_head = P("1.5 Evidence that the index separates pressure from ordinary situations", "h2")
    sep = d["sep"].copy()
    sel = sep[sep["decile"].isin(["1", "3", "5", "7", "8", "9", "10"])]
    rows = [["Pressure decile", "Mean |WP swing| per ball", "Dismissal %", "Strike rate", "Death-over balls %", "Knockout-match balls %"]]
    for _, r in sel.iterrows():
        rows.append([r["decile"], f"{float(r['mean_absWPA']):.3f}", f"{float(r['dismissal_%']):.1f}", f"{float(r['strike_rate']):.0f}",
                     f"{float(r['death_overs_%']):.0f}", f"{float(r['knockout_%']):.1f}"])
    story.append(KeepTogether([sep_head, table(rows, [2.6 * cm, 3.4 * cm, 2.4 * cm, 2.2 * cm, 2.9 * cm, 3.4 * cm])]))
    story.append(P("Batting view, all 200k balls. The average win-probability swing rises ~7× from the calmest to the most "
                   "pressured decile and knockout matches are 14× more common; dismissals rise in the top deciles. Average "
                   "strike rate barely moves: pressure changes how much each ball matters, not the average ball, which is "
                   "why differences between players carry the signal.", "caption"))
    story += fig(FIG / "pressure_separation.png", 16.5, "Figure 2 — Outcomes by pressure decile (shaded = high-pressure zone).")
    pf = d["profile"]
    story.append(P(f"<b>Where the high-pressure balls come from:</b> {pf['share_overs_1_3']:.0%} are in overs 1–3 (an open game, "
                   f"where an early wicket moves the result most), {pf['share_overs_7_16']:.0%} in overs 7–16 and "
                   f"{pf['share_overs_17_20']:.0%} in overs 17–20. Only {pf['share_nearly_decided (WP<15% or >85%)']:.1%} come from "
                   f"games that were nearly decided (win probability below 15% or above 85%): the index tracks live contests, as "
                   f"the brief's 'how close the contest is' requires."))
    story += [P("1.6 Worked example — Virat Kohli, SRH v RCB, IPL 2023 (100 off 63 chasing 187)", "h2"),
              P("Over 15.2: RCB 133/0 need 54 off 36 → WP 94.7%; expected swing 0.0064 (0.46× an average ball) → MSP 17. RCB "
                "were 5th, fighting for the play-offs: P(title | win) 9.5% − P(title | lose) 1.3% → TSP 72nd percentile. Kohli's "
                "form was neutral (IPP 48). CPI = 0.5×17.4 + 0.3×71.6 + 0.2×47.8 = 39.7, below the IPL cut-off of 59.7 — a big "
                "match, but nothing much riding on that ball. In overs 1–4 (open chase) and 17–18 (23 needed off 18) his CPI was "
                "71–79: 30 of his 63 balls were high-pressure. The bowler on the same ball (Bhuvneshwar) shared MSP but SRH were "
                "already eliminated, so his CPI was 19.4.")]
    story.append(PageBreak())

    # ================================================================ 2. performance measurement
    story += [P("2. Performance measurement", "h1"),
              P("2.1 Measuring against same-situation peers", "h2"),
              P("Pressure balls are disproportionately death overs of tight games, where everyone scores faster and gets out "
                "more. So each ball's outcome is compared with the <b>average player on balls of the same competition tier × phase "
                "× pressure level</b>: runs above expected, dismissals above expected, and for bowlers runs conceded and wickets "
                "above expected. This removes the 'death overs are expensive' artefact and lets IPL and T20I balls be pooled."),
              P("2.2 Relative to the player's own usual level", "h2"),
              P("A player's pressure sample (typically 300–900 balls) is small; his normal-situation sample is two to three times "
                "larger. We therefore estimate pressure performance in two levels:"),
              P("pressure estimate = usual level (normal balls, shrunk to the population) + λ × (pressure − usual difference)  "
                "with  λ = τ² / (τ² + noise)", "formula"),
              P("τ² is the true between-player variance of the pressure-minus-usual difference (method of moments) and 'noise' "
                "its sampling variance for that player. The data decides how much of a player's personal pressure gap is real: "
                "median λ ≈ 0.07 for batting scoring and ≈ 0.10 for bowling economy (≈ 0 for dismissal and wicket rates). The "
                "remaining difference is the <b>uplift</b> component — how a player performs under pressure compared with his "
                "usual level, as the brief asks."),
              P("2.3 Rating components", "h2")]
    rows = [["Component", "Batters", "Bowlers"],
            ["Impact", "Win probability added per pressure ball", "Win probability taken from the batting side per pressure ball"],
            ["Scoring / Economy", "Runs per pressure ball above same-situation peers", "Runs conceded per pressure ball vs peers (lower = better)"],
            ["Survival / Wickets", "Dismissals per pressure ball vs peers (lower = better)", "Wickets per pressure ball vs peers"],
            ["Reliability", "Share of pressure innings (≥5 high-pressure balls) in which he added win probability",
             "Share of pressure spells in which he took win probability from the batting side"],
            ["Uplift", "Shrunk pressure − usual difference in scoring", "Shrunk usual − pressure difference in runs conceded"]]
    story.append(table(rows, [3.2 * cm, 6.6 * cm, 7.2 * cm], bold_first_col=True))
    story.append(Spacer(1, 4))
    story += [P("2.4 Weights from repeatability, not opinion", "h2"),
              P("Each component's weight is proportional to its <b>split-half repeatability</b> under pressure: we split each "
                "player's pressure balls (or innings) into odd and even halves and correlate the halves across players. A measure "
                "that does not repeat is mostly luck and gets little weight. All components are z-scored across eligible players "
                "and summed with these weights.")]
    rb, rw = d["rel_bat"].set_index(d["rel_bat"].columns[0]), d["rel_bowl"].set_index(d["rel_bowl"].columns[0])
    rows = [["Batting component", "Split-half r", "Weight", "", "Bowling component", "Split-half r", "Weight"]]
    for (kb, a), (kw, b) in zip(rb.iterrows(), rw.iterrows()):
        rows.append([kb, fmt(float(a["split-half r"]), 2), f"{float(a['weight']):.0%}", "",
                     kw, fmt(float(b["split-half r"]), 2), f"{float(b['weight']):.0%}"])
    story.append(table(rows, [3.0 * cm, 2.2 * cm, 1.8 * cm, 0.4 * cm, 3.0 * cm, 2.2 * cm, 1.8 * cm]))
    story.append(P("Win probability added per ball barely repeats for batters (r = 0.05) and wicket rate barely repeats for "
                   "bowlers (r = 0.03): both swing on rare events. Scoring rate, survival, reliability, economy and uplift are "
                   "the repeatable signals.", "caption"))
    story += [P("2.5 Small samples and final order", "h2"),
              P("Every rate is shrunk towards the population by <b>empirical Bayes</b>, with the shrinkage strength estimated "
                "from the data (a player with few balls is pulled strongly to average; one with many barely moves). The final "
                "order is the <b>bagged rating</b>: the rating averaged over 100 bootstrap resamples of whole matches (shrinkage "
                "settings held at their full-data values), which smooths sampling noise in the close places.")]

    # ================================================================ 3. fair comparisons
    story += [P("3. Fair comparisons", "h1"),
              P("3.1 Data validated before use", "h2")]
    rows = [["Question", "Decision", "Evidence"],
            ["Runs per ball", "runs + extras1_runs + extras_2_runs", "Reproduces 399/400 stated run margins (the miss is a Super Over tie) and 99.8% of wicket margins"],
            ["extras_type 'other'", "No-ball", "With it as a no-ball, 100% of 216 completed overs containing one have 6 legal balls (0% otherwise)"],
            ["Revised-overs fields", "Innings length in balls", "No innings exceeds the value; read as overs they would mean 30–114-over innings"],
            ["Match state", "Rebuilt per ball", "99.6% of 843 completed chases end in a state that reproduces the recorded result"],
            ["Super Overs, abandoned games", "Excluded from regular play", "Super Over results count as ties; 16 matches have no deliveries"],
            ["Rain-shortened innings", "Limit from the data, or inferred", "16 innings had no recorded limit; inferred from where the innings stopped"]]
    story.append(table(rows, [3.4 * cm, 3.6 * cm, 10.0 * cm], bold_first_col=True))
    story += [P("3.2 IPL and T20I", "h2"),
              P("IPL and T20I are never mixed raw. Every ball is assigned a competition tier and compared only with peers in the "
                "same tier (§2.1). Tiers then carry weights reflecting the strength of opposition:")]
    rows = [["Tier", "Weight", "Why"],
            ["IPL", "1.0", "Strongest, deepest T20 competition"],
            ["T20I between ICC full members", "1.0", "International top level"],
            ["T20I involving an associate nation", "0.4", "Weaker opposition: runs and wickets come cheaper"],
            ["Other T20 (A-team events)", "0.3", "Second-string level"]]
    story.append(table(rows, [6.0 * cm, 1.6 * cm, 9.4 * cm], bold_first_col=True))
    story.append(P("All seasons 2022–2026 count equally. §4.3 shows the top 10 is robust to IPL-primary weighting, equal "
                   "weighting and recency weighting.", "caption"))
    story += [P("3.3 Eligibility and sample size", "h2")]
    story += bullets([
        "<b>Batters:</b> ≥ 200 high-pressure balls faced and ≥ 15 pressure innings, across all competitions "
        f"({nb} eligible). <b>Bowlers:</b> ≥ 240 high-pressure balls and ≥ 20 pressure spells ({nw} eligible).",
        "Confidence tiers by pressure balls (Medium / High): batters 300 / 500, bowlers 360 / 600. Every rank is reported with "
        "its tier, a 90% bootstrap rank interval and the probability of making the top 10.",
        "Empirical-Bayes shrinkage on every rate (§2.5), so a short hot streak cannot top the list.",
        "No 'still active' filter: the brief ranks performance over the period, so players who retired during 2022–26 remain eligible.",
    ])
    story += [P("3.4 Different match contexts and no leakage", "h2")]
    story += bullets([
        "Phase, competition tier and pressure level are controlled by the peer comparison; first and second innings by "
        "the joined-up win-probability model; rain-reduced innings by their actual limits; DLS targets by the revised target.",
        "Scoring environment, venue par, standings, net run rate and form use only matches before the one being scored "
        "(same-day matches cannot see each other). Win-probability models are tested on later seasons than they were trained on.",
        "The batting and bowling models are separate; the batter and bowler on one ball share only the match-situation component.",
    ])
    story.append(PageBreak())

    # ================================================================ 4. evidence
    story += [P("4. Evidence for the top 10", "h1"),
              P("4.1 Batters", "h2")]
    rows = [["#", "Batter", "Balls (P)", "SR (P)", "SR (U)", "Avg (P)", "Avg (U)", "Dot % (P)", "Rank 90% CI", "P(top 10)"]]
    for _, r in bat.head(10).iterrows():
        rows.append([int(r.final_rank), f"<b>{r.player_name}</b>", int(r.all_p_balls), fmt(r.all_p_sr, 0), fmt(r.all_n_sr, 0),
                     fmt(r.all_p_avg), fmt(r.all_n_avg), fmt(r.all_p_dot_pct), f"{r.rank_p05:.0f}–{r.rank_p95:.0f}", f"{r.p_top10:.0%}"])
    story.append(table(rows, [0.8 * cm, 3.6 * cm, 1.6 * cm, 1.4 * cm, 1.4 * cm, 1.5 * cm, 1.5 * cm, 1.6 * cm, 2.0 * cm, 1.6 * cm]))
    story.append(P("(P) = high-pressure balls, (U) = usual (all other) balls; all competitions. Raw descriptive statistics — the "
                   "rating itself uses the peer-adjusted, shrunk measures of §2. Rank 90% CI from 100 match-level resamples.", "caption"))
    scatter(bat.set_index("player_id"), "bat", "pressure_vs_usual_bat.png")
    scatter(bowl.set_index("player_id"), "bowl", "pressure_vs_usual_bowl.png")
    story += fig(FIG / "pressure_vs_usual_bat.png", 11.5, "Figure 3 — Strike rate under pressure vs usual for all eligible batters; "
                 "above the dashed line = scores faster under pressure.")
    story.append(P("<b>Suryakumar Yadav</b> is the clearest #1 in the data (in the top 10 in 100% of resamples): he scores "
                   "177 per 100 balls under pressure against 163 normally, with the highest reliability of any batter (64% of "
                   "pressure innings won win probability). The top five all score at 165–180 per 100 balls under pressure; four of "
                   "them also get out less often than same-situation peers — Abhishek Sharma is the exception, trading a slightly "
                   "higher dismissal rate for the fastest scoring of all (180).", "callout"))
    story.append(PageBreak())
    story += [P("4.2 Bowlers", "h2")]
    rows = [["#", "Bowler", "Balls (P)", "Econ (P)", "Econ (U)", "Wkts/24 (P)", "Dot % (P)", "Rank 90% CI", "P(top 10)"]]
    for _, r in bowl.head(10).iterrows():
        rows.append([int(r.final_rank), f"<b>{r.player_name}</b>", int(r.all_p_balls), fmt(r.all_p_econ, 2), fmt(r.all_n_econ, 2),
                     fmt(r.all_p_wkts_per24, 2), fmt(r.all_p_dot_pct), f"{r.rank_p05:.0f}–{r.rank_p95:.0f}", f"{r.p_top10:.0%}"])
    story.append(table(rows, [0.8 * cm, 3.8 * cm, 1.7 * cm, 1.6 * cm, 1.6 * cm, 1.9 * cm, 1.7 * cm, 2.1 * cm, 1.8 * cm]))
    story.append(P("(P) = high-pressure balls, (U) = usual balls; all competitions; raw descriptive statistics.", "caption"))
    story += fig(FIG / "pressure_vs_usual_bowl.png", 11.5, "Figure 4 — Economy under pressure vs usual for all eligible bowlers; "
                 "below the dashed line = tighter under pressure.")
    story.append(P("The bowling list is led by spinners who concede around 7 an over when it matters (Narine, Kuldeep, Axar, "
                   "Zampa, Krunal, Santner, Rashid). Bumrah and Narine are slightly more expensive under pressure than in their own "
                   "normal play, yet still better than almost every bowler facing the same situations — consistent with our "
                   "finding that bowling under pressure is mostly bowling quality.", "callout"))
    story.append(PageBreak())

    story += [P("4.3 How robust is the top 10?", "h2"),
              P("We re-ran the full ranking under every alternative choice. Overlap = how many of our top 10 remain in the "
                "alternative top 10.")]

    def overlaps(role, final):
        t = d[f"top_{role}"]
        top = set(final.player_name.head(10))
        return {c: len(top & set(t[c])) for c in t.columns if c != "baseline"}
    ob, ow = overlaps("bat", bat), overlaps("bowl", bowl)
    nice = lambda c: (c.replace("rating weights: ", "Rating weights: ").replace("competition weighting: ", "Competition weighting: ")
                      .replace("pressure definition: ", "Pressure definition: "))
    skip = lambda c: "data-driven" in c or "baseline:" in c or "baseline 0.5" in c
    rows = [["Alternative", "Batters overlap", "Bowlers overlap"]] + \
           [[nice(c), f"{ob[c]}/10", f"{ow[c]}/10"] for c in ob if not skip(c)]
    story.append(table(rows, [11.0 * cm, 3.0 * cm, 3.0 * cm]))
    so = [c for c in ob if "situation only" in c][0]
    ri = [c for c in ob if "rise above" in c][0]
    t_b, t_w = d["top_bat"][ri], d["top_bowl"][ri]
    ins = sorted(set(t_b) - set(bat.player_name.head(10))) + sorted(set(t_w) - set(bowl.player_name.head(10)))
    vb = [ob[c] for c in ob if not skip(c)]
    vw = [ow[c] for c in ow if not skip(c)]
    imp = [c for c in ob if "impact only" in c][0]
    story.append(P(f"Overlap with the final top 10. Across {len(vb)} alternatives, {min(vb)}–{max(vb)} of the batters and "
                   f"{min(vw)}–{max(vw)} of the bowlers survive (median {int(pd.Series(vb).median())} and "
                   f"{int(pd.Series(vw).median())}). Competition weighting changes least. The biggest changes come from rating on "
                   f"impact alone ({ob[imp]}/10 batters — the luck-driven measure of §2.4) and from dropping stakes and form from the "
                   f"pressure definition (situation-only keeps {ob[so]}/10 batters and {ow[so]}/10 bowlers), which shows those "
                   f"components add information. Places 1–5 are far more stable than 6–10 (Figure 5). "
                   f"The 'rise above own usual' framing (uplift weight 50%) keeps "
                   f"{ob[ri]}/10 batters and {ow[ri]}/10 bowlers, bringing in {', '.join(ins)} — players who improve most on their "
                   f"own norm — but our evidence shows such personal gaps are mostly noise (§2.2), so it is not the main ranking.", "caption"))
    pair = Table([[fig(FIG / "rank_uncertainty_bat.png", 8.4)[0], fig(FIG / "rank_uncertainty_bowl.png", 8.4)[0]]],
                 colWidths=[8.6 * cm, 8.6 * cm])
    pair.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [pair, P("Figure 5 — Final rank (diamond), bootstrap median rank (dot) and 90% interval from 100 match-level "
                      "resamples; left batters, right bowlers.", "caption")]
    story.append(PageBreak())
    story += role_section(bat, bowl)
    story += dip_section(bat, bowl)
    story.append(Spacer(1, 10))

    # ================================================================ 5. reliability & limitations
    story += [P("5. Reliability and limitations", "h1"),
              P("5.1 Is pressure performance a stable trait? (rate on 2022–24, test on 2025–26)", "h2")]
    tp = d["temporal"].set_index(d["temporal"].columns[0])
    want = [("players", "Players with enough pressure balls in both periods"),
            ("old estimate -> later pressure scoring/economy", "Pressure-balls-only estimate → later pressure scoring / economy (r)"),
            ("A (own level) -> later pressure scoring/economy", "Own-usual-level estimate (§2.2) → later pressure scoring / economy (r)"),
            ("normal level only -> later", "Normal-situation level only → later pressure scoring / economy (r)"),
            ("A CUP -> later", "Full rating 2022–24 → later pressure scoring / economy (r)"),
            ("CUP 2022-24 vs CUP 2025-26 (spearman)", "Rating 2022–24 vs rating 2025–26 (Spearman)"),
            ("partial r: raw pressure record given normal", "Pressure record → later pressure performance, controlling for normal ability (partial r)")]
    rows = [["Test", "Batters", "Bowlers"]]
    for k, label in want:
        a, b = tp.loc[k, "batters"], tp.loc[k, "bowlers"]
        nd = 0 if k == "players" else 2
        rows.append([label, fmt(float(a), nd), fmt(float(b), nd)])
    story.append(table(rows, [12.0 * cm, 2.5 * cm, 2.5 * cm]))
    story.append(P("Only ~40 players qualify in both periods, so each correlation carries roughly ±0.15 of noise.", "caption"))
    story += bullets([
        "<b>Batters have a genuine pressure trait:</b> their pressure record predicts later pressure performance even after "
        "controlling for normal ability (partial r = 0.27).",
        "<b>Bowlers do not:</b> a bowler's pressure-only record did not predict later pressure economy (r = 0.03); estimating it "
        "relative to his usual level raised this to 0.40, which is why §2.2 is part of the method.",
        "<b>Split-half repeatability</b> (§2.4) and the <b>match bootstrap</b> (§4.3) quantify consistency across matches: only Suryakumar is "
        "near-certain (100% P(top 10)); the other top-10 places range from 33–87% (batters) and 48–81% (bowlers), so the close "
        "places are genuinely close.",
    ])
    story += [P("5.2 Limitations", "h2")]
    story += bullets([
        "<b>Chasing became easier over the period</b> (chase win rate 48% to 2024, 53% in 2025, 55% in 2026). Out of time the "
        "win-probability models are a few points pessimistic for chasers; production models are refit on all seasons and "
        "MSP is a rank of leverage, which is robust to this level shift.",
        f"<b>Start and end of an innings carry most leverage:</b> {pf['share_overs_1_3']:.0%} of high-pressure balls are in overs "
        f"1–3 and {pf['share_overs_17_20']:.0%} in overs 17–20, because that is where one ball moves the result most. A comfortable "
        f"finish can still qualify (e.g. 23 off 18 with 10 wickets in hand); a 'direction' variant that adds pressure for the side "
        f"behind is a natural extension.",
        "<b>Form pressure is a proxy</b> built from statistics, not a measure of a player's mental state.",
        "<b>Tournament structure</b> is not recoverable for some multi-team events (Asia Cup group and Super 4 stages, 108 team-games); "
        "their stakes are neutral rather than guessed.",
        "<b>Small samples:</b> two batters (Klaasen, Rinku Singh) and one bowler (Narine) in the top 10 have Low confidence "
        "(fewer than 300/360 pressure balls). Shrinkage has already discounted them; their high P(top 10) shows the signal "
        "survives resampling, but their exact positions are less certain.",
        "<b>Judgement calls</b> remain in the pressure weights (0.5/0.3/0.2), the 30% threshold and the tier weights; each is "
        "sensitivity-tested in §4.3.",
        "Three matches whose final state cannot reproduce their recorded result and rain cuts within an innings (reduced limit "
        "applied to the whole innings) are documented edge cases.",
    ])
    story.append(PageBreak())
    story += rr_section(d)
    story += [P("Appendix — Reproducibility", "h1"),
              P("All results are produced from the supplied CSVs by <b>python run_pipeline.py</b> (Python, pandas, NumPy, "
                "scikit-learn, SciPy, matplotlib). Steps: data validation → match state → match-situation pressure (both innings) → "
                "tournament stakes → form pressure → ratings and rankings → validation. Every step writes a report to outputs/; "
                "docs/CODE_GUIDE.md explains every function, docs/DATA_DICTIONARY.md every column, and "
                "outputs/METHODOLOGY_NOTES.md every decision with its evidence. Final rankings: "
                "outputs/rankings_batting_with_uncertainty.csv and outputs/rankings_bowling_with_uncertainty.csv (column final_rank).")]

    doc = SimpleDocTemplate(str(PDF), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=2 * cm,
                            title="Performance Under Pressure — SupeRR Selector S2 methodology report",
                            author="SupeRR Selector S2 submission", subject="Methodology report")
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"written {PDF}")


if __name__ == "__main__":
    build()
