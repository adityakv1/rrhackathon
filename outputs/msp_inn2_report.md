# Second-innings Match Situation Pressure

Train: chases before 2025-01-01 (497 matches, 56,800 balls). Test: 335 later chases (37,194 balls). Ties, no-results and the 3 unreliable matches are excluded from fitting.

Test-period chase win rate 53.7% vs train 48.3%; scoring environment (runs/over) train 8.68 vs test 9.02.

## Out-of-time accuracy on 2025-26 (lower log loss / Brier is better)
| model                                   |   balls |   matches |   log_loss |   brier |    auc |
|:----------------------------------------|--------:|----------:|-----------:|--------:|-------:|
| Constant (train win rate)               |   37194 |       335 |     0.698  |  0.2524 | 0.5    |
| Required run rate only                  |   37194 |       335 |     0.4113 |  0.1341 | 0.8968 |
| Chase model without scoring environment |   37194 |       335 |     0.3743 |  0.1214 | 0.9153 |
| Chase model (logistic only)             |   37194 |       335 |     0.3734 |  0.1211 | 0.9156 |
| Chase model + endgame recursion (final) |   37194 |       335 |     0.3701 |  0.1202 | 0.9179 |
| last 12 balls: logistic only            |    2054 |       214 |     0.181  |  0.0554 | 0.9785 |
| last 12 balls: final                    |    2054 |       214 |     0.1526 |  0.0483 | 0.9851 |
| Final - IPL only                        |   16306 |       142 |     0.3945 |  0.1263 | 0.9207 |
| Final - T20I only                       |   19524 |       180 |     0.3506 |  0.1147 | 0.921  |

## Calibration on 2025-26 test set (predicted vs actual chase win rate)
| p          |   balls |   predicted |   actual |
|:-----------|--------:|------------:|---------:|
| (0.0, 0.1] |    9256 |       0.027 |    0.039 |
| (0.1, 0.2] |    3200 |       0.147 |    0.194 |
| (0.2, 0.3] |    2834 |       0.25  |    0.314 |
| (0.3, 0.4] |    2566 |       0.35  |    0.467 |
| (0.4, 0.5] |    2644 |       0.45  |    0.534 |
| (0.5, 0.6] |    2278 |       0.55  |    0.632 |
| (0.6, 0.7] |    2194 |       0.653 |    0.772 |
| (0.7, 0.8] |    2403 |       0.75  |    0.819 |
| (0.8, 0.9] |    2854 |       0.852 |    0.914 |
| (0.9, 1.0] |    6965 |       0.967 |    0.984 |

Known limitation: chasing has become easier over time (chase win rate 48% to 2024, 53% in 2025, 55% in 2026), so the out-of-time model is a few points pessimistic mid-range. Recency weighting and a recent-chase-rate feature were tested and did not help consistently across 2025 and 2026, so the simpler model is kept. The production model is refit on all seasons. Pressure (msp) is a rank, so it is robust to this.

## Model coefficients (standardised; + raises chase win probability)
|             |   coef |
|:------------|-------:|
| log_r       | -2.337 |
| w_sq        | -1.339 |
| r_per_wkt   | -1.086 |
| rrr         | -0.582 |
| rrr_rel     | -0.123 |
| is_ipl      |  0.19  |
| rrr_x_wlost |  0.373 |
| log_b       |  1.654 |
| w           |  2.747 |

## Ball outcome frequencies by phase (training data; weights for leverage)
| innings_phase   |   dot |     1 |     2 |     3 |     4 |     6 |   wicket |   extra |
|:----------------|------:|------:|------:|------:|------:|------:|---------:|--------:|
| Death           | 0.216 | 0.355 | 0.077 | 0.003 | 0.116 | 0.083 |    0.086 |   0.065 |
| Middle          | 0.259 | 0.44  | 0.066 | 0.002 | 0.09  | 0.056 |    0.051 |   0.036 |
| Powerplay       | 0.392 | 0.267 | 0.044 | 0.005 | 0.16  | 0.048 |    0.047 |   0.037 |

## Sanity checks
Mean MSP by over and final margin (pressure should build late in close chases):
| closeness              |   1 |   2 |   3 |   4 |   5 |   6 |   7 |   8 |   9 |   10 |   11 |   12 |   13 |   14 |   15 |   16 |   17 |   18 |   19 |   20 |
|:-----------------------|----:|----:|----:|----:|----:|----:|----:|----:|----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|
| close (<=6 runs/balls) |  57 |  58 |  60 |  62 |  63 |  64 |  59 |  60 |  61 |   63 |   64 |   65 |   67 |   69 |   69 |   75 |   82 |   82 |   81 |   87 |
| medium                 |  54 |  56 |  56 |  57 |  59 |  61 |  55 |  55 |  56 |   56 |   57 |   56 |   55 |   54 |   53 |   53 |   53 |   52 |   52 |   32 |
| one-sided              |  49 |  47 |  46 |  45 |  43 |  42 |  37 |  36 |  35 |   33 |   32 |   31 |   28 |   26 |   25 |   23 |   22 |   15 |    7 |    1 |

Mean MSP by final margin:
| closeness              |   msp |
|:-----------------------|------:|
| close (<=6 runs/balls) |  66.9 |
| medium                 |  54.9 |
| one-sided              |  34.1 |

Highest-leverage balls:
|   match_id | competition_group   |   overid | striker_name            | bowler_name         |   runs_required |   balls_remaining |   wickets_in_hand |   wp_before |   leverage_index |   total_runs | is_wicket   |
|-----------:|:--------------------|---------:|:------------------------|:--------------------|----------------:|------------------:|------------------:|------------:|-----------------:|-------------:|:------------|
|      14133 | IPL                 |       20 | Rashid Khan             | Marco Jansen        |               3 |                 1 |                 5 |       0.271 |           22.251 |            6 | False       |
|      14160 | IPL                 |       20 | Umesh Yadav             | Marcus Stoinis      |               3 |                 1 |                 3 |       0.271 |           22.251 |            0 | True        |
|      20221 | IPL                 |       20 | Sikandar Raza           | Matheesha Pathirana |               3 |                 1 |                 4 |       0.271 |           22.251 |            3 | False       |
|      28962 | T20I                |       20 | Gulbadin Naib           | Mukesh Kumar        |               3 |                 1 |                 4 |       0.271 |           22.251 |            2 | False       |
|      32621 | T20I                |       20 | Tim Pringle             | Mark Adair          |               3 |                 1 |                 2 |       0.271 |           22.251 |            1 | False       |
|      34429 | T20I                |       20 | Chamindu Wickramasinghe | Suryakumar Yadav    |               3 |                 1 |                 2 |       0.271 |           22.251 |            2 | False       |
|      40746 | IPL                 |       20 | Shubham Dubey           | Vaibhav Arora       |               3 |                 1 |                 3 |       0.271 |           22.251 |            1 | True        |
|      41511 | T20I                |       20 | Jason Holder            | Shaheen Afridi      |               3 |                 1 |                 2 |       0.271 |           22.251 |            4 | False       |

Tewatia vs Odean Smith, last two balls of GT v PBKS 2022 (12 needed off 2):
|   runs_required |   balls_remaining |   wp_before |   wp_after |   wpa |   leverage_index |    msp |
|----------------:|------------------:|------------:|-----------:|------:|-----------------:|-------:|
|              12 |                 2 |       0.009 |      0.094 | 0.084 |            0.961 | 54.399 |
|               6 |                 1 |       0.094 |      1     | 0.906 |            9.909 | 99.825 |