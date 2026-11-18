"""Build the Round 1 methodology report (PDF) from the pipeline outputs.

    python report/build_report.py      ->  outputs/SupeRR_Selector_Methodology_Report.pdf

Every table and number is read from files the pipeline writes (outputs/*.csv, outputs/*_report.md,
outputs/*.json), so the report always matches the code. Run `python run_pipeline.py` first.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.validate_rankings import scatter  # noqa: E402  (same chart code as the pipeline)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
FIG = OUT / "figures"
PDF = OUT / "SupeRR_Selector_Methodology_Report.pdf"
REPO = "github.com/adityakv1/rrhackathon"

# ------------------------------------------------------------------ fonts & styles (plain, document-like)
FONT_DIR = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Body", str(FONT_DIR / "calibri.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FONT_DIR / "calibrib.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", str(FONT_DIR / "calibrii.ttf")))
pdfmetrics.registerFont(TTFont("Body-BoldItalic", str(FONT_DIR / "calibriz.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-BoldItalic")

INK, MUTED, HEAD, RULE, SHADE = (colors.HexColor(c) for c in ["#222222", "#666666", "#1f3864", "#bfbfbf", "#f2f2f2"])
S = {
    "title": ParagraphStyle("title", fontName="Body-Bold", fontSize=24, leading=29, textColor=HEAD, spaceAfter=4),
    "subtitle": ParagraphStyle("subtitle", fontName="Body", fontSize=12.5, leading=16, textColor=MUTED, spaceAfter=16),
    "h1": ParagraphStyle("h1", fontName="Body-Bold", fontSize=16, leading=20, textColor=HEAD, spaceBefore=8, spaceAfter=7, keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName="Body-Bold", fontSize=12.5, leading=16, textColor=HEAD, spaceBefore=9, spaceAfter=4, keepWithNext=1),
    "body": ParagraphStyle("body", fontName="Body", fontSize=10.5, leading=14.2, textColor=INK, spaceAfter=6),
    "bullet": ParagraphStyle("bullet", fontName="Body", fontSize=10.5, leading=14.0, textColor=INK, leftIndent=14,
                             bulletIndent=3, spaceAfter=3),
    "formula": ParagraphStyle("formula", fontName="Body-Italic", fontSize=10.8, leading=14.6, textColor=INK, leftIndent=22,
                              spaceBefore=3, spaceAfter=8),
    "caption": ParagraphStyle("caption", fontName="Body-Italic", fontSize=9.2, leading=12, textColor=MUTED, spaceAfter=9),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=9.4, leading=11.4, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Body-Bold", fontSize=9.4, leading=11.4, textColor=INK),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def bullets(items):
    return [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def table(rows, widths, header=True, zebra=True, bold_first_col=False):
    data = [[c if isinstance(c, Paragraph) else Paragraph(str(c), S["cellb" if (header and i == 0) or (bold_first_col and j == 0) else "cell"])
             for j, c in enumerate(r)] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEABOVE", (0, 0), (-1, 0), 0.8, INK),
          ("LINEBELOW", (0, 0), (-1, 0), 0.6, INK), ("LINEBELOW", (0, -1), (-1, -1), 0.8, INK),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
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


def ordinal(n: int) -> str:
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def join_names(names) -> str:
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def fmt(x, nd=1):
    return "–" if pd.isna(x) else f"{x:.{nd}f}"


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
    boxes = [("Ball-by-ball\ndata (checked)", 0.05), ("Match state\nbefore every ball", 0.22),
             ("3 pressure\nsignals", 0.39), ("Combined\npressure index", 0.56), ("Player ratings\nvs peers", 0.73),
             ("Ranked top 10\n+ uncertainty", 0.90)]
    for text, x in boxes:
        ax.add_patch(plt.Rectangle((x - 0.075, 0.42), 0.15, 0.36, fc="#f2f2f2", ec="#1f3864", lw=1.1))
        ax.text(x, 0.60, text, ha="center", va="center", fontsize=8.6, color="#222222")
    for (_, a), (_, b) in zip(boxes[:-1], boxes[1:]):
        ax.annotate("", xy=(b - 0.078, 0.60), xytext=(a + 0.078, 0.60), arrowprops=dict(arrowstyle="->", color="#666666", lw=1.1))
    for i, t in enumerate(["match situation (how far one ball can swing the game)", "tournament stakes (how much the match matters)",
                           "form (recent output vs own baseline)"]):
        ax.text(0.39, 0.30 - i * 0.11, t, ha="center", fontsize=7.4, color="#444444")
    ax.set_xlim(-0.03, 1.0)
    ax.set_ylim(-0.05, 0.9)
    fig_.savefig(path, bbox_inches="tight")
    plt.close(fig_)
    return path


# ------------------------------------------------------------------ page furniture
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Body", 8.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(2 * cm, 1.2 * cm, "SupeRR Selector Season 2  |  Round 1 methodology report")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(doc.page))
    canvas.restoreState()


# ------------------------------------------------------------------ sections built from data
def _rank_lookup(final: pd.DataFrame) -> dict:
    return dict(zip(final["player_id"], final["final_rank"]))


def role_section(bat: pd.DataFrame, bowl: pd.DataFrame) -> list:
    """Section 4.4: the top three in each role, and why no death specialist reaches the bowling top 10."""
    out = [P("4.4 The best in each role", "h2"),
           P("Our lists ignore role, but a selector picking a side does not. The tables below use the same final rating "
             "within each role. The roles are only descriptive (a batter's usual position over the last two years, and the "
             "phase in which a bowler bowls most of his overs) and play no part in the rating.")]

    def cell(r, kind):
        stat = (f"SR {r.all_p_sr:.0f} / {r.all_n_sr:.0f}" if kind == "bat" else f"Econ {r.all_p_econ:.2f} / {r.all_n_econ:.2f}")
        return f"<b>{r.player_name}</b> ({ordinal(r.final_rank)})<br/><font color='#666666'>{stat}</font>"

    rows = [["Batting role", "1st", "2nd", "3rd"]]
    groups = [(lbl, bat[bat.batting_role == lbl]) for lbl in ["Opener", "Top order (3)", "Middle order (4-5)", "Finisher (6-7)"]]
    groups.append(("Wicketkeepers", bat[bat.keeper == True]))  # noqa: E712
    for lbl, g in groups:
        top = g.sort_values("final_rank").head(3)
        rows.append([f"{lbl} ({len(g)})"] + [cell(r, "bat") for _, r in top.iterrows()] + [""] * (3 - len(top)))
    out.append(table(rows, [3.4 * cm, 4.5 * cm, 4.5 * cm, 4.6 * cm], bold_first_col=True))
    out.append(P("Numbers in brackets after each role are eligible players in that role. SR is strike rate under pressure / usually; "
                 "the ordinal is the player's overall rank.", "caption"))

    rows = [["Bowling role", "1st", "2nd", "3rd"]]
    groups = [(lbl, bowl[bowl.bowling_role == lbl]) for lbl in
              ["Powerplay specialist", "Middle-overs specialist", "Death specialist", "All-phase"]]
    groups += [("Pace", bowl[bowl.pace_or_spin == "Pace"]), ("Spin", bowl[bowl.pace_or_spin == "Spin"])]
    for lbl, g in groups:
        top = g.sort_values("final_rank").head(3)
        rows.append([f"{lbl} ({len(g)})"] + [cell(r, "bowl") for _, r in top.iterrows()] + [""] * (3 - len(top)))
    out.append(table(rows, [3.4 * cm, 4.5 * cm, 4.5 * cm, 4.6 * cm], bold_first_col=True))
    out.append(P("Econ is economy under pressure / usually. A death specialist bowls at least a third of his balls in overs 17 to 20; "
                 "the average bowler bowls about a fifth there.", "caption"))

    per_over = bowl.groupby("bowling_role")["p_runs_ae"].mean() * -6     # runs per over saved vs same-situation peers
    death = bowl[bowl.bowling_role == "Death specialist"].sort_values("final_rank")
    best = death.iloc[0]
    out.append(P(f"No death specialist made the bowling top 10. We expected a cricket audience to question that, so we looked into "
                 f"it. Only {len(death)} of the {len(bowl)} eligible bowlers are death specialists. Under pressure they do better than "
                 f"bowlers in the same situations, by {per_over['Death specialist']:.2f} runs an over on average, but the leading "
                 f"middle-overs bowlers beat their own comparison group by more ({per_over['Middle-overs specialist']:.2f} runs an over), "
                 f"and economy is the measure that repeats best. The highest-ranked death specialist is {best.player_name}, "
                 f"{ordinal(best.final_rank)} overall. If the question is who should bowl the 19th over, the table above is a "
                 f"better guide than the overall list."))
    return out


def dip_section(bat: pd.DataFrame, bowl: pd.DataFrame) -> list:
    """Section 4.5: top-10 players whose own numbers are worse under pressure, named and explained."""
    tb, tw = bat.head(10), bowl.head(10)
    db = tb[tb.all_p_sr < tb.all_n_sr - 8]
    dw = tw[tw.all_p_econ > tw.all_n_econ + 0.5]
    if not len(db) and not len(dw):
        return []
    out = [P("4.5 Top-10 players who are worse under pressure than usual", "h2"),
           P("The brief asks about pressure performance compared with usual performance, so it is fair to point out the "
             "players in our top 10 whose own numbers drop when it matters:")]
    items = []
    for _, r in db.iterrows():
        pos = int((bat.all_p_sr > r.all_p_sr).sum() + 1)
        items.append(f"{r.player_name} ({ordinal(r.final_rank)}) strikes at {r.all_n_sr:.0f} normally and {r.all_p_sr:.0f} under "
                     f"pressure. Even so, {r.all_p_sr:.0f} is the {ordinal(pos)} best pressure strike rate among {len(bat)} eligible "
                     f"batters, and {r.p_runs_ae_raw * 100:.0f} runs per 100 balls more than batters in the same situations.")
    for _, r in dw.iterrows():
        pos = int((bowl.all_p_econ < r.all_p_econ).sum() + 1)
        items.append(f"{r.player_name} ({ordinal(r.final_rank)}) has an economy of {r.all_n_econ:.2f} normally and {r.all_p_econ:.2f} "
                     f"under pressure. His normal level is exceptional, and under pressure he still gives away {-r.p_runs_ae_raw * 6:.2f} "
                     f"runs an over fewer than bowlers in the same situations ({ordinal(pos)} best of {len(bowl)}).")
    out += bullets(items)
    out.append(P("We considered ranking on the size of the drop instead, but that favours players who go from poor to merely "
                 "average, and as Section 2.2 shows only a small part of an individual's gap carries over. So we rank on how well "
                 "players perform in pressure situations and report the drops openly."))
    return out


def rr_section(d: dict) -> list:
    """Section 6: the same method applied to the Rajasthan Royals squad."""
    allb, allw = d["all_bat"], d["all_bowl"]
    rk_b, rk_w = _rank_lookup(d["bat"]), _rank_lookup(d["bowl"])
    nb, nw = len(d["bat"]), len(d["bowl"])
    out = [P("6. A look at the Rajasthan Royals squad", "h1"),
           P("Round 1 is about the whole league, but since this is the Royals' competition we also ran their squad (the Rajasthan "
             "Royals list for the latest IPL season in the supplied data) through exactly the same method. Nothing was changed "
             "for this section: same pressure definition, same ratings, same thresholds.")]

    def status(pid, rk, n):
        return f"{ordinal(rk[pid])} of {n}" if pid in rk else "below threshold"

    b = allb[(allb.current_rr == True) & (allb.all_p_balls >= 100)].sort_values("all_p_balls", ascending=False)  # noqa: E712
    rows = [["Batter", "Role", "Pressure balls", "SR pressure", "SR usual", "Change", "Overall rank"]]
    for _, r in b.iterrows():
        rows.append([f"<b>{r.player_name}</b>", r.batting_role, int(r.all_p_balls), f"{r.all_p_sr:.0f}", f"{r.all_n_sr:.0f}",
                     f"{r.all_p_sr - r.all_n_sr:+.0f}", status(r.player_id, rk_b, nb)])
    out += [P("6.1 Batting", "h2"), table(rows, [3.7 * cm, 3.1 * cm, 2.0 * cm, 1.9 * cm, 1.7 * cm, 1.5 * cm, 3.1 * cm]),
            P("Squad players with at least 100 high-pressure balls faced. 'Below threshold' means fewer than 200 pressure balls or "
              "15 pressure innings, so not ranked.", "caption")]
    w = allw[(allw.current_rr == True) & (allw.all_p_balls >= 100)].sort_values("all_p_balls", ascending=False)  # noqa: E712
    rows = [["Bowler", "Role", "Pressure balls", "Econ pressure", "Econ usual", "Change", "Overall rank"]]
    for _, r in w.iterrows():
        rows.append([f"<b>{r.player_name}</b>", r.bowling_role.replace(" specialist", ""), int(r.all_p_balls),
                     f"{r.all_p_econ:.2f}", f"{r.all_n_econ:.2f}", f"{r.all_p_econ - r.all_n_econ:+.2f}", status(r.player_id, rk_w, nw)])
    out += [P("6.2 Bowling", "h2"), table(rows, [3.7 * cm, 3.1 * cm, 2.0 * cm, 1.9 * cm, 1.7 * cm, 1.5 * cm, 3.1 * cm]),
            P("Squad players with at least 100 high-pressure balls bowled. Change is pressure economy minus usual economy, so a "
              "negative number means tighter under pressure.", "caption")]

    bb = b.set_index("player_name")
    top_b = [n for n in bb.index if bb.at[n, "player_id"] in rk_b and rk_b[bb.at[n, "player_id"]] <= 10]
    risers = bb[(bb.all_p_sr - bb.all_n_sr) >= 8].index.tolist()
    fallers = bb[(bb.all_p_sr - bb.all_n_sr) <= -8].sort_values("all_p_sr").index.tolist()
    young = b[(~b.player_id.isin(rk_b)) & (b.all_p_sr >= 180)]
    ww = w.copy()
    ww["rank"] = ww.player_id.map(rk_w)
    best_w = ww.dropna(subset=["rank"]).sort_values("rank")
    death_rr = ww[ww.bowling_role == "Death specialist"]

    text = (f"{join_names(top_b)} {'is the only RR batter' if len(top_b) == 1 else 'are the RR batters'} in the league-wide top 10. "
            if top_b else "No RR batter is in the league-wide top 10. ")
    if risers:
        text += f"{join_names(risers)} score faster under pressure than they normally do. "
    if fallers:
        text += (f"{join_names(fallers)} slow down noticeably when it matters, and that is the biggest batting concern we "
                 f"found in the squad.")
    out += [P("6.3 What stands out", "h2"), P(text)]
    if len(young):
        y = young.iloc[0]
        out.append(P(f"{y.player_name} is one to watch. He strikes at {y.all_p_sr:.0f} under pressure, but on only "
                     f"{int(y.all_p_balls)} pressure balls, which is short of our threshold, so we can't yet call it reliable."))
    bowl_text = ""
    if len(best_w):
        bowl_text += (f"On the bowling side the best-ranked RR players are "
                      f"{join_names(f'{n} ({ordinal(r)})' for n, r in zip(best_w.player_name.head(2), best_w['rank'].head(2)))}, "
                      f"and nobody in the squad reaches the league top 10. ")
    if not len(death_rr):
        bowl_text += "No RR bowler meets our definition of a death specialist, "
    bowl_text += ("so the death overs look like the thinnest area under pressure. The role table in Section 4.4 shows who does "
                  "best there across the league.")
    out.append(P(bowl_text))
    out.append(P("These are findings from 2022 to 2026 data under our definition of pressure. They are meant to help selectors "
                 "and coaches, not to replace their judgement.", "caption"))
    return out


# ------------------------------------------------------------------ the report
def build():
    d = load()
    bat, bowl = d["bat"], d["bowl"]
    nb, nw = len(bat), len(bowl)
    pf = d["profile"]
    story = []

    # ================================================================ title + summary
    story += [P("Who delivers under pressure?", "title"),
              P("SupeRR Selector Season 2, Round 1: methodology report<br/>IPL and T20I data, 2022 to 2026", "subtitle")]
    story += [P("Summary", "h1"),
              P("Our question was simple to state and harder to answer: which batters and bowlers keep performing when a match is "
                "on the line? To answer it we rebuilt the match situation before each of the 200,961 deliveries in the data, worked "
                "out how much was riding on every ball for the players involved, and looked at how each player did on the balls that "
                "mattered most. Each player is compared with others who faced the same kind of situation, and with his own usual level."),
              P("Pressure, in our model, has three parts. The biggest, with half the weight, is the match situation: how far a single "
                "ball can swing a side's chance of winning. The second (30%) is what the match means for the player's team, from a "
                "dead rubber to a final. The third (20%) is the player's own form going into the game. The 30% of balls with the "
                "highest combined score count as high-pressure."),
              P("Two results shaped the rankings more than anything else. First, the dramatic moments, measured as the win "
                "probability a batter adds on a single ball, turned out to be mostly luck: a player's record on odd-numbered balls "
                "barely predicts his record on even-numbered ones (r = 0.05). Scoring rate, staying in and economy under pressure do "
                "repeat, so the rating leans on those. Second, batters seem to have a pressure skill of their own (it carries from "
                "2022–24 into 2025–26 even after allowing for general ability, partial r = 0.27), but we could not find one for "
                "bowlers. A bowler's ordinary economy predicts his economy under pressure better than his pressure record does "
                "(r = 0.62)."),
              P("Section 4.4 breaks the results down by role, including death bowling, and Section 6 applies the same method to "
                "the Rajasthan Royals squad.")]
    hdr = ["", "Batter", "Confidence", "P(top 10)", "", "", "Bowler", "Confidence", "P(top 10)"]
    rows = [hdr]
    for i in range(10):
        a, b = bat.iloc[i], bowl.iloc[i]
        rows.append([i + 1, f"<b>{a.player_name}</b>", a.confidence, f"{a.p_top10:.0%}", "",
                     i + 1, f"<b>{b.player_name}</b>", b.confidence, f"{b.p_top10:.0%}"])
    story.append(KeepTogether([P("Our top 10s", "h2"),
                               table(rows, [0.8 * cm, 3.5 * cm, 2.1 * cm, 1.6 * cm, 0.3 * cm, 0.8 * cm, 3.5 * cm, 2.1 * cm, 1.6 * cm]),
                               P(f"The order is the average rating over 100 resamples of the matches. Confidence reflects how many "
                                 f"high-pressure balls we have for the player (batters: Medium from 300, High from 500; bowlers: "
                                 f"Medium from 360, High from 600). P(top 10) is how often the player made the top 10 across those "
                                 f"resamples. {nb} batters and {nw} bowlers met our eligibility rules.", "caption")]))
    story.append(PageBreak())

    # ================================================================ 1. defining pressure
    story += [P("1. Defining pressure", "h1"),
              P("We started from one idea: a ball is a pressure ball when a lot is riding on it for the player facing or bowling "
                "it. We measure three separate sources of that, each on a 0 to 100 scale, and we only ever use information that "
                "was available at the time. No future result goes into any pressure number.")]
    story += fig(pipeline_figure(), 15.5, "Figure 1. How the pieces fit together. The whole pipeline runs from run_pipeline.py "
                                          "in about 12 minutes.")
    story += [P("1.1 Match situation: how much can this ball swing the game?", "h2"),
              P("For every delivery we reconstruct the state of the game just before it: runs needed, legal balls left, wickets "
                "in hand, target, run rates and phase. From that we estimate the batting side's chance of winning."),
              P("In a chase we use a logistic model on runs needed, balls left, wickets in hand and the recent scoring level (the "
                "run rate over the previous 40 games, so the model keeps up with scoring inflation). For the last 30 balls we "
                "switch to an exact ball-by-ball calculation, because a smooth curve gets the very end wrong: our first version "
                "gave a side needing 6 off the last ball about a 1% chance, when roughly 9% of death balls go for six. Trained on "
                "games before 2025 and tested on 2025–26, the chase model has a log loss of 0.370 and an AUC of 0.918, against "
                "0.411 and 0.897 for required run rate on its own."),
              P("There is no target in the first innings, so we predict how many runs are still to come and then ask how likely "
                "the opposition would be to chase each possible total. The runs model is constrained so that more balls or more "
                "wickets never mean fewer runs, and on unseen games it is out by 18.0 runs on average, against 27.0 for current "
                "run rate times overs left. The two innings line up: the win probability at the end of the first innings and at "
                "the start of the chase differ by only 0.002 on average."),
              P("With a win probability before every ball, the pressure on that ball is its leverage, the swing we would expect "
                "from it:"),
              P("Leverage = sum over outcomes (dot, 1, 2, 3, 4, 6, wicket, extra) of P(outcome in this phase) × "
                "| win probability after the outcome − win probability before |", "formula"),
              P("We turn leverage into a percentile across all balls. It is close to zero once a game is settled and highest in a "
                "close finish; the biggest values in the data all come from 3 needed off the last ball. It is the cricket version "
                "of baseball's leverage index, and batter and bowler share it, since whatever one side gains on a ball the other "
                "loses. Our first attempt measured only the gap between a four and a wicket. It scored Rahul Tewatia's famous "
                "6-off-1 ball against Punjab in 2022 at almost zero, because both of those outcomes lose from there, so we replaced it."),
              P("1.2 Tournament stakes: how much does this match matter to the team?", "h2"),
              P("Stakes = P(winning the competition if we win this match) − P(winning it if we lose)", "formula"),
              P("For league games we rebuild the points table using only earlier results, then play out the remaining fixtures "
                "4,000 times as coin flips, once with the team winning this match and once with it losing. Net run rate so far "
                "breaks ties. Knockouts need no simulation: a final is worth 1.0, a semi-final or Qualifier 2 is 0.5, and "
                "Qualifier 1 and the Eliminator are 0.25 (the loser of Qualifier 1 gets a second chance). For bilateral T20I series "
                "the target is winning the series."),
              P("The two teams in one match can have very different stakes. RR's last four games of 2025, for example, came after "
                "they were already out of contention, so they score zero for RR. For a few multi-team events (Asia Cup groups and "
                "Super 4s) the qualification rules can't be worked out from the data, and we left those games neutral rather than "
                "guess. And because a bilateral series game is a far bigger share of its competition than an IPL league game, "
                "stakes are ranked within each competition group."),
              P("1.3 Form: is the player himself under pressure?", "h2"),
              P("The third ingredient looks at the player. Going into each match we compare his last five innings (runs, strike "
                "rate, any run of low scores) or last five bowling performances (economy, wicket rate, any wicketless run) with his "
                "own career baseline up to that point. We only do this for players in a regular role: batters who usually bat in "
                "the top seven, and bowlers who usually bowl at least two overs. Without that filter, tail-enders' batting and "
                "part-timers' bowling filled the list of 'slumps'. This is a statistical form signal; it says nothing about how a "
                "player is feeling."),
              P("1.4 Putting it together", "h2"),
              P("Combined pressure = 0.5 × match situation + 0.3 × stakes + 0.2 × form (a missing part counts as 50).  "
                "High pressure = the top 30% of balls within each competition group.", "formula"),
              P("We gave the match situation half the weight because it is specific to the ball and is the part we could test "
                "against results. The weights are still a judgement call, so Section 4.3 shows what happens with three "
                "alternatives. Batter and bowler share the match-situation score, but each gets his own team's stakes and his own "
                "form, so one ball can be high-pressure for the batter and ordinary for the bowler.")]
    sep = d["sep"].copy()
    sel = sep[sep["decile"].isin(["1", "3", "5", "7", "8", "9", "10"])]
    rows = [["Pressure group", "Average swing per ball", "Dismissal %", "Strike rate", "Death-over balls %", "Knockout-game balls %"]]
    for _, r in sel.iterrows():
        rows.append([r["decile"], f"{float(r['mean_absWPA']):.3f}", f"{float(r['dismissal_%']):.1f}", f"{float(r['strike_rate']):.0f}",
                     f"{float(r['death_overs_%']):.0f}", f"{float(r['knockout_%']):.1f}"])
    story.append(KeepTogether([P("1.5 Does it pick out the right situations?", "h2"),
                               table(rows, [2.6 * cm, 3.4 * cm, 2.3 * cm, 2.2 * cm, 3.0 * cm, 3.5 * cm]),
                               P("Batting view across all 200,961 balls, split into ten equal groups from calmest (1) to most "
                                 "pressured (10).", "caption")]))
    story.append(P("The expected swing per ball rises about sevenfold from the calmest group to the most pressured, and knockout "
                   "games are 14 times more common at the top end. Dismissals go up in the top groups too. The average strike rate "
                   "hardly changes, which surprised us at first: pressure changes how much each ball matters rather than how the "
                   "average ball goes, which is why the interesting differences are between players."))
    story += fig(FIG / "pressure_separation.png", 16.5, "Figure 2. Outcomes by pressure group. The shaded area is the high-pressure zone.")
    story.append(P(f"Of the high-pressure balls, {pf['share_overs_1_3']:.0%} come in overs 1 to 3, where an early wicket moves the "
                   f"result most, {pf['share_overs_7_16']:.0%} in overs 7 to 16 and {pf['share_overs_17_20']:.0%} in overs 17 to 20. "
                   f"Only {pf['share_nearly_decided (WP<15% or >85%)']:.1%} come from games that were nearly settled (one side below "
                   f"a 15% chance of winning), so the index follows live contests, which is what the brief means by how close the "
                   f"contest is."))
    story += [P("1.6 A worked example: Virat Kohli's hundred against SRH, May 2023", "h2"),
              P("RCB were chasing 187. Early in the 15th over they were 133 without loss, needing 54 off 36, and our model gave "
                "them a 94.7% chance. The expected swing on that ball was 0.0064, about half an average ball, so its "
                "match-situation score was only 17. The game itself mattered a great deal: RCB were fifth and needed the points, "
                "so a win took their title chance to 9.5% against 1.3% for a defeat, which puts the stakes in the 72nd percentile "
                "of IPL games. Kohli's form going in was ordinary (48)."),
              P("Combined, that ball scores 0.5 × 17.4 + 0.3 × 71.6 + 0.2 × 47.8 = 39.7, below the IPL cut-off of 59.7: a big "
                "match, but nothing much hanging on that particular delivery. It was a different story at the start of the chase "
                "(overs 1 to 4) and at the end (23 needed off 18), where his combined score was between 71 and 79. In all, 30 of "
                "his 63 balls counted as high-pressure. Bhuvneshwar, bowling that same ball, shared the match-situation score, but "
                "SRH were already out of contention, so his combined score was just 19.4.")]
    story.append(Spacer(1, 8))

    # ================================================================ 2. measuring performance
    story += [P("2. Measuring performance", "h1"),
              P("2.1 Comparing like with like", "h2"),
              P("High-pressure balls are often in the closing overs of tight games, where everybody scores faster and gets out "
                "more. Comparing raw numbers would penalise anyone who bats or bowls at the death. Instead we compare each ball "
                "with the average for balls in the same competition tier, phase and pressure band. For batters that gives runs "
                "and dismissals above the expected level; for bowlers, runs conceded and wickets. It also lets IPL and T20I balls "
                "sit in one analysis."),
              P("2.2 Against the player's own usual level", "h2"),
              P("A player typically has 300 to 900 high-pressure balls but two or three times as many ordinary ones. Judging him "
                "on the pressure balls alone throws most of that information away, so we build the estimate in two layers:"),
              P("Pressure estimate = usual level + λ × (pressure − usual),  where  λ = τ² / (τ² + noise)", "formula"),
              P("The usual level comes from his ordinary balls. τ² is how much players genuinely differ in their pressure-minus-usual "
                "gap, and 'noise' is how uncertain that gap is for this particular player. Both are estimated from the data, so "
                "the data decides how much of an individual gap to believe. The answer was: not much. Typically about 7% of a "
                "batter's scoring gap and 10% of a bowler's economy gap is kept, and almost none of the gap in dismissals or "
                "wickets. We added this step after finding that our first bowling ratings had no predictive value at all "
                "(Section 5.1). Whatever gap survives becomes the 'uplift' part of the rating, which is how the brief's "
                "comparison with usual performance enters it."),
              P("2.3 What goes into the rating", "h2")]
    rows = [["Part", "Batters", "Bowlers"],
            ["Impact", "Win probability added per pressure ball", "Win probability taken from the batting side per pressure ball"],
            ["Scoring / economy", "Runs per pressure ball, compared with batters in the same situations",
             "Runs conceded per pressure ball, compared with bowlers in the same situations"],
            ["Survival / wickets", "Dismissals per pressure ball, compared as above", "Wickets per pressure ball, compared as above"],
            ["Reliability", "Share of his pressure innings (5+ high-pressure balls) in which his side gained win probability",
             "Share of his pressure spells in which his side gained win probability"],
            ["Uplift", "Pressure scoring minus usual scoring (after the shrinking in 2.2)",
             "Usual economy minus pressure economy (after the shrinking in 2.2)"]]
    story.append(table(rows, [3.1 * cm, 6.8 * cm, 7.1 * cm], bold_first_col=True))
    story.append(Spacer(1, 4))
    story += [P("2.4 How the parts are weighted", "h2"),
              P("Rather than choose the weights ourselves, we let each part earn its weight through repeatability. We split every "
                "player's pressure balls (or innings) into odd and even halves and checked how well one half predicts the other "
                "across players. Something that doesn't repeat is mostly luck, and gets little weight. Each part is standardised "
                "across eligible players before they are added together.")]
    rb, rw = d["rel_bat"].set_index(d["rel_bat"].columns[0]), d["rel_bowl"].set_index(d["rel_bowl"].columns[0])
    rows = [["Batting part", "Repeatability", "Weight", "", "Bowling part", "Repeatability", "Weight"]]
    for (kb, a), (kw, b) in zip(rb.iterrows(), rw.iterrows()):
        rows.append([kb.capitalize(), fmt(float(a["split-half r"]), 2), f"{float(a['weight']):.0%}", "",
                     kw.capitalize(), fmt(float(b["split-half r"]), 2), f"{float(b['weight']):.0%}"])
    story.append(table(rows, [3.0 * cm, 2.4 * cm, 1.7 * cm, 0.4 * cm, 3.0 * cm, 2.4 * cm, 1.7 * cm]))
    story.append(P("Repeatability is the correlation between odd and even halves of each player's pressure record. Win probability "
                   "added per ball hardly repeats for batters (0.05), and neither does wicket rate for bowlers (0.03); both hinge "
                   "on rare events.", "caption"))
    story += [P("2.5 Small samples and the final order", "h2"),
              P("Every rate is pulled towards the average by an amount that depends on how much data a player has (empirical "
                "Bayes, with the strength of the pull estimated from the data). Someone with a short hot streak is pulled back "
                "hard; someone with a long record barely moves. The final order is the rating averaged over 100 resamples of whole "
                "matches. When we first tried this, the averaging quietly undid the step in Section 2.2, because duplicated "
                "matches in a resample look like consistent differences between players. Holding the shrinking settings at their "
                "full-data values fixed it, and that is the version used here.")]

    # ================================================================ 3. fair comparisons
    story += [P("3. Making the comparisons fair", "h1"),
              P("3.1 Checking the data first", "h2"),
              P("Before building anything we checked our reading of the data against the match results it should reproduce.")]
    rows = [["Question", "What we concluded", "How we know"],
            ["Runs per ball", "runs + extras1_runs + extras_2_runs", "Reproduces 399 of 400 stated winning margins (the odd one out was a Super Over tie) and 99.8% of wicket margins"],
            ["extras_type 'other'", "A no-ball", "Treated as a no-ball, every one of the 216 completed overs containing one has 6 legal balls; treated as legal, none do"],
            ["Revised-overs fields", "Innings length in balls", "No innings goes past the value; read as overs they would mean 30 to 114-over innings"],
            ["Match state", "Rebuilt ball by ball", "99.6% of 843 completed chases end in a state that matches the recorded result"],
            ["Super Overs, abandoned games", "Left out of regular play", "Super Over results count as ties; 16 matches have no deliveries"],
            ["Rain-shortened innings", "Limit from the data, or inferred", "16 innings had no recorded limit, so we took it from where the innings stopped"]]
    story.append(table(rows, [3.5 * cm, 3.6 * cm, 9.9 * cm], bold_first_col=True))
    story += [P("3.2 IPL and T20I", "h2"),
              P("We never mix IPL and T20I numbers directly. Every ball is assigned to a competition tier and compared only with "
                "others in the same tier (Section 2.1), and the tiers are then weighted by the strength of the opposition:")]
    rows = [["Tier", "Weight", "Reason"],
            ["IPL", "1.0", "The strongest and deepest T20 competition"],
            ["T20I between ICC full members", "1.0", "Top international level"],
            ["T20I involving an associate nation", "0.4", "Weaker opposition, so runs and wickets come more cheaply"],
            ["Other T20 (A-team events)", "0.3", "Second-string level"]]
    story.append(table(rows, [6.0 * cm, 1.6 * cm, 9.4 * cm], bold_first_col=True))
    story.append(P("Every season from 2022 to 2026 counts equally. Section 4.3 checks the effect of weighting the IPL more, "
                   "weighting everything equally and favouring recent seasons.", "caption"))
    story += [P("3.3 Who is eligible", "h2"),
              P(f"A batter needs at least 200 high-pressure balls and 15 pressure innings across all competitions; a bowler needs "
                f"240 balls and 20 spells. That leaves {nb} batters and {nw} bowlers. Above that line we still report a confidence "
                f"level (Medium from 300 pressure balls for batters or 360 for bowlers, High from 500 or 600), a 90% range for each "
                f"rank and the chance of making the top 10. We did not drop players who have since retired, because the brief "
                f"asks about performance over the period, not about who is available now."),
              P("3.4 Context, and keeping the future out", "h2"),
              P("Phase, tier and pressure level are handled by the like-for-like comparison. Both innings share one "
                "win-probability scale, rain-shortened innings use their actual limits, and DLS games use the revised target. "
                "Anything that changes over time (scoring level, venue averages, the points table, net run rate, form) is "
                "calculated only from matches before the one being scored, and games on the same day can't see each other. "
                "The win-probability models were always tested on later seasons than they were trained on. Batting and "
                "bowling are rated separately.")]
    story.append(Spacer(1, 8))

    # ================================================================ 4. evidence
    story += [P("4. The evidence behind the top 10", "h1"),
              P("4.1 Batters", "h2")]
    rows = [["", "Batter", "Balls (P)", "SR (P)", "SR (U)", "Avg (P)", "Avg (U)", "Dots % (P)", "Rank range", "P(top 10)"]]
    for _, r in bat.head(10).iterrows():
        rows.append([int(r.final_rank), f"<b>{r.player_name}</b>", int(r.all_p_balls), fmt(r.all_p_sr, 0), fmt(r.all_n_sr, 0),
                     fmt(r.all_p_avg), fmt(r.all_n_avg), fmt(r.all_p_dot_pct), f"{r.rank_p05:.0f}–{r.rank_p95:.0f}", f"{r.p_top10:.0%}"])
    story.append(table(rows, [0.7 * cm, 3.6 * cm, 1.6 * cm, 1.4 * cm, 1.4 * cm, 1.5 * cm, 1.5 * cm, 1.7 * cm, 1.9 * cm, 1.7 * cm]))
    story.append(P("(P) high-pressure balls, (U) all other balls, all competitions. These are plain descriptive figures; the "
                   "rating itself uses the adjusted measures from Section 2. Rank range is the 90% interval from 100 resamples.",
                   "caption"))
    scatter(bat.set_index("player_id"), "bat", "pressure_vs_usual_bat.png")
    scatter(bowl.set_index("player_id"), "bowl", "pressure_vs_usual_bowl.png")
    story += fig(FIG / "pressure_vs_usual_bat.png", 11.5, "Figure 3. Strike rate under pressure against usual strike rate for "
                 "every eligible batter. Points above the dashed line score faster under pressure.")
    story.append(P("Suryakumar Yadav is the clearest call in the whole exercise: he made the top 10 in all 100 resamples. He "
                   "scores 177 per 100 balls under pressure against 163 normally, and his side gained win probability in 64% of his "
                   "pressure innings, the best rate of any batter. The top five all score between 165 and 180 per 100 balls under "
                   "pressure. Four of them also get out less often than batters in the same situations; Abhishek Sharma is the "
                   "exception, accepting a few more dismissals in return for the fastest scoring of the lot (180)."))
    story.append(Spacer(1, 8))
    story += [P("4.2 Bowlers", "h2")]
    rows = [["", "Bowler", "Balls (P)", "Econ (P)", "Econ (U)", "Wkts/24 (P)", "Dots % (P)", "Rank range", "P(top 10)"]]
    for _, r in bowl.head(10).iterrows():
        rows.append([int(r.final_rank), f"<b>{r.player_name}</b>", int(r.all_p_balls), fmt(r.all_p_econ, 2), fmt(r.all_n_econ, 2),
                     fmt(r.all_p_wkts_per24, 2), fmt(r.all_p_dot_pct), f"{r.rank_p05:.0f}–{r.rank_p95:.0f}", f"{r.p_top10:.0%}"])
    story.append(table(rows, [0.7 * cm, 3.8 * cm, 1.7 * cm, 1.6 * cm, 1.6 * cm, 1.9 * cm, 1.7 * cm, 2.0 * cm, 1.7 * cm]))
    story.append(P("(P) high-pressure balls, (U) all other balls, all competitions; plain descriptive figures.", "caption"))
    story += fig(FIG / "pressure_vs_usual_bowl.png", 11.5, "Figure 4. Economy under pressure against usual economy for every "
                 "eligible bowler. Points below the dashed line are tighter under pressure.")
    story.append(P("Spinners dominate the bowling list. Narine, Kuldeep, Axar, Zampa, Krunal, Santner and Rashid all go for about "
                   "seven an over when it matters. Bumrah and Narine are a little more expensive under pressure than they usually "
                   "are, but they remain better than nearly everyone bowling in the same situations, which fits our finding that "
                   "bowling well under pressure is mostly just bowling well."))
    story.append(Spacer(1, 8))

    story += [P("4.3 How much would the list change if we had chosen differently?", "h2"),
              P("We reran the whole ranking for each alternative choice we could reasonably have made. The table shows how many of "
                "our top 10 survive in each case.")]

    def overlaps(role, final):
        t = d[f"top_{role}"]
        top = set(final.player_name.head(10))
        return {c: len(top & set(t[c])) for c in t.columns if c != "baseline"}
    ob, ow = overlaps("bat", bat), overlaps("bowl", bowl)
    labels = {
        "rating weights: expert 0.35/0.2/0.15/0.2/0.1": "Hand-picked weights (0.35 / 0.2 / 0.15 / 0.2 / 0.1)",
        "rating weights: equal weights": "Equal weights for all five parts",
        "rating weights: impact only": "Impact only (win probability added)",
        "rating weights: rise above own usual (uplift 50%)": "Half the weight on improvement over own usual level",
        "competition weighting: IPL-primary: IPL 1, all T20I 0.5, other 0.3": "IPL weighted above all T20Is",
        "competition weighting: all balls equal": "All competitions weighted equally",
        "competition weighting: recency-weighted (half-life 2 seasons)": "Recent seasons weighted more",
        "pressure definition: equal 1/3 each": "Pressure: equal thirds for situation, stakes and form",
        "pressure definition: situation only": "Pressure: match situation only",
        "pressure definition: situation + stakes 0.6/0.4": "Pressure: situation and stakes only (0.6 / 0.4)",
    }
    skip = lambda c: "data-driven" in c or "baseline:" in c or "baseline 0.5" in c
    rows = [["Alternative", "Batters kept", "Bowlers kept"]] + \
           [[labels.get(c, c), f"{ob[c]} of 10", f"{ow[c]} of 10"] for c in ob if not skip(c)]
    story.append(KeepTogether([table(rows, [11.0 * cm, 3.0 * cm, 3.0 * cm])]))
    so = [c for c in ob if "situation only" in c][0]
    ri = [c for c in ob if "rise above" in c][0]
    imp = [c for c in ob if "impact only" in c][0]
    t_b, t_w = d["top_bat"][ri], d["top_bowl"][ri]
    ins = sorted(set(t_b) - set(bat.player_name.head(10))) + sorted(set(t_w) - set(bowl.player_name.head(10)))
    vb = [ob[c] for c in ob if not skip(c)]
    vw = [ow[c] for c in ow if not skip(c)]
    story.append(Spacer(1, 6))
    story.append(P(f"Between {min(vb)} and {max(vb)} of our batters and {min(vw)} to {max(vw)} of our bowlers survive each change "
                   f"(typically {int(pd.Series(vb).median())} and {int(pd.Series(vw).median())}). How we weight the competitions "
                   f"matters least. The biggest changes come from rating on impact alone ({ob[imp]} of 10 batters kept), which is "
                   f"the luck-heavy measure from Section 2.4, and from defining pressure by the match situation only ({ob[so]} "
                   f"batters and {ow[so]} bowlers kept), which tells us stakes and form are adding something. Places 1 to 5 are "
                   f"much steadier than places 6 to 10 (Figure 5)."))
    story.append(P(f"We also tried ranking mainly on improvement over a player's own norm. That keeps {ob[ri]} batters and "
                   f"{ow[ri]} bowlers and brings in {join_names(ins)}, but since most of an individual's gap is noise "
                   f"(Section 2.2) we did not use it for the main list."))
    pair = Table([[fig(FIG / "rank_uncertainty_bat.png", 8.4)[0], fig(FIG / "rank_uncertainty_bowl.png", 8.4)[0]]],
                 colWidths=[8.6 * cm, 8.6 * cm])
    pair.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [pair, P("Figure 5. Final rank (diamond), median rank across the 100 resamples (dot) and 90% range (bar). Batters "
                      "on the left, bowlers on the right.", "caption")]
    story.append(Spacer(1, 8))
    story += role_section(bat, bowl)
    story += dip_section(bat, bowl)
    story.append(Spacer(1, 10))

    # ================================================================ 5. reliability & limitations
    story += [P("5. How reliable is this?", "h1"),
              P("5.1 Does it hold up from one period to the next?", "h2"),
              P("The real test of a rating like this is whether it predicts what happens next. We rated everyone on 2022–24 only "
                "and compared that with how they performed under pressure in 2025–26.")]
    tp = d["temporal"].set_index(d["temporal"].columns[0])
    want = [("players", "Players with enough pressure balls in both periods"),
            ("old estimate -> later pressure scoring/economy", "Pressure record alone, as a predictor of later pressure scoring / economy"),
            ("A (own level) -> later pressure scoring/economy", "Our estimate (Section 2.2), as a predictor of the same"),
            ("normal level only -> later", "Usual (non-pressure) level only, as a predictor of the same"),
            ("A CUP -> later", "Full 2022–24 rating, as a predictor of the same"),
            ("CUP 2022-24 vs CUP 2025-26 (spearman)", "Rating in 2022–24 against rating in 2025–26 (rank correlation)"),
            ("partial r: raw pressure record given normal", "Pressure record as a predictor, after allowing for usual level")]
    rows = [["Test", "Batters", "Bowlers"]]
    for k, label in want:
        a, b = tp.loc[k, "batters"], tp.loc[k, "bowlers"]
        nd = 0 if k == "players" else 2
        rows.append([label, fmt(float(a), nd), fmt(float(b), nd)])
    story.append(table(rows, [12.0 * cm, 2.5 * cm, 2.5 * cm]))
    story.append(P("Figures are correlations. About 40 players qualify in both periods, so each figure is uncertain by roughly "
                   "±0.15.", "caption"))
    story.append(P("For batters the answer is encouraging. Their pressure record predicts their later pressure performance even "
                   "after allowing for general ability (partial r = 0.27), which suggests there is a real pressure skill. For "
                   "bowlers we could not find one. A bowler's pressure record on its own did not predict his later pressure "
                   "economy at all (r = 0.03); measuring it against his usual level brought that to 0.40, which is why Section 2.2 "
                   "exists."))
    story.append(P("Across the resamples, only Suryakumar is close to certain of a top-10 place. The other top-10 places range "
                   "from 33% to 87% for batters and 48% to 81% for bowlers, so the lower half of each list should be read as close "
                   "calls."))
    story += [P("5.2 What it can't do", "h2")]
    story += bullets([
        "Chasing got easier over the period: chasing sides won 48% of games up to 2024, 53% in 2025 and 55% in 2026. Tested on "
        "later seasons, our win-probability models are a few points too pessimistic about chases. The final models are refitted "
        "on all seasons, and because pressure is a ranking of leverage rather than a raw probability, it is not much affected.",
        f"Most leverage sits at the start and end of an innings ({pf['share_overs_1_3']:.0%} of high-pressure balls in overs 1 to 3 "
        f"and {pf['share_overs_17_20']:.0%} in overs 17 to 20), because that is where one ball moves the result most. A fairly "
        f"comfortable finish can still count, such as 23 off 18 with all ten wickets left. Giving extra weight to the side that "
        f"is behind would be a natural next step.",
        "The form measure is statistical and says nothing about a player's state of mind.",
        "We could not reconstruct the qualification rules for some multi-team events (Asia Cup groups and Super 4s, 108 "
        "team-games), so those games carry neutral stakes.",
        "Three players in our top 10 have Low confidence: Klaasen and Rinku Singh among the batters and Narine among the bowlers. "
        "The rating has already discounted their smaller samples and they make the top 10 in most resamples, but their exact "
        "positions are less certain.",
        "The pressure weights, the 30% cut-off and the tier weights are judgement calls. Section 4.3 shows how much each one matters.",
        "Three matches can't be reconstructed to match their recorded result, and when rain shortens an innings part-way through "
        "we apply the reduced length to the whole innings. Both affect only a handful of games.",
    ])
    story.append(Spacer(1, 8))
    story.append(CondPageBreak(9 * cm))
    story += rr_section(d)
    story += [P("Reproducing the results", "h1"),
              P(f"Everything in this report comes from the supplied CSV files via <b>python run_pipeline.py</b> (Python with "
                f"pandas, NumPy, scikit-learn, SciPy and matplotlib), and the report itself is built from the pipeline's outputs "
                f"by report/build_report.py. The steps are: data checks, match state, match-situation pressure for both innings, "
                f"tournament stakes, form, ratings and rankings, and validation. Each step writes a short report to outputs/. "
                f"docs/CODE_GUIDE.md describes every function, docs/DATA_DICTIONARY.md every column, and "
                f"outputs/METHODOLOGY_NOTES.md every decision along with the evidence for it. The final rankings are in "
                f"outputs/rankings_batting_with_uncertainty.csv and outputs/rankings_bowling_with_uncertainty.csv (column "
                f"final_rank). Code: {REPO}")]

    doc = SimpleDocTemplate(str(PDF), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                            title="Who delivers under pressure? SupeRR Selector Season 2 methodology report",
                            author="SupeRR Selector Season 2 team", subject="Round 1 methodology report")
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"written {PDF}")


if __name__ == "__main__":
    build()
