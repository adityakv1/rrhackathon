# Methodology & Decision Log — SupeRR Selector S2

Every assumption below is tested against the data. Scripts that reproduce each one are in brackets.

## Data definitions (validated) [`python -m src.validate`]
| Question | Decision | Evidence |
|---|---|---|
| Runs per ball | `runs + extras1_runs + extras_2_runs` | Reproduces 399/400 stated run margins; the one miss is a tie decided by a Super Over (212 vs 212). Wicket margins reproduced in 99.8% of games |
| `extras_type == "other"` | No-ball (same as `Overstep`) | With `other` = no-ball, 100% of 216 completed overs containing one have exactly 6 legal balls (0% if `other` is treated as legal). Also removes 150 impossible innings with >120 legal balls |
| `*_revised_overs` columns | Innings length in **balls** | No played innings exceeds its value; read as overs they would mean 30–114-over innings |
| `revised_target` | Runs needed to win (DLS-adjusted where applicable) | Every chase won by wickets reaches it; 35% equal first total + 1, the rest are DLS |
| Retired-out | Not a batting dismissal | Cricket convention |
| Super Overs (innings 3–4) | Excluded from regular play; a Super Over-decided match is a tie in regular play | — |

## Match state [`python -m src.match_state`]
- The state is recorded **before** each ball (what the player faced) and **after** it.
- 99.6% of 843 completed chases end in a state that reproduces the recorded result.
- 16 rain-shortened innings had no revised length recorded; their limit is inferred from where a decided match's innings stopped (flag `limit_inferred`).
- 3 matches cannot be reconstructed (18532, 24822, 28334) and are flagged `state_reliable=False` and excluded from model fitting.
- Small, documented look-ahead: when rain cuts an innings mid-way, the reduced length applies to the whole innings.

## Match Situation Pressure (MSP) [`python -m src.pressure_msp`, `python -m src.pressure_msp1`]
- **Chase win probability:** interpretable logistic model (runs required, balls left, wickets in hand, scoring environment) with an exact ball-outcome recursion over the last 30 balls.
  - Trained on chases before 2025, tested on 2025–26: log loss 0.370 / AUC 0.918, against 0.411 / 0.897 for required run rate alone.
  - Last 12 balls: log loss 0.153, against 0.181 for the logistic model alone.
- **First innings:** a monotonic gradient-boosting model of runs still to come (MAE 18.0 runs, against 18.8 for the best baseline and 27.0 for current run rate × overs). Win probability = the chase model applied to every possible final total, weighted by its probability.
  - The two innings join up: mean gap 0.002 between the end of innings 1 and the start of innings 2. The rare larger gaps are matches where the second innings was shortened.
- **Leverage** = the expected absolute change in win probability over the possible outcomes of a ball (dot, 1, 2, 3, 4, 6, wicket, extra), weighted by phase-specific frequencies.
  - **MSP** = leverage as a 0–100 percentile on one scale for both innings.
  - The same situation applies to the batter and the bowler. **WPA** (win probability added) credits the batter, and the bowler gets its negative.
- **Leakage controls:** the scoring environment and venue par use only matches played before the current match date (same-day matches cannot see each other).

## Tournament Stakes Pressure (TSP) [`python -m src.pressure_tsp`]
- **One formula for every match:** TSP(team) = P(win the competition | win this match) − P(win the competition | lose this match). The competition is the title, or the series for bilateral T20Is (a drawn series counts as half).
- **League and series games:**
  - The table is rebuilt from *earlier* results only (no future results used).
  - The remaining *fixtures*, which are known in advance, are simulated 4,000 times as 50/50 games.
  - Ties on points are broken by NRR-to-date plus noise.
  - A Super Over winner takes the points, as in the IPL table.
- **Knockouts are exact under 50/50 games:** Final 1.0, Qualifier 2 / Semi-final 0.5, Qualifier 1 0.25 (the loser gets a second chance), Eliminator 0.25.
- **Team-specific:** the two sides in one match can differ. For example, RR 2024 game 70 was worth 25 (a top-2 decider), while RR 2025's last four games were 0 (already eliminated).
- **Not modelled:** Asia Cup-style group and Super 4 stages, because their qualification rules cannot be recovered from the data. Their knockouts are scored and the other stages are flagged `structure_unknown` (108 team-games, none in the IPL).
- **Scale caveat:** a bilateral series game is a large share of a small competition, so T20I TSP runs higher than IPL league TSP. TSP must therefore be compared *within* a competition group, never pooled raw.

## Individual Performance Pressure (IPP) [`python -m src.pressure_ipp`]
- **A form-based proxy, NOT a measure of psychological state.** It measures how far recent output (last 5 innings or matches) sits below the player's own career-to-date baseline. It uses only matches before the one being scored, across all T20 competitions.
- **Batting components:** runs drop, strike-rate drop, low-score streak (innings below half the baseline).
- **Bowling components:** economy rise, wicket-rate drop, wicketless streak.
- **Scoring:** each component becomes a percentile, the three are averaged with equal weight, and the result is a 0–100 percentile.
- **Shrinkage:** baselines are pulled towards the population average (10 innings of weight).
- **Role filter:**
  - Batting IPP applies only to players who usually bat in the top 7, judged from previous innings.
  - Bowling IPP applies only to genuine bowlers: usually 2+ overs a match, and 4+ overs in the recent window.
  - Without this filter, tail-enders' batting and part-timers' bowling dominated the "slumps".
  - Players with fewer than 3 previous innings are flagged and left out.
- **Validation:** the highest-IPP cases are recognisable slumps (Rohit Sharma and Mitchell Marsh in IPL 2023).
- **Finding:**
  - Batters in the worst form (top 20% IPP) score at their own baseline next innings (+0.08 runs), so a batting slump does not predict the next innings.
  - Out-of-form bowlers concede ~0.27 runs/over more than their baseline, a slight persistence.
  - IPP is therefore used as pressure **context** (did the player respond when under form pressure?), not as a forecast.

## Consistency Under Pressure (CUP) and rankings [`python -m src.cup`]
- **Combined pressure per ball:** CPI = 0.5 × MSP + 0.3 × TSP (percentile within competition group) + 0.2 × IPP. A missing part counts as a neutral 50.
  - A ball is *high pressure* if it is in the top 30% by CPI within its competition group.
  - Three alternative weightings were tested (see sensitivity).
- **Fair comparison:** each ball's runs, dismissals and wickets are measured against the average player on balls of the **same competition tier × phase × pressure tier**.
  - Tiers: IPL / T20I between ICC full members / T20I involving an associate nation / Other T20 (A-team events).
  - Tier weights: 1.0 / 1.0 / 0.4 / 0.3. Top-level cricket counts fully, and runs or wickets against weaker opposition count less.
  - All seasons count equally (the brief covers 2022 onwards). Recency weighting is a sensitivity check only.
- **Shrinkage:** empirical Bayes. k (noise-to-signal ratio) is estimated from unweighted data, then applied using each player's effective sample size.
- **Data-driven weights:** each CUP component is weighted by its split-half repeatability under pressure (odd vs even balls or innings).
  - **Key finding:** realised batting WPA per pressure ball is mostly luck (split-half r = 0.05). Scoring rate (0.33), pressure-innings success rate (0.30), uplift (0.25) and survival (0.23) repeat.
  - For bowlers, economy (0.37), impact (0.26) and uplift (0.21) repeat, while wicket rate barely does (0.03).
  - Noisy measures therefore get little weight automatically. The hand-set weights are kept only as a sensitivity check.
- **Pressure relative to the player's own usual level (two-level empirical Bayes, `eb_two_level`):**
  - pressure estimate = normal-situation level (shrunk to the population) + pressure-minus-normal difference (shrunk by λ = τ²/(τ²+noise)).
  - The data keeps only a small part of individual differences: median λ ≈ 0.07 for batting scoring and 0.10 for bowling economy; dismissal and wicket differences ≈ 0.
  - **Tested against unshrunk 2025–26 pressure performance (rated on 2022–24):**
    - Bowling pressure-economy prediction improved from r = 0.03 (pressure balls only) to 0.40.
    - Batting was about neutral (0.41 → 0.34 for scoring; full rating 0.34 → 0.39).
    - Bowling rating stability improved from −0.03 to 0.15.
  - **Finding:** batters show a pressure-specific trait beyond general ability (partial r = 0.27); bowlers do not (−0.14). Bowling under pressure is mostly bowling quality: normal economy alone predicts later pressure economy at r = 0.62.
- **Final order = bagged rating:** the rating is averaged over 100 match-level bootstrap resamples, which smooths sampling noise in places 4–10. Each player is reported with their bootstrap P(top 10) and a 90% rank interval.
- **Framing decision (final):** the lists are the **best performers in pressure situations**, measured against same-situation peers and relative to each player's usual level. This matches the submission wording ("the 10 best-performing batters under pressure") and is the version with the best out-of-time predictive evidence.
  - The alternative "rises most above own usual level" framing (uplift weight 50%) is reported as a sensitivity check: against the final list, 7 of 10 batters and 8 of 10 bowlers are unchanged.
  - That framing brings in Powell, Shanaka and Sikandar Raza (batters) and Avesh Khan and Mohsin Khan (bowlers). It drops Tim David, Abhishek Sharma and Gill (batters) and Bumrah and Rashid Khan (bowlers).
  - It is not the main ranking because the evidence shows that a player's personal pressure-vs-usual gap is mostly noise (only ~7–10% of it persists).
- **Eligibility (brief: best performers under pressure, 2022–26):**
  - Batters need at least 200 high-pressure balls faced and 15 pressure innings; bowlers need at least 240 high-pressure balls and 20 pressure spells, across all competitions.
  - Confidence tiers: Medium from 300 (bat) or 360 (bowl) pressure balls; High from 500 or 600.
  - No "still active" filter: the brief ranks performance over the period, not auction availability.
  - *(An earlier RR-auction version used IPL-only pools, an activity filter and recency weighting; this was superseded by the official brief.)*
- **Roles (descriptive only, not used in ranking):**
  - Batting position is the median over the last 2 years; keeper = kept wicket in at least 30% of matches.
  - Bowling phase role comes from IPL usage when available. Death specialist = 33%+ of balls at the death, against a ~20% baseline.
- **Sensitivity (overlap with the final top 10, 10 alternatives; see report §4.3):** 5–9 of the batters and 6–9 of the bowlers survive (median 7 and 8). Competition weighting changes least (8–9/10). Impact-only rating (5/10 batters) and situation-only pressure (7/10 batters, 6/10 bowlers) change most. Places 1–5 survive in 10–12 of 12 variants; places 6–10 are less stable (Jaiswal 3/12, Boult 5/12).
- **Finding (death bowling):** only 6 of 65 eligible bowlers are death specialists, and none reaches the top 10. They do beat same-situation peers under pressure (0.23 runs per over fewer on average), but the leading middle-overs bowlers beat their peers by more (0.33 runs per over), and economy is the most repeatable bowling measure. The report's §4.4 therefore adds best-by-role tables.

### Known limitation — chasing has become easier
- Chase win rate: 48% before 2025, 53% in 2025, 55% in 2026.
- **Training years:** the method is unbiased (first-innings WP at ball 1: predicted 52.1% vs actual 51.7%; predicted total 174.5 vs 174.0).
- **Out of time (2025–26):** the models favour the side batting first by ~10 points.
- **Fixes tested:** recency weighting and a leakage-safe "recent chase rate" feature. Neither helped consistently across 2025 and 2026, so the simpler model is kept.
- **Production models are refit on all seasons.** MSP is a rank of how much win probability can move on a ball, so it is robust to level bias.
