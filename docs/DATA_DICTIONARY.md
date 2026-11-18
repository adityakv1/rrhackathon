# Data Dictionary

Every table the pipeline writes, and what each derived column means. Raw columns copied unchanged from the supplied CSVs (ids, names, `stroke`, `bowl_speed`, …) are not repeated here.

Conventions:
- `_before` = the state before the ball (the situation the player faced). `_after` = the state after it.
- **Legal ball** = not a wide and not a no-ball (`Overstep` or `other`).
- **WP** = the batting side's probability of winning (0–1).

---

## `data/processed/deliveries.parquet` — clean balls (200,961 rows, innings 1–2 only)
Written by `src/data.py`.

| Column | Meaning |
|---|---|
| `total_runs` | runs + extras1_runs + extras_2_runs. All runs from the ball (validated against match results). |
| `batter_runs` | Runs off the bat (`runs`). Byes and leg-byes hold their runs in `extras1_runs`. |
| `is_wide` / `is_no_ball` | Wide / no-ball (`Overstep`, plus `other`, which is proven to be a no-ball). |
| `legal_ball` | Neither a wide nor a no-ball. Counts towards the innings' balls. |
| `ball_faced` | Not a wide. A no-ball still counts as faced by the batter. |
| `bowler_runs` | Runs charged to the bowler. On byes, leg-byes and penalty only the bat runs count. |
| `bowler_wicket` | Wicket credited to the bowler (Caught, Bowled, LBW, Stump, Hit Wicket). |
| `batter_out` | A wicket that counts as a batting dismissal (everything except Retire Out). |
| `competition_group` | IPL / T20I / Other T20. |

## `data/processed/matches.parquet` — matches (883 rows)
Raw match table plus `comp_name`, `season`, `competition_group` and a parsed `match_date`.
- `first_inn_revised_overs` and `second_inn_revised_overs` are **innings lengths in balls** (proven in `validate.py`).
- `revised_target` is the runs needed to win.

## `data/processed/match_state.parquet` — situation on every ball (200,961 rows)
Written by `src/match_state.py`. Includes the clean ball columns above, plus:

| Column | Meaning |
|---|---|
| `score_before`, `wickets_before`, `legal_balls_before` | Innings score, wickets and legal balls before this ball. |
| `score_after`, `wickets_after`, `legal_balls_after` | The same, after this ball. |
| `innings_limit_balls` | Legal balls allowed this innings (120, or the revised or inferred limit). |
| `limit_inferred` | True if a rain-shortened limit was missing from the data and inferred from where the innings stopped. |
| `balls_remaining` | innings_limit_balls − legal_balls_before. |
| `wickets_in_hand` | 10 − wickets_before. |
| `innings_progress` | Share of the innings bowled (0–1). |
| `innings_phase` | Powerplay (overs 1–6), Middle (7–16), Death (17–20). |
| `current_run_rate` | Runs per over so far. |
| `target` | Innings 2 only: revised target if set, else first-innings total + 1. |
| `runs_required`, `required_run_rate`, `rrr_minus_crr` | Innings 2 only: runs still needed, runs per over needed, gap to the current rate. |
| `first_innings_total` | Final first-innings score of the match. |
| `outcome_type` | win / tie (including Super Over-decided games) / no_result. |
| `decided_by_super_over`, `dls` | Result flags. |
| `batting_team_won` | 1 / 0 / 0.5 (tie) / NaN (no result). **A label for checking and fitting only, never a pressure input.** |
| `state_reliable` | False for the 3 matches whose final state cannot reproduce their result (excluded from fitting and rating). |

## `data/processed/pressure_msp.parquet` — match situation pressure (200,961 rows)
Written by `src/pressure_msp1.py` (both innings). `pressure_msp_inn2.parquet` is the chase-only intermediate.

| Column | Meaning |
|---|---|
| `wp_before`, `wp_after` | Batting side's win probability before and after the ball. |
| `wpa` | Win probability added = wp_after − wp_before. Batter's credit; the bowler's credit is −wpa. |
| `leverage` | Expected absolute WP swing on this ball, over the possible outcomes (dot, 1, 2, 3, 4, 6, wicket, extra) weighted by their phase frequencies. "How much is riding on this ball". |
| `leverage_index` | leverage ÷ average leverage (1 = an average ball). |
| `msp` | **Match Situation Pressure**: leverage as a 0–100 percentile across all balls of both innings. |
| `batting_pressure_dir` / `bowling_pressure_dir` | 1 − wp_before / wp_before: how far behind / ahead the batting side is. |

## `data/processed/pressure_tsp.parquet` — tournament stakes (one row per team per match)
Written by `src/pressure_tsp.py`.

| Column | Meaning |
|---|---|
| `p_title_if_win`, `p_title_if_lose` | Team's probability of winning the competition (or the series) if it wins / loses this match. |
| `tsp` | **Tournament Stakes Pressure** = p_title_if_win − p_title_if_lose (0–1). `tsp_100` = × 100. |
| `points_before`, `rank_before` | League table position before the match (earlier results only). |
| `tsp_method` | simulated_ipl / simulated_bilateral / simulated_round_robin(_final) / knockout_exact / structure_unknown. |

## `data/processed/pressure_ipp.parquet` — form pressure (one row per player per match innings per role)
Written by `src/pressure_ipp.py`. `role` = bat or bowl.

| Column | Meaning |
|---|---|
| `ipp` | **Individual Performance Pressure**: 0–100 percentile of how far recent form sits below the player's own baseline. A proxy, not psychology. |
| `ipp_flag` | ok / insufficient_history (< 3 previous innings) / not_role_player (tail-ender batting, part-timer bowling). |
| `history_n` | Number of previous innings or matches the baseline is built on. |
| `baseline_runs`, `baseline_sr` / `baseline_econ`, `baseline_wkts_per24` | Career-to-date level (shrunk towards the population average). |
| `recent_*` | The same measures over the last 5 innings or matches. |
| `runs_drop`, `sr_drop`, `low_streak` | Batting components. |
| `econ_rise`, `wkt_drop`, `dry_streak` | Bowling components. |

## `outputs/rankings_batting.csv`, `outputs/rankings_bowling.csv` — player ratings
Written by `src/cup.py`, one row per **eligible** player, sorted by rank. Prefixes on descriptive columns:
- `all_p_`: high-pressure balls, all competitions.
- `all_n_`: normal (not high-pressure) balls.
- `ipl_p_` / `ipl_n_` / `ipl_`: IPL pressure / normal / all balls.
- `t20i_` / `t20i_p_`: T20I all / pressure balls.

| Column | Meaning |
|---|---|
| `rank`, `cup`, `cup_100` | Final rank, rating (weighted z-score sum) and its 0–100 percentile among eligible players. |
| `confidence` | Low / Medium / High, from the number of high-pressure balls. |
| `p_wpa` | Shrunk WPA per high-pressure ball (bowlers: win probability taken from the batting side). |
| `p_runs_ae` | Estimated runs per high-pressure ball **above same-situation peers** (same tier × phase × pressure level) = `n_runs_ae` + `d_runs_ae` (two-level shrinkage relative to the player's own usual level). For bowlers, lower is better. |
| `d_runs_ae` | Shrunk **pressure minus usual** difference in runs above peers. The data keeps only ~7% (batting) or ~10% (bowling) of a player's raw difference, because most of it is noise. Drives the uplift component. |
| `p_runs_ae_pop`, `p_out_ae_pop`, `p_wkt_ae_pop` | Older estimate from pressure balls only, shrunk to the population. Kept for the validation comparison. |
| `*_raw` | Unshrunk weighted means. Used as the "truth" in the temporal validation. |
| `p_out_ae` / `p_wkt_ae` | Shrunk dismissals (batters, lower is better) / wickets (bowlers) per pressure ball above peers. |
| `n_runs_ae`, `n_out_ae`, `n_wkt_ae` | The player's **usual level**: runs, dismissals or wickets above peers on normal balls, shrunk to the population. |
| `reliability` | Shrunk share of pressure innings or spells (5+ high-pressure balls) in which the player **gained** win probability for their side. |
| `pressure_innings` / `pressure_spells` | Number of such innings or spells. |
| `z_*` | Each rating component standardised across eligible players (inputs to `cup`). |
| `*_balls`, `*_runs`, `*_sr`, `*_avg`, `*_econ`, `*_wkts_per24`, `*_dot_pct`, `*_boundary_pct`, `*_wpa` | Plain descriptive statistics for the prefix's subset. |
| `sr_uplift` / `econ_uplift` | Pressure SR − normal SR (batters) / normal economy − pressure economy (bowlers). Positive = better under pressure. |
| `batting_role`, `keeper`, `bowling_role`, `pace_or_spin`, `share_*` | Descriptive role information (not used in the rating). |

`outputs/rankings_*_with_uncertainty.csv` are the **final submitted rankings**. They add the bootstrap columns:
- `bagged_cup`: the rating averaged over 100 match-level resamples, with shrinkage settings held at their full-data values.
- `final_rank`: the rank by `bagged_cup`. **This is the submitted order.**
- `median_rank`, `rank_p05` and `rank_p95` (90% interval), and `p_top10`.
- `cup_p20`: the rating a player exceeds in 80% of resamples. `safe_rank` is the rank by `cup_p20` (consistency-first ordering, used as a robustness check).

`outputs/sensitivity_top10_*.csv`: the top 10 under every sensitivity variant, side by side.

## `outputs/players_all_batting.csv`, `outputs/players_all_bowling.csv` — every player
The same columns as `rankings_*.csv`, but for **all** players, including those below the eligibility threshold (written by `src/cup.py`, `save_profiles`). They are used for squad views, such as the Rajasthan Royals section of the report. Rank columns are absent because only eligible players are ranked.

## `outputs/pressure_profile.json` — where high-pressure balls come from
The share of high-pressure balls (batting view) in nearly-decided games (win probability below 15% or above 85%), in overs 1–3, in overs 7–16 and in overs 17–20.

## `outputs/pressure_selection.csv` / `.md` — pressure definitions compared out of sample
Written by `src/select_pressure.py`, with one row per definition (weights for situation/stakes/form × high-pressure share).
- `batters r` / `bowlers r`: correlation of 2022–24 ratings with unshrunk 2025–26 pressure performance. `mean r` is their average.
- `mean stability`: Spearman correlation between 2022–24 and 2025–26 ratings.
- `in use`: marks the definition used for the rankings.
