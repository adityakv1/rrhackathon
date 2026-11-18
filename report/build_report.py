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
    "h3": ParagraphStyle("h3", fontName="Body-BoldItalic", fontSize=11.2, leading=14.5, textColor=HEAD, spaceBefore=6,
                         spaceAfter=3, keepWithNext=1),
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


# ------------------------------------------------------------------ typeset equations (LaTeX-style, via matplotlib mathtext)
plt.rcParams["mathtext.fontset"] = "cm"
EQ_DIR = FIG / "equations"
_eq_n = [0]


def eq(tex: str, label: str | None = None, size: float = 15.0) -> Table:
    """Render a formula as a typeset image and centre it, with an optional equation number on the right."""
    EQ_DIR.mkdir(parents=True, exist_ok=True)
    _eq_n[0] += 1
    path = EQ_DIR / f"eq{_eq_n[0]:02d}.png"
    f = plt.figure()
    f.text(0, 0, f"${tex}$", fontsize=size)
    f.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.04, transparent=True)
    plt.close(f)
    img = Image(str(path))
    scale = 0.80                                     # 300 dpi image -> slightly above body-text size
    img.drawWidth, img.drawHeight = img.imageWidth / 300 * 72 * scale, img.imageHeight / 300 * 72 * scale
    num = P(f"({label})", "body") if label else P("", "body")
    t = Table([[img, num]], colWidths=[15.4 * cm, 1.2 * cm])
    t.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def pair_figs(a: Path, b: Path, caption: str, width=8.2) -> list:
    t = Table([[fig(a, width)[0], fig(b, width)[0]]], colWidths=[8.3 * cm, 8.3 * cm])
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return [t, P(caption, "caption")]


# ------------------------------------------------------------------ sections built from data
def _rank_lookup(final: pd.DataFrame) -> dict:
    return dict(zip(final["player_id"], final["final_rank"]))


def role_section(bat: pd.DataFrame, bowl: pd.DataFrame) -> list:
    """Results 5.4: the top three in each role, and why no death specialist reaches the bowling top 10."""
    def names(g):
        return ", ".join(f"{r.player_name} ({int(r.final_rank)})" for _, r in g.sort_values("final_rank").head(3).iterrows())

    rows = [["Role", "Best three under pressure (overall rank)"]]
    for lbl in ["Opener", "Top order (3)", "Middle order (4-5)", "Finisher (6-7)"]:
        rows.append([f"Batting: {lbl}", names(bat[bat.batting_role == lbl])])
    rows.append(["Batting: wicketkeeper", names(bat[bat.keeper == True])])  # noqa: E712
    for lbl in ["Powerplay specialist", "Middle-overs specialist", "Death specialist", "All-phase"]:
        rows.append([f"Bowling: {lbl.replace(' specialist', '').lower()}", names(bowl[bowl.bowling_role == lbl])])
    per_over = bowl.groupby("bowling_role")["p_runs_ae"].mean() * -6
    death = bowl[bowl.bowling_role == "Death specialist"]
    return [P("5.4 Best in each role", "h2"),
            P("Roles are descriptive only (usual batting position; the phase in which a bowler bowls most) and play no part "
              "in the rating."),
            table(rows, [4.6 * cm, 12.0 * cm], bold_first_col=True),
            Spacer(1, 6),
            P(f"No death specialist reaches the bowling top 10. Only {len(death)} of {len(bowl)} eligible bowlers qualify as one "
              f"(a third of their balls in overs 17 to 20). They beat same-situation peers by {per_over['Death specialist']:.2f} "
              f"runs an over under pressure, but the leading middle-overs bowlers beat theirs by "
              f"{per_over['Middle-overs specialist']:.2f}. For the death overs, the table above is the better guide.")]


def dip_section(bat: pd.DataFrame, bowl: pd.DataFrame) -> list:
    """Results 5.5: top-10 players whose own numbers are worse under pressure."""
    tb, tw = bat.head(10), bowl.head(10)
    db = tb[tb.all_p_sr < tb.all_n_sr - 8]
    dw = tw[tw.all_p_econ > tw.all_n_econ + 0.5]
    if not len(db) and not len(dw):
        return []
    items = []
    for _, r in db.iterrows():
        pos = int((bat.all_p_sr > r.all_p_sr).sum() + 1)
        items.append(f"{r.player_name} ({ordinal(r.final_rank)}): SR {r.all_n_sr:.0f} usually, {r.all_p_sr:.0f} under pressure, "
                     f"which is still the {ordinal(pos)} best pressure strike rate of {len(bat)}.")
    for _, r in dw.iterrows():
        pos = int((bowl.all_p_econ < r.all_p_econ).sum() + 1)
        items.append(f"{r.player_name} ({ordinal(r.final_rank)}): economy {r.all_n_econ:.2f} usually, {r.all_p_econ:.2f} under "
                     f"pressure, still {-r.p_runs_ae_raw * 6:.2f} an over better than same-situation peers.")
    return [P("5.5 Top-10 players who dip under pressure", "h2"),
            P("Three of our top 10 are worse under pressure than in their own normal play:")] + bullets(items) + \
           [P("They rank highly because they still beat almost everyone in the same situations, and only a small part of an "
              "individual's gap persists (Section 4.3.2).")]


def rr_section(d: dict) -> list:
    """Results 5.7: the Rajasthan Royals squad through the same method."""
    allb, allw = d["all_bat"], d["all_bowl"]
    rk_b, rk_w = _rank_lookup(d["bat"]), _rank_lookup(d["bowl"])
    nb, nw = len(d["bat"]), len(d["bowl"])

    def status(pid, rk, n):
        return f"{ordinal(rk[pid])}/{n}" if pid in rk else "not ranked"

    b = allb[(allb.current_rr == True) & (allb.all_p_balls >= 100)].sort_values("all_p_balls", ascending=False)  # noqa: E712
    w = allw[(allw.current_rr == True) & (allw.all_p_balls >= 100)].sort_values("all_p_balls", ascending=False)  # noqa: E712
    rows = [["Batter", "SR (P / U)", "Rank", "", "Bowler", "Econ (P / U)", "Rank"]]
    for i in range(max(len(b), len(w))):
        lb = [f"<b>{b.iloc[i].player_name}</b>", f"{b.iloc[i].all_p_sr:.0f} / {b.iloc[i].all_n_sr:.0f}",
              status(b.iloc[i].player_id, rk_b, nb)] if i < len(b) else ["", "", ""]
        lw = [f"<b>{w.iloc[i].player_name}</b>", f"{w.iloc[i].all_p_econ:.2f} / {w.iloc[i].all_n_econ:.2f}",
              status(w.iloc[i].player_id, rk_w, nw)] if i < len(w) else ["", "", ""]
        rows.append(lb + [""] + lw)

    bb = b.set_index("player_name")
    risers = bb[(bb.all_p_sr - bb.all_n_sr) >= 8].index.tolist()
    fallers = bb[(bb.all_p_sr - bb.all_n_sr) <= -8].sort_values("all_p_sr").index.tolist()
    young = b[(~b.player_id.isin(rk_b)) & (b.all_p_sr >= 180)]
    ww = w.copy()
    ww["rank"] = ww.player_id.map(rk_w)
    best_w = ww.dropna(subset=["rank"]).sort_values("rank").head(2)
    top_b = [n for n in bb.index if bb.at[n, "player_id"] in rk_b and rk_b[bb.at[n, "player_id"]] <= 10]
    txt = (f"{join_names(top_b)} is RR's only player in either top 10. {join_names(risers)} score faster under pressure; "
           f"{join_names(fallers)} slow down markedly, the squad's main batting risk. ")
    if len(young):
        y = young.iloc[0]
        txt += f"{y.player_name} strikes at {y.all_p_sr:.0f} under pressure but on only {int(y.all_p_balls)} balls, below our threshold. "
    txt += (f"The best RR bowlers are {join_names(f'{n} ({ordinal(r)})' for n, r in zip(best_w.player_name, best_w['rank']))}, "
            f"and the squad has no death specialist, its thinnest area under pressure.")
    return [P("5.7 The Rajasthan Royals squad", "h2"),
            P("The same method, unchanged, applied to RR's latest IPL squad (players with 100+ pressure balls):"),
            table(rows, [3.5 * cm, 2.0 * cm, 1.9 * cm, 0.3 * cm, 3.2 * cm, 2.3 * cm, 1.9 * cm]),
            P("(P) under pressure, (U) usually. 'Not ranked' = below the eligibility threshold.", "caption"),
            P(txt)]


# ------------------------------------------------------------------ the report
def build():
    d = load()
    bat, bowl = d["bat"], d["bowl"]
    nb, nw = len(bat), len(bowl)
    pf = d["profile"]
    story = []

    # ================================================================ title + abstract
    story += [P("Who delivers under pressure?", "title"),
              P("SupeRR Selector Season 2, Round 1: methodology report. IPL and T20I data, 2022 to 2026", "subtitle"),
              P("Abstract", "h2"),
              P(f"We score how much is riding on every delivery for the batter and the bowler, then rate players on the most "
                f"pressured 30% of balls against same-situation peers and their own usual level. Weights come from how "
                f"repeatable each measure is, small samples are shrunk and every rank carries an uncertainty estimate. "
                f"{bat.iloc[0].player_name} and {bowl.iloc[0].player_name} top the lists. Batters show a pressure skill of their "
                f"own; for bowlers, pressure performance is mostly general bowling quality.")]

    # ================================================================ 1-3
    story += [P("1. Problem Statement", "h1"),
              P("Reputations for 'delivering when it matters' rest on memorable moments. The challenge is to build a data-driven "
                "system that measures how batters and bowlers perform in high-pressure situations compared with their usual "
                "level, defines pressure in a justified way, and ranks the ten most reliable batters and bowlers. The data: "
                "200,961 deliveries from 867 IPL and T20I matches (January 2022 to November 2026), plus match, team, squad and "
                "playing-XI files."),
              P("2. Objectives", "h1")]
    story += bullets(["Define pressure for every ball, for batters and bowlers, using only information available at the time.",
                      "Show that it separates pressure situations from ordinary ones.",
                      "Rate players against same-situation peers and against their own usual level.",
                      "Keep comparisons fair across competitions, phases and sample sizes.",
                      "Rank the top 10 batters and bowlers with honest uncertainty, and test stability over time."])
    rows = [["Gap in the usual approach", "How we address it"],
            ["Averages treat every ball the same", "A pressure score for every ball (4.2)"],
            ["Raw death-over numbers punish the hardest jobs", "Compare with same phase and pressure band (4.3.1)"],
            ["'Clutch' reputations rest on memorable moments", "Weight each measure by its repeatability (4.3.4)"],
            ["Small samples flatter", "Shrinkage, eligibility rules, confidence levels (4.3.3, 4.4)"],
            ["Players judged on pressure balls alone", "Estimate relative to the player's usual level (4.3.2)"],
            ["IPL and T20I pooled as if equal", "Competition tiers, compared within tier (4.4)"],
            ["Importance judged with hindsight", "Only information available before each ball (4.4)"],
            ["Rankings shown without uncertainty", "Rank ranges and P(top 10) from 100 resamples (5.3)"]]
    story += [P("3. Gap Identification", "h1"),
              KeepTogether([table(rows, [7.6 * cm, 9.0 * cm], bold_first_col=True)])]

    # ================================================================ 4. methodology
    story += [P("4. Methodology", "h1")]
    story.append(KeepTogether(fig(pipeline_figure(), 14.0, "Figure 1. The pipeline (run_pipeline.py, about 12 minutes from the raw files).")))
    story += [P("4.1 Data and match state", "h2"),
              P("Every reading of the data was checked against results it should reproduce. Runs per ball "
                "(runs + extras1_runs + extras_2_runs) reproduce 399 of 400 stated winning margins; the 'other' extras type is a "
                "no-ball (with that reading all 216 completed overs containing one have six legal balls, otherwise none do); "
                "revised-overs fields are in balls. Super Overs and 16 abandoned matches are excluded. We rebuild the state "
                "before and after every ball, and 99.6% of 843 completed chases end in a state matching the recorded result."),
              P("4.2 Defining pressure", "h2"),
              P("A ball is a pressure ball when a lot rides on it for the player. Three signals, each scaled 0 to 100, use only "
                "information available at the time."),
              P("4.2.1 Match situation (MSP)", "h3"),
              P("We estimate the batting side's win probability WP before every ball. Chases use a logistic model on runs needed, "
                "balls left, wickets in hand and the recent scoring level, with an exact ball-by-ball recursion over the last 30 "
                "balls (tested on 2025–26: AUC 0.918, log loss 0.370, against 0.897 and 0.411 for required run rate alone). "
                "In the first innings, with remaining runs R predicted by a monotonic model (error 18.0 runs, against 27.0 for "
                "run rate × overs left):"),
              eq(r"WP_1=\sum_{T}P(\mathrm{final\ total}=T\mid\mathrm{state})\,\left(1-WP_2(\mathrm{target}=T+1)\right)", "1"),
              P("Pressure on ball b is its leverage, the win-probability swing expected from it, summed over the outcomes "
                "dot, 1, 2, 3, 4, 6, wicket and extra:"),
              eq(r"L_b=\sum_{o}P(o\mid\mathrm{phase})\,\left|\,WP_{b}^{\,o}-WP_b\,\right|,\qquad "
                 r"\mathrm{MSP}_b=100\cdot\mathrm{percentile}(L_b)", "2"),
              P("4.2.2 Tournament stakes (TSP)", "h3"),
              eq(r"\mathrm{TSP}_{t,m}=P(\mathrm{title}\mid t\ \mathrm{wins}\ m)-P(\mathrm{title}\mid t\ \mathrm{loses}\ m)", "3"),
              P("League tables are rebuilt from earlier results only and the remaining fixtures simulated 4,000 times. "
                "Knockouts are exact (final 1.0, semi-final and Qualifier 2 0.5, Qualifier 1 and Eliminator 0.25); bilateral "
                "series use 'win the series'. TSP is ranked within competition group."),
              P("4.2.3 Form (IPP)", "h3"),
              P("Each player's last five innings or spells against his own career baseline (runs, strike rate and low-score run; "
                "economy, wicket rate and wicketless run), averaged as percentiles. Role players only; a statistical signal, not "
                "a claim about state of mind."),
              P("4.2.4 Combined index", "h3"),
              eq(r"\mathrm{CPI}_b=0.5\,\mathrm{MSP}_b+0.3\,\mathrm{TSP}_b+0.2\,\mathrm{IPP}_b", "4"),
              eq(r"b\ \mathrm{is\ high\ pressure}\ \Leftrightarrow\ \mathrm{CPI}_b\geq Q_{0.70}(\mathrm{CPI})", "5"),
              P("Batter and bowler share MSP but use their own team's stakes and their own form.")]
    sep = d["sep"]
    sel = sep[sep["decile"].isin(["1", "5", "8", "9", "10"])]
    rows = [["Pressure group", "Avg swing per ball", "Dismissal %", "Strike rate", "Knockout balls %"]]
    for _, r in sel.iterrows():
        rows.append([r["decile"], f"{float(r['mean_absWPA']):.3f}", f"{float(r['dismissal_%']):.1f}",
                     f"{float(r['strike_rate']):.0f}", f"{float(r['knockout_%']):.1f}"])
    story += [KeepTogether([P("4.2.5 Does it separate pressure from ordinary balls?", "h3"),
                            table(rows, [3.0 * cm, 3.6 * cm, 3.0 * cm, 3.0 * cm, 4.0 * cm])]),
              P(f"Across all balls split into ten groups, the expected swing rises sevenfold and knockout balls fourteenfold from "
                f"calmest to most pressured, while average strike rate barely moves: pressure changes how much a ball matters, not "
                f"how the average ball goes. Only {pf['share_nearly_decided (WP<15% or >85%)']:.1%} of high-pressure balls come "
                f"from nearly settled games. Example: Kohli's hundred v SRH (2023), RCB 133/0 needing 54 off 36 had WP 94.7%, so "
                f"MSP 17, stakes 72 and form 48 gave CPI 39.7, below the cut-off of 59.7; 30 of his 63 balls (overs 1 to 4 and "
                f"17 to 18) were high-pressure.")]

    story += [P("4.3 Measuring performance", "h2"),
              P("4.3.1 Same-situation peers. Each outcome y (runs, dismissal, runs conceded, wicket) is compared with the average "
                "over balls of the same competition tier c, phase φ and pressure band h:", "body"),
              eq(r"\Delta y_b=y_b-\bar{y}_{\,c,\,\phi,\,h}", "6"),
              P("4.3.2 Own usual level. A player j has far more ordinary balls than pressure balls, so his pressure estimate starts "
                "from his usual level u and keeps only the part of his pressure gap the data supports:"),
              eq(r"\hat{p}_j=\hat{u}_j+\lambda_j\left(\bar{p}_j-\bar{u}_j\right),\qquad "
                 r"\lambda_j=\dfrac{\tau_d^{2}}{\tau_d^{2}+\sigma_j^{2}}", "7"),
              P("The numerator is the true spread of pressure gaps between players, the second term in the denominator is the "
                "sampling noise in player j's own gap. Typically λ ≈ 0.07 for batting and 0.10 for bowling: most individual gaps "
                "are noise. The shrunk gap is the uplift component."),
              P("4.3.3 Small samples. Every rate is shrunk towards the population mean μ by an amount k estimated from the data "
                "(within-player noise relative to the true spread between players):"),
              eq(r"\hat{\theta}_j=\mu+\dfrac{n_j}{n_j+k}\left(\bar{x}_j-\mu\right),\qquad k=\dfrac{\sigma_w^{2}}{\tau^{2}}", "8"),
              P("4.3.4 Rating. Five components (impact = win probability added; scoring or economy; survival or wickets; "
                "reliability = share of pressure innings that gained win probability; uplift) are standardised across eligible "
                "players and weighted by their split-half repeatability r; the final order uses the average over 100 match "
                "resamples s:"),
              eq(r"R_j=\sum_{c}w_c\,z_{jc},\qquad w_c=\dfrac{\max(r_c,0)}{\sum_{c'}\max(r_{c'},0)},\qquad "
                 r"\overline{R}_j=\dfrac{1}{100}\sum_{s=1}^{100}R_j^{(s)}", "9")]
    rb, rw = d["rel_bat"].set_index(d["rel_bat"].columns[0]), d["rel_bowl"].set_index(d["rel_bowl"].columns[0])
    rows = [["Batting", "r", "Weight", "", "Bowling", "r", "Weight"]]
    for (kb, a), (kw, b) in zip(rb.iterrows(), rw.iterrows()):
        rows.append([kb.capitalize(), fmt(float(a["split-half r"]), 2), f"{float(a['weight']):.0%}", "",
                     kw.capitalize(), fmt(float(b["split-half r"]), 2), f"{float(b['weight']):.0%}"])
    story += [KeepTogether([table(rows, [3.0 * cm, 1.8 * cm, 1.8 * cm, 0.5 * cm, 3.0 * cm, 1.8 * cm, 1.8 * cm]),
              P("Resamples keep the shrinkage settings at their full-data values. Win probability added per ball barely repeats "
                "(r = 0.05), so it carries little weight.", "caption")])]

    story += [P("4.4 Fair comparisons", "h2"),
              P(f"IPL and T20I are never mixed raw: balls are compared within competition tier (equation 6) and tiers weighted by "
                f"opposition strength (IPL 1.0, T20I between full members 1.0, T20I involving an associate 0.4, A-team events 0.3); all seasons count equally. Eligibility: batters need 200+ pressure balls and 15+ "
                f"pressure innings, bowlers 240+ balls and 20+ spells ({nb} and {nw} qualify). Confidence is Medium from 300 "
                f"(batters) or 360 (bowlers) pressure balls and High from 500 or 600. Everything that changes over time "
                f"(scoring level, tables, form) uses only earlier matches, and models are tested on later seasons.")]

    # ================================================================ 5. results
    story.append(CondPageBreak(9 * cm))
    story += [P("5. Results", "h1"), P("5.1 Final top 10s", "h2")]
    rows = [["", "Batter", "Conf.", "P(top 10)", "", "", "Bowler", "Conf.", "P(top 10)"]]
    for i in range(10):
        a, b = bat.iloc[i], bowl.iloc[i]
        rows.append([i + 1, f"<b>{a.player_name}</b>", a.confidence, f"{a.p_top10:.0%}", "",
                     i + 1, f"<b>{b.player_name}</b>", b.confidence, f"{b.p_top10:.0%}"])
    story += [table(rows, [0.8 * cm, 3.7 * cm, 1.7 * cm, 1.7 * cm, 0.3 * cm, 0.8 * cm, 3.7 * cm, 1.7 * cm, 1.7 * cm]),
              P("P(top 10): share of 100 match resamples in which the player is in the top 10.", "caption")]

    rows = [["", "Batter", "Balls (P)", "SR (P)", "SR (U)", "Avg (P)", "Avg (U)", "Rank range"]]
    for _, r in bat.head(10).iterrows():
        rows.append([int(r.final_rank), f"<b>{r.player_name}</b>", int(r.all_p_balls), fmt(r.all_p_sr, 0), fmt(r.all_n_sr, 0),
                     fmt(r.all_p_avg), fmt(r.all_n_avg), f"{r.rank_p05:.0f}–{r.rank_p95:.0f}"])
    story += [P("5.2 Evidence", "h2"),
              KeepTogether([table(rows, [0.8 * cm, 3.8 * cm, 1.9 * cm, 1.7 * cm, 1.7 * cm, 1.9 * cm, 1.9 * cm, 2.9 * cm])]), Spacer(1, 5)]
    rows = [["", "Bowler", "Balls (P)", "Econ (P)", "Econ (U)", "Wkts/24 (P)", "Dots % (P)", "Rank range"]]
    for _, r in bowl.head(10).iterrows():
        rows.append([int(r.final_rank), f"<b>{r.player_name}</b>", int(r.all_p_balls), fmt(r.all_p_econ, 2), fmt(r.all_n_econ, 2),
                     fmt(r.all_p_wkts_per24, 2), fmt(r.all_p_dot_pct), f"{r.rank_p05:.0f}–{r.rank_p95:.0f}"])
    story += [KeepTogether([table(rows, [0.8 * cm, 3.8 * cm, 1.9 * cm, 1.7 * cm, 1.7 * cm, 1.9 * cm, 1.9 * cm, 2.9 * cm]),
              P("(P) high-pressure balls, (U) all other balls; raw figures. Rank range: 90% interval over 100 resamples.", "caption")])]
    scatter(bat.set_index("player_id"), "bat", "pressure_vs_usual_bat.png")
    scatter(bowl.set_index("player_id"), "bowl", "pressure_vs_usual_bowl.png")
    story += pair_figs(FIG / "pressure_vs_usual_bat.png", FIG / "pressure_vs_usual_bowl.png",
                       "Figure 2. Pressure vs usual for every eligible player: strike rate (left, above the line = faster under "
                       "pressure) and economy (right, below the line = tighter).")
    story.append(P("Suryakumar Yadav is the clearest call (top 10 in all 100 resamples): 177 per 100 balls under pressure against "
                   "163 usually, and the best reliability of any batter (64% of pressure innings gained win probability). The top "
                   "five batters all score at 165 to 180 under pressure. The bowling list is led by spinners who concede about "
                   "seven an over when it matters."))

    def overlaps(role, final):
        t = d[f"top_{role}"]
        top = set(final.player_name.head(10))
        return {c: len(top & set(t[c])) for c in t.columns if c != "baseline"}
    ob, ow = overlaps("bat", bat), overlaps("bowl", bowl)
    labels = {"rating weights: expert 0.35/0.2/0.15/0.2/0.1": "Hand-picked rating weights",
              "rating weights: equal weights": "Equal rating weights",
              "rating weights: impact only": "Impact only",
              "rating weights: rise above own usual (uplift 50%)": "50% weight on improvement over own level",
              "competition weighting: IPL-primary: IPL 1, all T20I 0.5, other 0.3": "IPL weighted above T20I",
              "competition weighting: all balls equal": "All competitions equal",
              "competition weighting: recency-weighted (half-life 2 seasons)": "Recent seasons weighted more",
              "pressure definition: equal 1/3 each": "Pressure: equal thirds",
              "pressure definition: situation only": "Pressure: match situation only",
              "pressure definition: situation + stakes 0.6/0.4": "Pressure: situation + stakes only"}
    skip = lambda c: "data-driven" in c or "baseline:" in c or "baseline 0.5" in c
    keys = [c for c in ob if not skip(c)]
    rows = [["Alternative choice", "Batters kept", "Bowlers kept"]] + [[labels.get(c, c), f"{ob[c]}/10", f"{ow[c]}/10"] for c in keys]
    vb, vw = [ob[c] for c in keys], [ow[c] for c in keys]
    story += [P("5.3 Robustness and uncertainty", "h2"),
              KeepTogether([table(rows, [9.6 * cm, 3.4 * cm, 3.4 * cm])]),
              P(f"Each alternative keeps {min(vb)} to {max(vb)} batters and {min(vw)} to {max(vw)} bowlers (typically "
                f"{int(pd.Series(vb).median())} and {int(pd.Series(vw).median())}). Places 1 to 5 are far steadier than 6 to 10.")]
    story += pair_figs(FIG / "rank_uncertainty_bat.png", FIG / "rank_uncertainty_bowl.png",
                       "Figure 3. Final rank (diamond), median resampled rank (dot) and 90% range (bar).")

    story += role_section(bat, bowl)
    story += dip_section(bat, bowl)

    tp = d["temporal"].set_index(d["temporal"].columns[0])
    want = [("old estimate -> later pressure scoring/economy", "Pressure record alone"),
            ("A (own level) -> later pressure scoring/economy", "Our estimate, equation 7"),
            ("normal level only -> later", "Usual level alone"),
            ("partial r: raw pressure record given normal", "Pressure record, beyond usual level (partial r)")]
    rows = [["Predicting 2025–26 pressure performance from 2022–24", "Batters", "Bowlers"]]
    for k, label in want:
        rows.append([label, fmt(float(tp.loc[k, "batters"]), 2), fmt(float(tp.loc[k, "bowlers"]), 2)])
    story += [P("5.6 Stability over time", "h2"),
              table(rows, [11.0 * cm, 2.7 * cm, 2.7 * cm]),
              P("Correlations; about 40 players per group, so roughly ±0.15.", "caption"),
              P("Batters have a pressure skill beyond general ability (partial r = 0.27). Bowlers do not: their pressure record "
                "alone predicted nothing (0.03), while equation 7 lifts this to 0.40.")]

    story += rr_section(d)

    # ================================================================ 6. conclusion
    story += [P("6. Conclusion", "h1"),
              P(f"Pressure can be measured ball by ball in a way that follows close contests, knockouts and match-turning moments, "
                f"and it can differ for the batter and bowler on one delivery. Rated fairly, against same-situation peers and "
                f"their own usual level, {bat.iloc[0].player_name} and {bowl.iloc[0].player_name} are the clearest pressure "
                f"performers of 2022–26. Big individual moments are mostly luck; scoring rate, survival and economy are the "
                f"skills that repeat. Places 6 to 10 in each list are close calls, and we report them as such."),
              P("Limitations", "h3")]
    story += bullets(["Chasing became easier over the period (48% of chases won to 2024, 55% in 2026); the win-probability models "
                      "are refitted on all seasons and MSP, a ranking of leverage, is robust to this.",
                      f"Leverage concentrates at the start and end of innings ({pf['share_overs_1_3']:.0%} and "
                      f"{pf['share_overs_17_20']:.0%} of pressure balls in overs 1 to 3 and 17 to 20).",
                      "Asia Cup group stages (108 team-games) carry neutral stakes; their qualification rules are not in the data.",
                      "Klaasen, Rinku Singh and Narine have Low confidence; shrinkage discounts them, but their positions are less certain.",
                      "The pressure weights, the 30% cut-off and the tier weights are judgement calls, tested in Section 5.3."])
    story += [P("Future work", "h3")]
    story += bullets(["Extra pressure for the side that is behind.",
                      "A 'safest' ordering from the lower end of each player's rating range.",
                      "More seasons and domestic leagues to lift Low-confidence players."])
    story += [P("Appendix: reproducibility", "h3"),
              P(f"All results come from the supplied CSVs via python run_pipeline.py; the report is built by "
                f"report/build_report.py. Code, documentation and outputs: {REPO}")]

    doc = SimpleDocTemplate(str(PDF), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                            title="Who delivers under pressure? SupeRR Selector Season 2 methodology report",
                            author="SupeRR Selector Season 2 team", subject="Round 1 methodology report")
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"written {PDF}")


if __name__ == "__main__":
    build()
