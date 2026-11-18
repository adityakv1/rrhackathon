# SupeRR Selector Season 2 — Performance Under Pressure

A data-driven system that measures how batters and bowlers perform in **high-pressure match situations compared with their usual level**, and ranks the players who deliver most consistently when it matters. It uses IPL and T20I ball-by-ball data from 2022 onwards.

**Outputs:** two ranked top-10 lists (batters, bowlers) plus all the evidence behind them.

---

## Quick start

```bash
pip install -r requirements.txt
python run_pipeline.py                      # full run, ~12 minutes
python run_pipeline.py --skip validate_rankings   # skip the slow bootstrap, ~7 minutes
python run_pipeline.py --from cup           # re-rank only (needs earlier outputs)
```

Raw CSVs go in `data/raw/`. Every result is regenerated from them. Nothing is entered by hand.

**Results:**
- `outputs/rankings_batting.csv` and `outputs/rankings_bowling.csv`: every eligible player with rank, rating and supporting stats.
- `outputs/cup_rankings_report.md`: top 10s, rating weights, sensitivity analysis.
- `outputs/validation_rankings_report.md` and `outputs/figures/`: evidence and charts.

---

## How it works (one paragraph per step)

1. **Clean and validate the data** (`src/data.py`, `src/validate.py`). Every assumption is checked against independent evidence: the runs formula reproduces 399/400 stated match margins, `other` extras are proven to be no-balls from over structure, and the revised-overs columns are proven to be in balls.
2. **Rebuild the match situation for every ball** (`src/match_state.py`): score, wickets, balls left, target, required and current run rate, before and after each of ~201,000 balls. 99.6% of chases end in a state that reproduces the recorded result.
3. **Match situation pressure** (`src/pressure_msp.py`, `src/pressure_msp1.py`). A win-probability model (AUC 0.918 on unseen 2025–26 games) gives each side's chance of winning before every ball.
   - **Leverage** is how much that chance could swing on the ball. It is the core of "pressure", and the same situation applies to the batter and the bowler.
   - **WPA** (win probability added) is each player's credit for the ball.
4. **Tournament stakes** (`src/pressure_tsp.py`): P(win the competition | win this match) − P(… | lose it), from points tables rebuilt using earlier results only. A final scores 1.0 and a dead rubber 0.
5. **Form pressure** (`src/pressure_ipp.py`): how far a player's recent output sits below their own baseline, from past matches only. A statistical proxy, not a claim about psychology.
6. **Rate and rank** (`src/cup.py`):
   - Combined pressure = 0.5 situation + 0.3 stakes + 0.2 form. The top 30% of balls are "high pressure".
   - Players are compared with peers on balls of the same competition tier, phase and pressure level, and with their own usual level.
   - Small samples are shrunk (empirical Bayes), and rating components are weighted by how repeatable they are.
7. **Validate** (`src/validate_rankings.py`): does pressure separate situations, how certain is each rank (match bootstrap), and is pressure performance stable over time?

Full detail: [`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md) (every function), [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) (every column), [`outputs/METHODOLOGY_NOTES.md`](outputs/METHODOLOGY_NOTES.md) (every decision and its evidence).

---

## Project layout

```text
run_pipeline.py            single entry point (see --help)
requirements.txt
src/
  config.py                paths, cricket constants (legal ball, credited wickets, phases)
  data.py                  load + clean raw CSVs
  validate.py              data-assumption tests
  match_state.py           per-ball match situation
  pressure_msp.py          chase win probability, leverage, WPA (innings 2)
  pressure_msp1.py         first-innings win probability; combined MSP table
  pressure_tsp.py          tournament stakes
  pressure_ipp.py          form pressure
  cup.py                   combined pressure, player ratings, rankings, sensitivity
  validate_rankings.py     separation, bootstrap, temporal stability, charts
data/
  raw/                     supplied CSVs (input; never modified)
  processed/               parquet tables written by the pipeline
outputs/                   reports, rankings, figures, methodology log
docs/                      code guide, data dictionary
notebooks/                 original exploration (load.py) — kept as the record, not used by the pipeline
```

## Design principles

- **No future information.** Every pressure input (scoring environment, venue par, standings, form) uses only matches before the one being scored. Models are tested on later seasons than they were trained on.
- **Everything is tested, not assumed.** Each data definition and modelling choice has a check and a report in `outputs/`.
- **Fair comparisons.** IPL and T20I are never mixed raw. Players are measured against same-situation peers within a competition tier.
- **Honest uncertainty.** Every rank comes with a confidence tier and a bootstrap probability of making the top 10. Limitations are written down in `outputs/METHODOLOGY_NOTES.md`.
