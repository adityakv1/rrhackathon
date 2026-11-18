# Code Guide — every function, in pipeline order

The pipeline is a chain of scripts. Each one reads the previous step's output from `data/processed/`, adds something, and writes a report to `outputs/`.

```
raw CSVs
  │  src/data.py            clean deliveries + matches                     → deliveries.parquet, matches.parquet
  │  src/validate.py        prove the data assumptions                     → outputs/validation_report.md
  │  src/match_state.py     score/wickets/balls/target before & after each ball → match_state.parquet
  │  src/pressure_msp.py    chase win probability, leverage, WPA (innings 2) → pressure_msp_inn2.parquet
  │  src/pressure_msp1.py   first-innings win probability; joins both innings → pressure_msp.parquet
  │  src/pressure_tsp.py    tournament stakes per team per match            → pressure_tsp.parquet
  │  src/pressure_ipp.py    form pressure per player per match              → pressure_ipp.parquet
  │  src/cup.py             combine pressures, rate players, rank           → outputs/rankings_*.csv
  ▼  src/validate_rankings.py  evidence: separation, bootstrap, stability, charts → outputs/figures/
```

Run everything with `python run_pipeline.py` (see `--help` for `--from`, `--only` and `--skip`). It runs `src.validate`, `src.match_state`, `src.pressure_msp`, `src.pressure_msp1`, `src.pressure_tsp`, `src.pressure_ipp`, `src.cup` and `src.validate_rankings` in that order. Column meanings are in [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md).

Two words used throughout:
- **Legal ball:** not a wide and not a no-ball. It counts towards the 120 balls of an innings.
- **WP (win probability):** the chance the batting side wins, from 0 to 1.

---

## `src/config.py` — settings (no functions)
All shared constants live here:
- **Paths:** `RAW`, `PROCESSED`, `OUTPUTS`.
- **Innings:** `REGULAR_INNINGS = (1, 2)`, because Super Overs are innings 3–4. `T20_MAX_BALLS = 120`.
- **`BOWLER_WICKETS`:** the dismissal types credited to the bowler (Caught, Bowled, LBW, Stump, Hit Wicket). Run-outs and similar are not.
- **`NOT_BATTER_DISMISSALS`:** Retire Out, which does not count against a batting average.
- **`OTHER_AS_NO_BALL = True`:** the `other` extras are treated as no-balls. `validate.py` proves this.
- **`PHASES`:** Powerplay 1–6, Middle 7–16, Death 17–20.

---

## `src/data.py` — load and clean

| Function | What it does |
|---|---|
| `load_raw()` | Reads all six CSVs into a dict of DataFrames. |
| `classify_competitions(comps)` | Labels each competition **IPL** (name contains "IPL"), **T20I** (format is T20I) or **Other T20**. |
| `build_matches(raw)` | Joins each match to its competition name, season and group, and turns dates into real dates. |
| `build_deliveries(raw, other_as_no_ball)` | The core cleaning step, described below. |
| `build_all(save)` | Runs the three functions above and saves `deliveries.parquet` and `matches.parquet`. |

What `build_deliveries` does:
1. Keeps innings 1–2 only, so Super Overs are excluded.
2. Fills missing run values with 0 and sorts balls in order.
3. Creates these columns:
   - `total_runs` = runs + extras1_runs + extras_2_runs (validated against match results).
   - `batter_runs` = runs (bat runs only).
   - `is_wide`, `is_no_ball` (Overstep, plus `other` if the flag is on), `legal_ball` (neither), `ball_faced` (not a wide; a no-ball is still faced).
   - `bowler_runs` = total runs, but on byes, leg-byes and penalty only the bat runs count, because those extras are not the bowler's fault.
   - `bowler_wicket` = a wicket of a credited type. `batter_out` = a wicket that is not Retire Out.
4. Attaches the competition, season and date to every ball.

---

## `src/validate.py` — prove the data assumptions

| Function | What it does |
|---|---|
| `log(s)` | Prints a line and also stores it for the report file. |
| `parse_result(result)` | Reads text like "India won by 7 wickets (DLS)" and returns (`"wickets"`, 7, DLS=True). |
| `innings_summary(d)` | For every match and innings: total runs, wickets, legal balls, deliveries. One row per match. |
| `check_runs(matches, d)` | **Test 1.** For wins by runs: does first total − second total equal the stated margin? For wins by wickets: does 10 − wickets lost equal the margin? Proves the runs formula (99.8% match; the only miss is a Super Over tie). |
| `check_other_extras(raw)` | **Test 2.** Builds the data twice, with `other` as a legal ball and as a no-ball, then counts how many completed overs containing an `other` ball have exactly 6 legal balls (0% vs 100%). Proves `other` is a no-ball. |
| `check_revised(matches, d)` | **Test 3.** For rain-shortened matches: no innings ever exceeds the revised value read as balls, and reading it as overs gives impossible 30–114-over innings. Also shows `revised_target` is the runs-to-win target. |
| `check_structure(matches, d)` | **Test 4.** Duplicate balls, innings with more than 120 legal balls or 10 wickets, one-innings matches, the IPL competition list, stages. |
| `main()` | Runs all four tests and writes `outputs/validation_report.md`. |

---

## `src/match_state.py` — the situation before and after every ball

| Function | What it does |
|---|---|
| `match_outcomes(matches)` | Classifies each result as `win`, `tie` (including Super Over-decided games, which are ties in regular play) or `no_result`, and flags DLS. |
| `innings_limits(matches, deliveries)` | The legal-ball limit of each innings. Innings 1 uses the revised value, or, if a decided match's first innings stopped early without being all out, the balls actually bowled (rain cut, unrecorded), or else 120. Innings 2 uses its revised value or the innings-1 limit. Flags `limit_inferred`. |
| `build_match_state(deliveries, matches)` | **The main table**, described below. |
| `validate_state(s)` | Checks that every chase's final state agrees with the recorded result (99.6%). Also reports how innings ended and lists the unreliable matches. |
| `main()` | Builds, saves `match_state.parquet` and writes `outputs/match_state_validation.md`. |

What `build_match_state` produces:
- **After each ball:** running totals of score, wickets and legal balls within each innings.
- **Before each ball:** after-value minus this ball. This is the situation the player actually faced.
- **Situation columns:** `target` (revised target, or first-innings total + 1), `balls_remaining`, `wickets_in_hand`, `runs_required`, `current_run_rate`, `required_run_rate`, `innings_progress`, `innings_phase`.
- **Result label:** `batting_team_won` (1, 0, 0.5 for a tie). It is used only to check and fit models, **never** as a pressure input.
- **`state_reliable`:** False for the 3 matches whose final state cannot reproduce their result.

---

## `src/pressure_msp.py` — chase win probability and ball-level pressure (innings 2)

| Function / class | What it does |
|---|---|
| `scoring_environment(s)` | For every match: the average run rate of the **previous 40 matches** in the same competition group. Only earlier dates are used (same-day games can't see each other). Captures scoring inflation without leakage. |
| `features(R, B, W, is_ipl, env)` | Turns runs required (R), balls left (B) and wickets in hand (W) into model inputs: required rate (also relative to the scoring environment), log of runs and balls, wickets and wickets², required rate × wickets lost, runs per remaining wicket, and an IPL flag. |
| `ChaseWinModel` | Logistic regression on those features. |
| `ChaseWinModel.fit(df)` | Trains it. |
| `ChaseWinModel.predict(R, B, W, ...)` | Returns WP, with the cricket rules forced: target reached gives 1, and out of balls or wickets gives 0 (0.5 if exactly 1 short, a tie). |
| `ChaseWinModel.coefficients()` | Shows how each feature pushes WP, for the report. |
| `EndgameDP` | An **exact** calculation for the last few balls. WP(R,B,W) = Σ over outcomes (dot, 1, 2, 3, 4, 6, wicket, extra) of P(outcome) × WP(state after it), computed recursively with caching. A smooth logistic curve is wrong at the very end (it gave 6 off 1 about 1%; reality is about 9%). |
| `EndgameDP.wp` / `.predict` | One state / many states. |
| `HybridWP` | Uses `EndgameDP` for the last 6 balls, blends linearly into the logistic model by 30 balls left, and uses the logistic model before that. |
| `outcome_probs(train)` | How often each ball outcome happens in each phase, from training data. Used as weights for the endgame recursion and for leverage. |
| `chase_frame(s)` | Second-innings balls with R, B, W, IPL flag, environment and the result label. |
| `evaluate(pred, test, name)` | Log loss, Brier score and AUC of a model on test data. |
| `calibration(model, t)` | Predicted vs actual chase win rate in 10 probability bands. |
| `score_balls(c, model, probs, mean_lev)` | **Per-ball pressure**, described below. |
| `main()` | Trains on games **before 2025**, tests on 2025–26 against baselines, then refits on all data, scores every chase ball, runs sanity checks and writes the report. |

What `score_balls` computes for every chase ball:
- `wp_before`, `wp_after`, and `wpa` = after − before. WPA is the batter's credit; the bowler's credit is the negative.
- `leverage`: the expected size of the WP swing on this ball, Σ P(outcome) × |WP(after outcome) − WP(before)|. This is "how much is riding on this ball".
- `leverage_index`: leverage ÷ the average. `msp`: leverage as a 0–100 percentile.

---

## `src/pressure_msp1.py` — first-innings win probability; join both innings

| Function / class | What it does |
|---|---|
| `venue_run_rate(s, env)` | Run rate at the venue in **earlier** matches, pulled towards the scoring environment when the venue has few games (5 games of weight). |
| `first_innings_frame(s)` | First-innings balls with the environment, venue rate, IPL flag, current run rate, final total, whether the innings ran its natural course, and `remaining_runs` (the training target). |
| `RemainingRuns` | Gradient boosting that predicts the runs still to come from balls left, wickets in hand, environment, venue rate, current run rate and IPL flag. **Monotonic constraints:** more balls or wickets can never predict fewer runs. |
| `RemainingRuns.fit` | Trains the model and measures the spread of errors by balls left. |
| `RemainingRuns.mean` / `.sd` | Predicted runs to come, and how uncertain that is (shrinks to 0 at the end). |
| `FirstInningsWP` | WP of the side batting first. |
| `FirstInningsWP.defend_curve(limit, ...)` | For every final total T from 0 to 330: 1 − chase WP at the start of a chase for T+1. "If we post T, how likely are we to win?" |
| `FirstInningsWP.wp(score, balls, wkts, X, curve)` | Builds a probability distribution of the final total (normal, centred on score + predicted runs to come, never below the current score) and multiplies it by the defend curve. Vectorised per match. |
| `score_innings1(f, wpm, probs)` | Per match: WP before and after each ball, and leverage (the same expected-swing formula as the chase). Then WPA. |
| `wp_metrics(y, p, name)` | Log loss, Brier score and AUC. |
| `main()` | Out-of-time tests (runs-to-come error against baselines; WP accuracy by stage), refits on all data, then **combines both innings into one table**, where `msp` is a 0–100 percentile on one scale for every ball. Also checks the two innings join up (mean gap 0.002). |

---

## `src/pressure_tsp.py` — tournament stakes

| Function | What it does |
|---|---|
| `match_results(matches)` | Adds a `shared` flag for no result or abandoned (1 point each). A Super Over winner keeps the win, as in the IPL table. |
| `net_run_rate_before(state, matches)` | Each team's net run rate in the competition using only **earlier** matches. All-out counts as the full overs, as in the real NRR rule. Used to break ties on points. |
| `title_probability(points, tiebreak, rank_value, split_ties)` | Takes simulated final points tables (simulations × teams), ranks them, and converts each rank into P(title) using the format, e.g. IPL: ranks 1–2 → 0.375, ranks 3–4 → 0.125. For bilateral series a tie on points shares the series. |
| `league_stakes(comp, nrr, rank_value, split_ties, seed)` | For each league game in order: table from earlier results only, the remaining fixtures simulated 4,000 times as coin flips, run twice (this team wins vs loses). **TSP = P(title \| win) − P(title \| loss)** for each of the two teams. |
| `knockout_value(stage, order, fmt)` | Exact stakes for knockouts: Final 1.0, Semi-final 0.5, Eliminator 0.25, Qualifier 1 0.25, Qualifier 2 0.5. |
| `competition_format(g)` | Detects the format: IPL, bilateral series, round robin (with or without a final), or knockouts-only (the Asia Cup style, whose group rules are unknown). |
| `main()` | Runs each competition with its format, flags stages it can't model (`structure_unknown`) and saves `pressure_tsp.parquet`. |
| `report(tsp)` | Coverage, how stakes spread through an IPL season, knockouts, the highest-stakes games, RR examples and bilateral series patterns. |

---

## `src/pressure_ipp.py` — form pressure (a proxy, not psychology)

| Function | What it does |
|---|---|
| `batting_innings(s)` | One row per batter per innings: runs, balls, out or not, batting position. Includes batters run out without facing a ball. |
| `bowling_matches(s)` | One row per bowler per match innings: runs conceded, legal balls, wickets. |
| `prior_rolling_sum(g, window)` | Sum over a player's **previous** innings only (shifted by one), over the whole career so far or the last `window` innings. This is what prevents leakage. |
| `streak_before(flag, player)` | How many consecutive previous innings met a condition (e.g. low scores) right before this one. |
| `to_pct(x)` | Converts to a 0–100 percentile. |
| `batting_ipp(b)` | Baseline runs and strike rate (career to date, pulled towards the population average by 10 innings of weight), last-5 runs and strike rate, `runs_drop`, `sr_drop` and `low_streak` (innings below half the baseline). Only players who usually bat in the top 7. |
| `bowling_ipp(w)` | Baseline economy and wicket rate (pulled towards the population average), last-5 economy and wickets, `econ_rise`, `wkt_drop` and `dry_streak` (matches without a wicket). Only genuine bowlers (12+ balls a match usually, 24+ in the recent window). |
| `finish(df, comps, role, role_ok)` | Turns each component into a percentile, averages them and converts the result to a 0–100 percentile `ipp`. Flags `insufficient_history` (fewer than 3 previous innings) or `not_role_player`. |
| `report(bat, bowl)` | Coverage, how the components relate, what happened in the match by form band (form does not predict the next batting innings), and the biggest slumps. |
| `main()` | Saves `pressure_ipp.parquet` and writes the report. |

---

## `src/cup.py` — combine pressures, rate players, rank

**Setup**

| Function | What it does |
|---|---|
| `load()` | Joins every ball (reliable matches only) to its MSP and WPA, the batting and bowling teams' TSP (as a percentile within the competition group), and the striker's batting IPP and bowler's bowling IPP. Adds `striker_out`, the competition `tier` and ball weights. |
| `competition_tier(s)` | IPL / T20I between two ICC full members / T20I involving an associate / Other T20 (A-team events). |
| `set_weights(s, tier_w, halflife)` | Ball weight = tier weight (1.0 / 1.0 / 0.4 / 0.3), optionally × a recency weight (off in the main rating). |
| `add_pressure(s, wm, wt, wi)` | **Combined pressure** CPI = wm·MSP + wt·TSP + wi·IPP (default 0.5 / 0.3 / 0.2; a missing part counts as 50), computed separately from the batter's and the bowler's view. `hp_bat` / `hp_bowl` = the top 30% of CPI within the competition group (**high-pressure balls**). |

**Statistics helpers**

| Function | What it does |
|---|---|
| `eb_shrink(x, w, player, min_n)` | **Empirical Bayes shrinkage.** Estimates k (the noise-to-signal ratio of the metric) from how much players really differ compared with random noise, then pulls each player's weighted average towards the overall average by n_eff/(n_eff+k). A player with few balls is pulled a lot; one with many balls barely moves. Returns infinite k if no real difference between players is detectable. |
| `split_half(x, player, min_n)` | **Repeatability test.** Splits each player's balls (or innings) into odd and even halves and correlates the two halves across players. A high value means the metric measures a real skill, not luck. |
| `split_half_diff(...)` | The same test for a difference (pressure minus normal), used for "uplift". |

**Player tables**

| Function | What it does |
|---|---|
| `batting_table(s)` | Balls faced. `runs_ae` / `out_ae` = runs and dismissals **above the average batter on balls of the same tier × phase × pressure level**. Computes the shrunk metrics (WPA per pressure ball, runs above expected under pressure, dismissals above expected under pressure, runs above expected in normal situations), **reliability** (the share of pressure innings, those with 5+ high-pressure balls, in which the batter **added** win probability, shrunk) and the repeatability of each component. `desc()` adds plain descriptive stats (balls, strike rate, average, dot %, boundary %) split by pressure vs normal, IPL vs T20I. |
| `bowling_table(s)` | The bowling mirror: WPA is reversed, runs conceded and wickets are above same-situation peers, and reliability is the share of pressure spells that **cost the batting side** win probability. Descriptive economy, wickets per 24 balls and dot %. |
| `player_context(s)` | Name, last match, batting position (median over the last 2 years) → role, keeper flag (from the playing XIs), pace or spin, phase usage → bowling role, latest IPL team. Descriptive only. |

**Scoring and ranking**

| Function | What it does |
|---|---|
| `zscore(x)` | Standardises a metric across the eligible players. |
| `cup_score(t, role, weights)` | **The rating.** Batters: impact (WPA), scoring, survival, reliability, uplift (pressure minus normal). Bowlers: impact, economy, wickets, reliability, uplift. Each is z-scored, then combined as a weighted sum. |
| `build_table(s, ctx, role)` | Player table + context + **eligibility**: batters need 200+ high-pressure balls and 15+ pressure innings; bowlers 240+ and 20+. |
| `data_weights(rel)` | **Rating weights ∝ repeatability**, so luck-driven components count for little. |
| `score_pool(pool, role, weights)` | Rating, 0–100 percentile, confidence (Medium from 300 / 360 pressure balls, High from 500 / 600), sort, rank. |
| `weight_variants(role, rel)` | Alternative rating weights for the sensitivity tests: data-driven, expert, equal, impact-only. |
| `compare(base, other, label)` | Top-10 overlap, same #1, and Spearman correlation between two rankings. |
| `run_all()` | Builds the baseline ranking plus every sensitivity variant: competition weighting (tiered, IPL-primary, all equal, recency) and pressure definition (baseline, equal, situation only, situation + stakes). |
| `main()` | Saves `rankings_batting.csv` and `rankings_bowling.csv` and writes `outputs/cup_rankings_report.md` (weights, top 10, ranks 11–20, sensitivity). |

---

## `src/validate_rankings.py` — evidence for the report

| Function | What it does |
|---|---|
| `pressure_separation(s)` | Splits all balls into 10 pressure deciles and shows that win-probability swing, dismissal rate, strike rate, death-over share and knockout share change with pressure. Chart `figures/pressure_separation.png`. |
| `bootstrap(s, ctx, base, weights, rng)` | 100 times: resample **whole matches** with replacement, re-rate every eligible player with the same weights, record ranks. Gives median rank, 90% interval and P(top 10). |
| `rank_chart(df, title, fname)` | Chart of the top 10 with rank intervals. |
| `temporal(s, ctx, weights)` | Rates players on 2022–24 and again on 2025–26. Do early pressure ratings predict later pressure performance, and do they add information **beyond normal-situation ability** (partial correlation)? |
| `scatter(base, role, fname)` | Pressure vs usual chart: strike rate for batters, economy for bowlers, top 10 highlighted, diagonal = "same as usual". |
| `main()` | Runs everything and writes `outputs/validation_rankings_report.md` and `outputs/figures/*.png`. |
