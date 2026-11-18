# First-innings Match Situation Pressure

## 1. Runs still to come: test MAE on 345 2025-26 first innings (lower is better)
| method                               |   MAE (runs) |
|:-------------------------------------|-------------:|
| Current run rate x overs left        |        27    |
| Scoring environment x overs left     |        18.83 |
| Remaining-runs model (monotonic GBM) |        18.03 |

MAE of predicted FINAL total at key points:
|     |   after 0 overs |   after 6 overs |   after 10 overs |   after 16 overs |
|:----|----------------:|----------------:|-----------------:|-----------------:|
| MAE |            31.6 |            22.6 |               18 |             10.1 |

## 2. First-innings win probability on 2025-26 (out-of-time)
| model                  |   balls |   log_loss |   brier |    auc |
|:-----------------------|--------:|-----------:|--------:|-------:|
| Constant               |   41158 |     0.6934 |  0.2501 | 0.5    |
| First-innings WP model |   41158 |     0.7005 |  0.2485 | 0.6581 |

Accuracy by stage of the first innings (AUC grows as the innings reveals more):
| legal_balls_before   |   auc |   mean_pred |   actual |
|:---------------------|------:|------------:|---------:|
| overs 1-6            | 0.546 |       0.589 |    0.463 |
| 7-12                 | 0.652 |       0.587 |    0.459 |
| 13-18                | 0.724 |       0.584 |    0.467 |
| 19-20                | 0.747 |       0.595 |    0.492 |

## 3. Sanity checks
- Innings join-up: |WP at end of innings 1 - (1 - chase WP at start of innings 2)| mean 0.0018, max 0.2421 over 845 matches
- Mean MSP by innings and over (0-100, one scale for both innings):
|   innings |   1 |   2 |   3 |   4 |   5 |   6 |   7 |   8 |   9 |   10 |   11 |   12 |   13 |   14 |   15 |   16 |   17 |   18 |   19 |   20 |
|----------:|----:|----:|----:|----:|----:|----:|----:|----:|----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|
|         1 |  67 |  62 |  57 |  61 |  51 |  56 |  43 |  39 |  42 |   41 |   40 |   39 |   39 |   36 |   40 |   38 |   53 |   51 |   51 |   52 |
|         2 |  59 |  59 |  59 |  58 |  58 |  57 |  51 |  50 |  51 |   50 |   50 |   49 |   48 |   46 |   47 |   48 |   52 |   51 |   49 |   42 |

- Mean MSP in knockout matches 50.5 vs others 50.0 (MSP measures the match situation only; stakes are added separately)

Example first innings (every 4th over end): projected WP of batting side
|   overid |   score_after |   wickets_after |   wp_after |
|---------:|--------------:|----------------:|-----------:|
|        1 |             6 |               1 |      0.427 |
|        5 |            24 |               4 |      0.174 |
|        9 |            35 |               5 |      0.074 |
|       13 |            59 |               7 |      0.033 |
|       17 |            87 |               8 |      0.046 |