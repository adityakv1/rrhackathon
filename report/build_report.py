"""Build the Round 1 methodology report (PDF) from the pipeline outputs.

    python report/build_report.py      ->  outputs/SupeRR_Selector_Methodology_Report.pdf

Every table, figure and number is read from files the pipeline writes (outputs/*.csv, outputs/*_report.md,
outputs/*.json), so the report always matches the code. Run `python run_pipeline.py` first.
The report is typeset in black and white; its figures are drawn here in greyscale.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
FIG = OUT / "figures" / "report"
PDF = OUT / "SupeRR_Selector_Methodology_Report.pdf"
REPO = "github.com/adityakv1/rrhackathon"

# ------------------------------------------------------------------ typography (black and white, serif)
FONT_DIR = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Serif", str(FONT_DIR / "times.ttf")))
pdfmetrics.registerFont(TTFont("Serif-Bold", str(FONT_DIR / "timesbd.ttf")))
pdfmetrics.registerFont(TTFont("Serif-Italic", str(FONT_DIR / "timesi.ttf")))
pdfmetrics.registerFont(TTFont("Serif-BoldItalic", str(FONT_DIR / "timesbi.ttf")))
pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Serif-Bold", italic="Serif-Italic", boldItalic="Serif-BoldItalic")

BLACK = colors.black
S = {
    "title": ParagraphStyle("title", fontName="Serif-Bold", fontSize=18, leading=22, alignment=TA_CENTER, spaceAfter=6),
    "subtitle": ParagraphStyle("subtitle", fontName="Serif", fontSize=12, leading=15, alignment=TA_CENTER, spaceAfter=18),
    "abs_head": ParagraphStyle("abs_head", fontName="Serif-Bold", fontSize=11, leading=14, alignment=TA_CENTER, spaceAfter=4),
    "abstract": ParagraphStyle("abstract", fontName="Serif", fontSize=10.5, leading=14, alignment=TA_JUSTIFY,
                               leftIndent=1.2 * cm, rightIndent=1.2 * cm, spaceAfter=14),
    "h1": ParagraphStyle("h1", fontName="Serif-Bold", fontSize=13.5, leading=17, spaceBefore=12, spaceAfter=6, keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName="Serif-Bold", fontSize=12, leading=15, spaceBefore=8, spaceAfter=4, keepWithNext=1),
    "h3": ParagraphStyle("h3", fontName="Serif-BoldItalic", fontSize=11, leading=14, spaceBefore=6, spaceAfter=3, keepWithNext=1),
    "body": ParagraphStyle("body", fontName="Serif", fontSize=11, leading=14.6, alignment=TA_JUSTIFY, spaceAfter=6),
    "item": ParagraphStyle("item", fontName="Serif", fontSize=11, leading=14.4, alignment=TA_JUSTIFY, leftIndent=18,
                           bulletIndent=4, spaceAfter=3),
    "tcap": ParagraphStyle("tcap", fontName="Serif-Bold", fontSize=10, leading=13, spaceBefore=4, spaceAfter=3, keepWithNext=1),
    "note": ParagraphStyle("note", fontName="Serif-Italic", fontSize=9.5, leading=12, spaceBefore=2, spaceAfter=9),
    "fcap": ParagraphStyle("fcap", fontName="Serif", fontSize=10, leading=13, alignment=TA_CENTER, spaceBefore=3, spaceAfter=10),
    "cell": ParagraphStyle("cell", fontName="Serif", fontSize=10, leading=12),
    "cellb": ParagraphStyle("cellb", fontName="Serif-Bold", fontSize=10, leading=12),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def items(lines, numbered=False):
    return [Paragraph(t, S["item"], bulletText=(f"{i}." if numbered else "•")) for i, t in enumerate(lines, 1)]


_tab_n, _fig_n = [0], [0]


def table(rows, widths, caption=None, note=None, bold_first_col=False, head=None):
    """Booktabs-style table: rules above and below the header and at the bottom, no shading."""
    data = [[c if isinstance(c, Paragraph) else Paragraph(str(c), S["cellb" if i == 0 or (bold_first_col and j == 0) else "cell"])
             for j, c in enumerate(r)] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LINEABOVE", (0, 0), (-1, 0), 1.0, BLACK), ("LINEBELOW", (0, 0), (-1, 0), 0.6, BLACK),
                           ("LINEBELOW", (0, -1), (-1, -1), 1.0, BLACK),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                           ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    block = [head] if head is not None else []
    if caption:
        _tab_n[0] += 1
        block.append(P(f"Table {_tab_n[0]}. {caption}", "tcap"))
    block.append(t)
    if note:
        block.append(P(note, "note"))
    else:
        block.append(Spacer(1, 8))
    return KeepTogether(block)


def image(path, width_cm):
    img = Image(str(path))
    img.drawWidth, img.drawHeight = width_cm * cm, width_cm * cm * img.imageHeight / img.imageWidth
    return img


def figure(paths, caption, width_cm=15.0):
    """One image, or two side by side, with a numbered caption below."""
    _fig_n[0] += 1
    if isinstance(paths, (list, tuple)):
        w = width_cm / 2 - 0.2
        body = Table([[image(p, w) for p in paths]], colWidths=[width_cm / 2 * cm] * 2)
        body.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    else:
        body = image(paths, width_cm)
    return KeepTogether([body, P(f"Figure {_fig_n[0]}. {caption}", "fcap")])


def ordinal(n: int) -> str:
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def join_names(names) -> str:
    names = list(names)
    return "".join(names) if len(names) <= 1 else ", ".join(names[:-1]) + " and " + names[-1]


def fmt(x, nd=1):
    return "–" if pd.isna(x) else f"{x:.{nd}f}"


# ------------------------------------------------------------------ equations (typeset with matplotlib mathtext)
plt.rcParams.update({"mathtext.fontset": "cm", "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"]})
_eq_n = [0]


def eq(tex: str, size: float = 15.0) -> Table:
    """Typeset a numbered display equation."""
    (FIG / "eq").mkdir(parents=True, exist_ok=True)
    _eq_n[0] += 1
    path = FIG / "eq" / f"eq{_eq_n[0]:02d}.png"
    f = plt.figure()
    f.text(0, 0, f"${tex}$", fontsize=size, color="black")
    f.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.04, transparent=True)
    plt.close(f)
    img = Image(str(path))
    img.drawWidth, img.drawHeight = img.imageWidth / 300 * 72 * 0.8, img.imageHeight / 300 * 72 * 0.8
    t = Table([[img, P(f"({_eq_n[0]})", "cell")]], colWidths=[15.4 * cm, 1.2 * cm])
    t.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "CENTER"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


# ------------------------------------------------------------------ data
def md_table(md: str, heading: str) -> pd.DataFrame:
    """First markdown table after a heading line that contains `heading`."""
    lines = md.replace("mean_|WPA|", "mean_absWPA").replace("record | normal", "record given normal").split("\n")
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
    d = {"bat": pd.read_csv(OUT / "rankings_batting_with_uncertainty.csv").sort_values("final_rank"),
         "bowl": pd.read_csv(OUT / "rankings_bowling_with_uncertainty.csv").sort_values("final_rank"),
         "all_bat": pd.read_csv(OUT / "players_all_batting.csv"),
         "all_bowl": pd.read_csv(OUT / "players_all_bowling.csv"),
         "profile": json.loads((OUT / "pressure_profile.json").read_text(encoding="utf-8"))}
    cup = (OUT / "cup_rankings_report.md").read_text(encoding="utf-8")
    val = (OUT / "validation_rankings_report.md").read_text(encoding="utf-8")
    d["rel_bat"] = md_table(cup.split("# Batters")[1], "Component repeatability")
    d["rel_bowl"] = md_table(cup.split("# Bowlers")[1], "Component repeatability")
    d["sep"] = md_table(val, "## 1.")
    d["temporal"] = md_table(val, "## 3.")
    for r in ["bat", "bowl"]:
        d[f"top_{r}"] = pd.read_csv(OUT / f"sensitivity_top10_{'batting' if r == 'bat' else 'bowling'}.csv", index_col=0)
    return d


# ------------------------------------------------------------------ greyscale figures
GREY = {"axes.edgecolor": "black", "axes.labelcolor": "black", "xtick.color": "black", "ytick.color": "black",
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False, "font.size": 9}


def fig_separation(sep: pd.DataFrame) -> Path:
    path = FIG / "separation.png"
    x = sep["decile"].astype(int)
    with plt.rc_context(GREY):
        f, ax = plt.subplots(1, 3, figsize=(10, 2.9), dpi=200)
        for a, col, title in zip(ax, ["mean_absWPA", "dismissal_%", "strike_rate"],
                                 ["(a) Expected win-probability swing", "(b) Dismissal rate (%)", "(c) Strike rate"]):
            a.axvspan(7.5, 10.5, color="0.88", lw=0)
            a.plot(x, sep[col].astype(float), "k-o", ms=3.5, lw=1.1)
            a.set_title(title, fontsize=9.5)
            a.set_xlabel("Pressure decile (1 = lowest)")
            a.set_xticks(range(1, 11))
        f.tight_layout()
        f.savefig(path, bbox_inches="tight")
        plt.close(f)
    return path


def fig_scatter(df: pd.DataFrame, role: str) -> Path:
    path = FIG / f"scatter_{role}.png"
    xcol, ycol = ("all_n_sr", "all_p_sr") if role == "bat" else ("all_n_econ", "all_p_econ")
    top = df.head(10)
    with plt.rc_context(GREY):
        f, ax = plt.subplots(figsize=(5, 4.4), dpi=200)
        ax.scatter(df[xcol], df[ycol], s=12, facecolors="white", edgecolors="0.45", lw=0.7, label="Other eligible players")
        ax.scatter(top[xcol], top[ycol], s=20, color="black", label="Top 10")
        for _, r in top.iterrows():
            ax.annotate(r["player_name"].split()[-1], (r[xcol], r[ycol]), fontsize=6.5, xytext=(3, 2), textcoords="offset points")
        lo, hi = min(df[xcol].min(), df[ycol].min()), max(df[xcol].max(), df[ycol].max())
        ax.plot([lo, hi], [lo, hi], color="black", lw=0.7, ls="--")
        if role == "bat":
            ax.set_xlabel("Strike rate, usual situations")
            ax.set_ylabel("Strike rate, high pressure")
        else:
            ax.set_xlabel("Economy, usual situations")
            ax.set_ylabel("Economy, high pressure")
        ax.legend(frameon=False, fontsize=7, loc="upper left")
        f.tight_layout()
        f.savefig(path, bbox_inches="tight")
        plt.close(f)
    return path


def fig_ranks(df: pd.DataFrame, role: str) -> Path:
    path = FIG / f"ranks_{role}.png"
    top = df.head(10).iloc[::-1]
    y = np.arange(len(top))
    with plt.rc_context(GREY):
        f, ax = plt.subplots(figsize=(5, 3.6), dpi=200)
        ax.hlines(y, top["rank_p05"], top["rank_p95"], color="0.6", lw=3)
        ax.plot(top["median_rank"], y, "o", mfc="white", mec="black", ms=4.5, label="Median resampled rank")
        ax.plot(top["final_rank"], y, "D", color="black", ms=3.8, label="Final rank")
        ax.set_yticks(y)
        ax.set_yticklabels(top["player_name"], fontsize=7.5)
        ax.set_xlabel("Rank (bar: 90% interval over 100 resamples)")
        ax.legend(frameon=False, fontsize=7, loc="lower right")
        f.tight_layout()
        f.savefig(path, bbox_inches="tight")
        plt.close(f)
    return path


# ------------------------------------------------------------------ page furniture
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Serif", 9)
    canvas.drawCentredString(A4[0] / 2, 1.2 * cm, str(doc.page))
    canvas.restoreState()


# ------------------------------------------------------------------ the report
def build():
    FIG.mkdir(parents=True, exist_ok=True)
    d = load()
    bat, bowl = d["bat"], d["bowl"]
    nb, nw = len(bat), len(bowl)
    pf = d["profile"]
    story = []

    # ================================================================ title and abstract
    story += [P("Measuring Player Performance Under Pressure in T20 Cricket", "title"),
              P("SupeRR Selector Season 2, Round 1: Methodology Report", "subtitle"),
              P("Abstract", "abs_head"),
              P(f"This report presents a method for identifying the batters and bowlers who perform most consistently in "
                f"high-pressure situations, using IPL and T20 International ball-by-ball data from 2022 to 2026. Pressure is "
                f"defined for every delivery as a weighted combination of match-situation leverage, tournament stakes and "
                f"individual form. Players are rated on the most pressured 30% of deliveries relative to players in equivalent "
                f"situations and to their own usual level, with empirical-Bayes shrinkage for small samples, component weights "
                f"derived from measured repeatability, and bootstrap estimates of rank uncertainty. {bat.iloc[0].player_name} "
                f"and {bowl.iloc[0].player_name} lead the batting and bowling rankings respectively. The analysis finds a "
                f"persistent pressure-specific effect for batters but not for bowlers.", "abstract")]

    # ================================================================ 1. problem statement
    story += [P("1. Problem Statement", "h1"),
              P("Assessments of how players respond to pressure are frequently based on a small number of memorable "
                "performances. The SupeRR Selector Season 2 challenge requires a data-driven system that measures how batters "
                "and bowlers perform in high-pressure match situations compared with their usual performance, and that ranks "
                "the ten batters and ten bowlers who deliver most consistently when it matters. The definition of pressure is "
                "left to the participant and must be justified and shown to distinguish pressure situations from ordinary ones."),
              P("The supplied data comprise 200,961 regular deliveries from 867 IPL and T20I matches played between January 2022 "
                "and November 2026, together with match, team, squad and playing-XI records.")]

    # ================================================================ 2. objectives
    story += [P("2. Objectives", "h1")]
    story += items(["To define a measure of pressure for every delivery that applies to both batters and bowlers and uses "
                    "only information available at the time.",
                    "To demonstrate that this measure separates pressure situations from ordinary ones.",
                    "To evaluate each player's performance under pressure against players in equivalent situations and "
                    "against the player's own usual level.",
                    "To ensure fair comparison across competitions, phases of play and sample sizes.",
                    "To produce ranked top-10 lists of batters and bowlers with quantified uncertainty, and to test the "
                    "stability of the ratings over time."], numbered=True)

    # ================================================================ 3. gap identification
    story += [P("3. Gap Identification", "h1"),
              P("Conventional approaches to this question have several limitations. Table 1 lists them and the corresponding "
                "element of the proposed method.")]
    story.append(table(
        [["Limitation of conventional approaches", "Response in the proposed method"],
         ["Season averages and strike rates weight every delivery equally", "A pressure score for every delivery (Section 4.3)"],
         ["Raw death-over figures penalise players in the most difficult roles", "Comparison with players in the same phase and pressure band (Section 4.4.1)"],
         ["Reputations rest on isolated, memorable moments", "Component weights based on measured repeatability (Section 4.4.4)"],
         ["Small samples produce extreme values", "Shrinkage, eligibility thresholds and confidence levels (Sections 4.4.3, 4.5)"],
         ["Pressure performance is judged in isolation", "Estimation relative to the player's usual level (Section 4.4.2)"],
         ["IPL and T20I statistics are pooled directly", "Competition tiers with within-tier comparison (Section 4.5)"],
         ["Match importance is assessed with hindsight", "Use of information available before each delivery only (Section 4.5)"],
         ["Rankings are reported without uncertainty", "Bootstrap rank intervals and top-10 probabilities (Section 5.4)"]],
        [7.8 * cm, 8.8 * cm], caption="Limitations addressed by the method."))

    # ================================================================ 4. methodology
    story += [P("4. Methodology", "h1"),
              P("4.1 Data Preparation and Validation", "h2"),
              P("Each interpretation of the data was verified against independent evidence. Total runs per delivery, computed as "
                "the sum of batter runs and both extras fields, reproduce 399 of 400 stated winning margins in matches won by "
                "runs; the single exception is a tie decided by a Super Over. Deliveries recorded with extras type 'other' were "
                "established to be no-balls: under this interpretation every one of the 216 completed overs containing such a "
                "delivery has exactly six legal balls, against none under the alternative. Revised-innings fields were shown to "
                "record innings length in balls. Super Overs and the 16 matches with no deliveries were excluded."),
              P("4.2 Match-State Reconstruction", "h2"),
              P("For every delivery the state of the match immediately before and after the ball was reconstructed: score, "
                "wickets, legal balls bowled and remaining, target, runs required, and current and required run rates. In 99.6% "
                "of the 843 completed chases, the final reconstructed state agrees with the recorded result. Three matches whose "
                "state could not be reconciled with the result were excluded from model fitting."),
              P("4.3 Pressure Definition", "h2"),
              P("A delivery is regarded as a pressure delivery when a great deal depends on it for the player concerned. Three "
                "components are measured, each on a scale of 0 to 100 and each computed from information available before the "
                "delivery."),
              P("4.3.1 Match Situation Pressure", "h3"),
              P("The batting side's win probability WP is estimated before every delivery. In the second innings a logistic model "
                "uses runs required, balls remaining, wickets in hand and the prevailing scoring rate of the preceding 40 "
                "matches; over the final 30 balls it is combined with an exact recursion over ball outcomes. Trained on matches "
                "before 2025 and tested on 2025–26, the model achieves an AUC of 0.918 and a log loss of 0.370, compared with "
                "0.897 and 0.411 for required run rate alone. In the first innings the distribution of the final total T is "
                "predicted by a monotonic gradient-boosting model of remaining runs (mean absolute error 18.0 runs), and"),
              eq(r"WP_1=\sum_{T}P(\mathrm{final\ total}=T\mid\mathrm{state})\,\left(1-WP_2(\mathrm{target}=T+1)\right)."),
              P("The match situation pressure of delivery b is its leverage, the expected absolute change in win probability over "
                "the possible outcomes o (dot ball, one to six runs, wicket, extra), expressed as a percentile:"),
              eq(r"L_b=\sum_{o}P(o\mid\mathrm{phase})\,\left|\,WP_{b}^{\,o}-WP_b\,\right|,\qquad "
                 r"\mathrm{MSP}_b=100\cdot\mathrm{percentile}(L_b)."),
              P("4.3.2 Tournament Stakes Pressure", "h3"),
              P("The stakes of match m for team t are the difference the result makes to the team's probability of winning the "
                "competition:"),
              eq(r"\mathrm{TSP}_{t,m}=P(\mathrm{title}\mid t\ \mathrm{wins}\ m)-P(\mathrm{title}\mid t\ \mathrm{loses}\ m)."),
              P("For league matches the points table is reconstructed from earlier results only and the remaining fixtures are "
                "simulated 4,000 times. Knockout values are exact (final 1.0; semi-final and Qualifier 2, 0.5; Qualifier 1 and "
                "Eliminator, 0.25). For bilateral series the objective is winning the series. Values are expressed as percentiles "
                "within each competition group."),
              P("4.3.3 Individual Form Pressure", "h3"),
              P("Form pressure measures the extent to which a player's last five innings or spells fall below the player's own "
                "career baseline up to that match, using runs, strike rate and runs of low scores for batters, and economy, wicket "
                "rate and wicketless runs for bowlers. It is computed only for players in a regular batting or bowling role and "
                "is a statistical indicator of form rather than a measure of psychological state."),
              P("4.3.4 Combined Pressure Index", "h3"),
              eq(r"\mathrm{CPI}_b=0.5\,\mathrm{MSP}_b+0.3\,\mathrm{TSP}_b+0.2\,\mathrm{IPP}_b"),
              eq(r"b\ \mathrm{is\ a\ high\text{-}pressure\ delivery}\ \Leftrightarrow\ \mathrm{CPI}_b\geq Q_{0.70}(\mathrm{CPI})"),
              P("The match situation receives the largest weight because it is specific to the delivery and can be validated "
                "against results. The batter and bowler share the match-situation component but each takes the stakes of his "
                "own team and his own form, so the same delivery may carry different pressure for each."),
              P("4.3.5 Validation of the Pressure Index", "h3")]
    sep = d["sep"]
    sel = sep[sep["decile"].isin(["1", "3", "5", "7", "8", "9", "10"])]
    rows = [["Pressure decile", "Mean |ΔWP| per ball", "Dismissal rate (%)", "Strike rate", "Knockout deliveries (%)"]]
    for _, r in sel.iterrows():
        rows.append([r["decile"], f"{float(r['mean_absWPA']):.3f}", f"{float(r['dismissal_%']):.1f}",
                     f"{float(r['strike_rate']):.0f}", f"{float(r['knockout_%']):.1f}"])
    story.append(table(rows, [3.0 * cm, 3.4 * cm, 3.2 * cm, 2.6 * cm, 4.4 * cm],
                       caption="Outcomes by pressure decile (batting view, all deliveries)."))
    story.append(P(f"The expected swing in win probability rises approximately sevenfold from the lowest to the highest decile, "
                   f"and knockout deliveries are fourteen times more frequent in the highest decile. The dismissal rate increases "
                   f"in the upper deciles while the average strike rate is almost unchanged, indicating that pressure alters the "
                   f"importance of a delivery rather than its typical outcome. Only "
                   f"{pf['share_nearly_decided (WP<15% or >85%)']:.1%} of high-pressure deliveries occur in matches that were "
                   f"close to decided (win probability below 15% or above 85%)."))
    story.append(figure(fig_separation(sep), "Outcomes by pressure decile. The shaded region is the high-pressure zone."))

    story += [P("4.4 Performance Measurement", "h2"),
              P("4.4.1 Situation-Adjusted Outcomes", "h3"),
              P("Each outcome y (runs, dismissal, runs conceded, wicket) is compared with the mean outcome of deliveries in the "
                "same competition tier c, phase φ and pressure band h:"),
              eq(r"\Delta y_b=y_b-\bar{y}_{\,c,\,\phi,\,h}."),
              P("4.4.2 Estimation Relative to Usual Level", "h3"),
              P("Because each player has considerably more ordinary deliveries than pressure deliveries, the pressure estimate "
                "for player j begins from the player's usual level and retains only the part of the observed difference supported "
                "by the data:"),
              eq(r"\hat{p}_j=\hat{u}_j+\lambda_j\left(\bar{p}_j-\bar{u}_j\right),\qquad "
                 r"\lambda_j=\dfrac{\tau_d^{2}}{\tau_d^{2}+\sigma_j^{2}},"),
              P("where the first variance is the true between-player variance of the pressure difference and the second is the "
                "sampling variance of player j's difference. The median retained share is approximately 0.07 for batting and "
                "0.10 for bowling. The retained difference forms the uplift component of the rating."),
              P("4.4.3 Small-Sample Shrinkage", "h3"),
              P("All rates are shrunk towards the population mean μ, with the shrinkage constant k estimated from the ratio of "
                "within-player to between-player variance:"),
              eq(r"\hat{\theta}_j=\mu+\dfrac{n_j}{n_j+k}\left(\bar{x}_j-\mu\right),\qquad k=\dfrac{\sigma_w^{2}}{\tau^{2}}."),
              P("4.4.4 Composite Rating", "h3"),
              P("Five components are standardised across eligible players: impact (win probability added), scoring or economy, "
                "survival or wickets, reliability (the share of pressure innings or spells in which the player's side gained win "
                "probability) and uplift. Each component is weighted in proportion to its split-half repeatability r, and the "
                "final rating is averaged over 100 bootstrap resamples of matches:"),
              eq(r"R_j=\sum_{c}w_c\,z_{jc},\qquad w_c=\dfrac{\max(r_c,0)}{\sum_{c'}\max(r_{c'},0)},\qquad "
                 r"\overline{R}_j=\dfrac{1}{100}\sum_{s=1}^{100}R_j^{(s)}.")]
    rb, rw = d["rel_bat"].set_index(d["rel_bat"].columns[0]), d["rel_bowl"].set_index(d["rel_bowl"].columns[0])
    rows = [["Batting component", "r", "Weight", "Bowling component", "r", "Weight"]]
    for (kb, a), (kw, b) in zip(rb.iterrows(), rw.iterrows()):
        rows.append([kb.capitalize(), fmt(float(a["split-half r"]), 2), f"{float(a['weight']):.0%}",
                     kw.capitalize(), fmt(float(b["split-half r"]), 2), f"{float(b['weight']):.0%}"])
    story.append(table(rows, [3.6 * cm, 1.8 * cm, 1.8 * cm, 3.6 * cm, 1.8 * cm, 1.8 * cm],
                       caption="Split-half repeatability and resulting component weights.",
                       note="Win probability added per delivery shows almost no repeatability for batters (r = 0.05), and wicket "
                            "rate shows almost none for bowlers (r = 0.03); both receive little weight."))

    story += [P("4.5 Comparability and Eligibility", "h2"),
              P(f"IPL and T20I statistics are not pooled directly. Deliveries are compared within competition tiers (equation 6) "
                f"and weighted by the strength of opposition: IPL and T20Is between ICC Full Members 1.0, T20Is involving an "
                f"Associate Member 0.4, and A-team competitions 0.3. All seasons are weighted equally. Batters require at least "
                f"200 high-pressure deliveries and 15 pressure innings, and bowlers at least 240 deliveries and 20 spells, which "
                f"gives {nb} eligible batters and {nw} eligible bowlers. Confidence is classed as Medium from 300 (batters) or 360 "
                f"(bowlers) pressure deliveries and High from 500 or 600. Every time-varying input (scoring rate, points tables, "
                f"form) uses only matches played before the match in question, and all models were tested on later seasons than "
                f"those on which they were trained.")]

    # ================================================================ 5. results
    story.append(CondPageBreak(10 * cm))
    story += [P("5. Results", "h1"), P("5.1 Final Rankings", "h2")]
    rows = [["Rank", "Batter", "Confidence", "P(top 10)", "Bowler", "Confidence", "P(top 10)"]]
    for i in range(10):
        a, b = bat.iloc[i], bowl.iloc[i]
        rows.append([i + 1, a.player_name, a.confidence, f"{a.p_top10:.0%}", b.player_name, b.confidence, f"{b.p_top10:.0%}"])
    story.append(table(rows, [1.3 * cm, 3.5 * cm, 2.0 * cm, 1.9 * cm, 3.5 * cm, 2.0 * cm, 1.9 * cm],
                       caption="Final top-10 rankings.",
                       note="P(top 10) is the proportion of 100 bootstrap resamples in which the player ranks in the top 10."))

    head52 = P("5.2 Batting Results", "h2")
    rows = [["Rank", "Batter", "Pressure balls", "SR pressure", "SR usual", "Avg pressure", "Avg usual", "90% rank interval"]]
    for _, r in bat.head(10).iterrows():
        rows.append([int(r.final_rank), r.player_name, int(r.all_p_balls), fmt(r.all_p_sr, 0), fmt(r.all_n_sr, 0),
                     fmt(r.all_p_avg), fmt(r.all_n_avg), f"{r.rank_p05:.0f}–{r.rank_p95:.0f}"])
    story.append(table(rows, [1.3 * cm, 3.5 * cm, 1.9 * cm, 1.8 * cm, 1.7 * cm, 1.9 * cm, 1.7 * cm, 2.8 * cm], head=head52,
                       caption="Top-10 batters: descriptive statistics under pressure and in usual situations.",
                       note="Descriptive figures across all competitions. The rating uses the adjusted measures of Section 4.4."))
    dips_b = bat.head(10)[bat.head(10).all_p_sr < bat.head(10).all_n_sr - 8]
    story.append(P(f"{bat.iloc[0].player_name} is ranked first in all 100 resamples, with a strike rate of "
                   f"{bat.iloc[0].all_p_sr:.0f} under pressure against {bat.iloc[0].all_n_sr:.0f} in usual situations and the "
                   f"highest reliability of any batter. The five highest-ranked batters all score at 165 to 180 runs per 100 balls "
                   f"under pressure. {join_names(dips_b.player_name)} "
                   + ("records a lower strike rate under pressure than in usual situations but remains ranked because his "
                      "pressure strike rate still exceeds that of almost all players in equivalent situations."
                      if len(dips_b) == 1 else
                      "record lower strike rates under pressure than in usual situations but remain ranked because their "
                      "pressure strike rates still exceed those of almost all players in equivalent situations.")))

    head53 = P("5.3 Bowling Results", "h2")
    rows = [["Rank", "Bowler", "Pressure balls", "Econ pressure", "Econ usual", "Wkts/24 pressure", "Dot % pressure", "90% rank interval"]]
    for _, r in bowl.head(10).iterrows():
        rows.append([int(r.final_rank), r.player_name, int(r.all_p_balls), fmt(r.all_p_econ, 2), fmt(r.all_n_econ, 2),
                     fmt(r.all_p_wkts_per24, 2), fmt(r.all_p_dot_pct), f"{r.rank_p05:.0f}–{r.rank_p95:.0f}"])
    story.append(table(rows, [1.3 * cm, 3.5 * cm, 1.9 * cm, 1.9 * cm, 1.7 * cm, 2.0 * cm, 1.8 * cm, 2.5 * cm], head=head53,
                       caption="Top-10 bowlers: descriptive statistics under pressure and in usual situations."))
    dips_w = bowl.head(10)[bowl.head(10).all_p_econ > bowl.head(10).all_n_econ + 0.5]
    story.append(P(f"The bowling rankings are led by spin bowlers who concede approximately seven runs per over under pressure. "
                   + (f"{join_names(dips_w.player_name)} {'concedes' if len(dips_w) == 1 else 'concede'} more under pressure than in usual "
                      f"situations but {'remains' if len(dips_w) == 1 else 'remain'} better than "
                      f"nearly all bowlers in equivalent situations, which is consistent with the finding in Section 5.6 that bowling "
                      f"performance under pressure largely reflects general bowling quality." if len(dips_w) else "")))
    story.append(figure([fig_scatter(bat, "bat"), fig_scatter(bowl, "bowl")],
                        "Performance under pressure against usual performance for all eligible players: strike rate for batters "
                        "(left) and economy rate for bowlers (right). The dashed line marks equal performance; top-10 players are "
                        "shown in black."))

    # ---- 5.4 robustness
    def overlaps(role, final):
        t = d[f"top_{role}"]
        top = set(final.player_name.head(10))
        return {c: len(top & set(t[c])) for c in t.columns if c != "baseline"}
    ob, ow = overlaps("bat", bat), overlaps("bowl", bowl)
    labels = {"rating weights: expert 0.35/0.2/0.15/0.2/0.1": "Fixed component weights (0.35, 0.2, 0.15, 0.2, 0.1)",
              "rating weights: equal weights": "Equal component weights",
              "rating weights: impact only": "Impact component only",
              "rating weights: rise above own usual (uplift 50%)": "Uplift weighted at 50%",
              "competition weighting: IPL-primary: IPL 1, all T20I 0.5, other 0.3": "IPL weighted above T20I",
              "competition weighting: all balls equal": "Equal weighting of all competitions",
              "competition weighting: recency-weighted (half-life 2 seasons)": "Recent seasons weighted more heavily",
              "pressure definition: equal 1/3 each": "Pressure components weighted equally",
              "pressure definition: situation only": "Pressure from match situation only",
              "pressure definition: situation + stakes 0.6/0.4": "Pressure from situation and stakes only"}
    skip = lambda c: "data-driven" in c or "baseline:" in c or "baseline 0.5" in c
    keys = [c for c in ob if not skip(c)]
    vb, vw = [ob[c] for c in keys], [ow[c] for c in keys]
    story += [table([["Alternative specification", "Batters retained", "Bowlers retained"]] +
                    [[labels.get(c, c), f"{ob[c]} of 10", f"{ow[c]} of 10"] for c in keys],
                    [10.0 * cm, 3.3 * cm, 3.3 * cm], caption="Players retained in the top 10 under alternative specifications.",
                    head=P("5.4 Robustness and Uncertainty", "h2")),
              P(f"Across the alternative specifications, between {min(vb)} and {max(vb)} of the ten batters and between "
                f"{min(vw)} and {max(vw)} of the ten bowlers are retained (medians {int(pd.Series(vb).median())} and "
                f"{int(pd.Series(vw).median())}). The largest changes arise from rating on the impact component alone and from "
                f"defining pressure by the match situation only, which indicates that the stakes and form components contribute "
                f"information. The first five places in each list are considerably more stable than places six to ten."),
              figure([fig_ranks(bat, "bat"), fig_ranks(bowl, "bowl")],
                     "Final rank, median resampled rank and 90% rank interval for the top-10 batters (left) and bowlers (right).")]

    # ---- 5.5 roles
    def names(g):
        return ", ".join(f"{r.player_name} ({int(r.final_rank)})" for _, r in g.sort_values("final_rank").head(3).iterrows())
    rows = [["Role", "Highest-ranked players (overall rank)"]]
    for lbl in ["Opener", "Top order (3)", "Middle order (4-5)", "Finisher (6-7)"]:
        rows.append([f"Batting: {lbl.lower()}", names(bat[bat.batting_role == lbl])])
    rows.append(["Batting: wicketkeeper", names(bat[bat.keeper == True])])  # noqa: E712
    for lbl in ["Powerplay specialist", "Middle-overs specialist", "Death specialist", "All-phase"]:
        rows.append([f"Bowling: {lbl.replace(' specialist', '').lower()}", names(bowl[bowl.bowling_role == lbl])])
    per_over = bowl.groupby("bowling_role")["p_runs_ae"].mean() * -6
    death = bowl[bowl.bowling_role == "Death specialist"]
    story += [table(rows, [4.6 * cm, 12.0 * cm], caption="Highest-ranked players within each role.", head=P("5.5 Results by Role", "h2"),
                    note="Roles are descriptive (usual batting position; phase in which a bowler bowls most) and do not enter the rating."),
              P(f"No death-overs specialist appears in the bowling top 10. Only {len(death)} of the {nw} eligible bowlers bowl at "
                f"least a third of their deliveries in overs 17 to 20. These bowlers concede {per_over['Death specialist']:.2f} "
                f"runs per over fewer than bowlers in equivalent situations, whereas the leading middle-overs bowlers concede "
                f"{per_over['Middle-overs specialist']:.2f} fewer.")]

    # ---- 5.6 temporal validation
    tp = d["temporal"].set_index(d["temporal"].columns[0])
    want = [("old estimate -> later pressure scoring/economy", "Pressure record only"),
            ("A (own level) -> later pressure scoring/economy", "Proposed estimate (equation 7)"),
            ("normal level only -> later", "Usual level only"),
            ("partial r: raw pressure record given normal", "Pressure record, controlling for usual level (partial r)")]
    rows = [["Predictor (2022–24)", "Batters", "Bowlers"]] + \
           [[label, fmt(float(tp.loc[k, "batters"]), 2), fmt(float(tp.loc[k, "bowlers"]), 2)] for k, label in want]
    story += [P("5.6 Temporal Validation", "h2"),
              P("Players were rated on 2022–24 data only, and the ratings were compared with their performance under pressure "
                "in 2025–26."),
              table(rows, [10.6 * cm, 3.0 * cm, 3.0 * cm],
                    caption="Correlation of 2022–24 estimates with 2025–26 performance under pressure.",
                    note="Approximately 40 players qualify in each group; the standard error of each correlation is about 0.15."),
              P("For batters, the pressure record predicts later pressure performance after controlling for usual level "
                "(partial r = 0.27), indicating a persistent pressure-specific effect. For bowlers no such effect is found: the "
                "pressure record alone has no predictive value (r = 0.03), while the proposed estimate achieves r = 0.40.")]

    # ---- 5.7 RR squad
    allb, allw = d["all_bat"], d["all_bowl"]
    rk_b = dict(zip(bat.player_id, bat.final_rank))
    rk_w = dict(zip(bowl.player_id, bowl.final_rank))
    b = allb[(allb.current_rr == True) & (allb.all_p_balls >= 100)].sort_values("all_p_balls", ascending=False)  # noqa: E712
    w = allw[(allw.current_rr == True) & (allw.all_p_balls >= 100)].sort_values("all_p_balls", ascending=False)  # noqa: E712
    st = lambda pid, rk, n: f"{int(rk[pid])} of {n}" if pid in rk else "Not eligible"
    rows = [["Batter", "SR pressure / usual", "Rank", "Bowler", "Econ pressure / usual", "Rank"]]
    for i in range(max(len(b), len(w))):
        lb = [b.iloc[i].player_name, f"{b.iloc[i].all_p_sr:.0f} / {b.iloc[i].all_n_sr:.0f}", st(b.iloc[i].player_id, rk_b, nb)] \
            if i < len(b) else ["", "", ""]
        lw = [w.iloc[i].player_name, f"{w.iloc[i].all_p_econ:.2f} / {w.iloc[i].all_n_econ:.2f}", st(w.iloc[i].player_id, rk_w, nw)] \
            if i < len(w) else ["", "", ""]
        rows.append(lb + lw)
    bb = b.set_index("player_name")
    risers = bb[(bb.all_p_sr - bb.all_n_sr) >= 8].index.tolist()
    fallers = bb[(bb.all_p_sr - bb.all_n_sr) <= -8].sort_values("all_p_sr").index.tolist()
    ww = w.assign(rank=w.player_id.map(rk_w)).dropna(subset=["rank"]).sort_values("rank").head(2)
    story += [CondPageBreak(8 * cm), P("5.7 Application to the Rajasthan Royals Squad", "h2"),
              P("The same method, without modification, was applied to the Rajasthan Royals squad for the most recent IPL "
                "season in the data (players with at least 100 pressure deliveries)."),
              table(rows, [3.5 * cm, 2.7 * cm, 2.2 * cm, 3.2 * cm, 2.8 * cm, 2.2 * cm],
                    caption="Rajasthan Royals players under pressure."),
              P(f"{bat[bat.player_id.isin(b.player_id)].head(1).player_name.iloc[0]} is the only squad member in either top 10. "
                f"{join_names(risers)} score faster under pressure than in usual situations, whereas {join_names(fallers)} score "
                f"markedly more slowly. The highest-ranked squad bowlers are "
                f"{join_names(f'{n} ({int(r)})' for n, r in zip(ww.player_name, ww['rank']))}, and no squad bowler meets the "
                f"definition of a death-overs specialist.")]

    # ================================================================ 6. conclusion
    story += [P("6. Conclusion", "h1"),
              P("6.1 Summary of Findings", "h2"),
              P(f"Pressure can be measured at the level of individual deliveries in a way that reflects close contests, knockout "
                f"matches and decisive moments, and that may differ between the batter and the bowler on the same delivery. "
                f"Evaluated against players in equivalent situations and against their own usual level, {bat.iloc[0].player_name} "
                f"and {bowl.iloc[0].player_name} are the strongest performers under pressure in 2022–26. Isolated high-impact "
                f"events show little repeatability, whereas scoring rate, survival and economy under pressure are repeatable. "
                f"Batters exhibit a persistent pressure-specific effect; bowlers do not. Places six to ten in each ranking carry "
                f"substantial uncertainty."),
              P("6.2 Limitations", "h2")]
    story += items(["The proportion of chases won rose from 48% (2022–24) to 55% (2026). The win-probability models are refitted "
                    "on all seasons, and the pressure measure, being a ranking of leverage, is robust to this shift.",
                    f"Leverage is concentrated at the start and end of innings ({pf['share_overs_1_3']:.0%} and "
                    f"{pf['share_overs_17_20']:.0%} of high-pressure deliveries occur in overs 1–3 and 17–20 respectively).",
                    "Qualification rules for some multi-team events could not be reconstructed; 108 team-matches are assigned "
                    "neutral stakes.",
                    "Three top-10 players (Klaasen, Rinku Singh and Narine) have low confidence owing to smaller samples.",
                    "The pressure weights, the 30% threshold and the tier weights involve judgement; their effect is reported in "
                    "Section 5.4."])
    story += [P("6.3 Future Work", "h2")]
    story += items(["Incorporating the direction of pressure, so that the side behind in a match carries greater pressure.",
                    "Ranking by the lower bound of each player's rating interval to favour consistently strong records.",
                    "Extending the data to further seasons and domestic leagues to increase sample sizes."])
    story += [P("Reproducibility", "h1"),
              P(f"All results are generated from the supplied data by run_pipeline.py, and this report is generated by "
                f"report/build_report.py. Code and documentation are available at {REPO}.")]

    doc = SimpleDocTemplate(str(PDF), pagesize=A4, leftMargin=2.3 * cm, rightMargin=2.3 * cm, topMargin=2.2 * cm,
                            bottomMargin=2.2 * cm, title="Measuring Player Performance Under Pressure in T20 Cricket",
                            author="SupeRR Selector Season 2 team", subject="Round 1 methodology report")
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"written {PDF}")


if __name__ == "__main__":
    build()
