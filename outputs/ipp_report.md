# Individual Performance Pressure (form-based proxy)

IPP measures how far a player's recent output sits below his own baseline going into a match, using previous matches only. It is a statistical form signal, NOT a measure of psychological state.

- Batting innings: {'ok': 9763, 'insufficient_history': 2344, 'not_role_player': 1645} (role = usually bats in the top 7, judged from previous innings)
- Bowling matches: {'ok': 7941, 'insufficient_history': 1677, 'not_role_player': 476} (role = usually bowls 12+ balls and 24+ balls in the recent window)

## Component correlations (should be positive but not ~1: each adds something)
Batting:
|            |   runs_drop |   sr_drop |   low_streak |
|:-----------|------------:|----------:|-------------:|
| runs_drop  |        1    |      0.64 |         0.47 |
| sr_drop    |        0.64 |      1    |         0.31 |
| low_streak |        0.47 |      0.31 |         1    |

Bowling:
|            |   econ_rise |   wkt_drop |   dry_streak |
|:-----------|------------:|-----------:|-------------:|
| econ_rise  |        1    |       0.27 |         0.16 |
| wkt_drop   |        0.27 |       1    |         0.44 |
| dry_streak |        0.16 |       0.44 |         1    |

## What happened in the match itself, by IPP band (descriptive)
Batting: runs in this innings minus the player's baseline. Near-zero differences mean form pressure carries little predictive signal: it is used as a pressure CONTEXT, not a forecast.
| band                 |   innings |   mean_runs |   baseline |   runs_vs_base |
|:---------------------|----------:|------------:|-----------:|---------------:|
| 0-20 (in form)       |      1952 |       25.38 |      24.52 |           0.86 |
| 20-40                |      1953 |       23.54 |      23.43 |           0.11 |
| 40-60                |      1953 |       23.95 |      22.57 |           1.38 |
| 60-80                |      1952 |       22.74 |      21.57 |           1.16 |
| 80-100 (out of form) |      1953 |       20.46 |      20.38 |           0.08 |

Bowling: economy / wickets in this match by IPP band:
| band                 |   matches |   econ |   base_econ |   wkts_per24 |
|:---------------------|----------:|-------:|------------:|-------------:|
| 0-20 (in form)       |      1588 |   8.38 |        8.29 |         1.31 |
| 20-40                |      1587 |   8.69 |        8.43 |         1.32 |
| 40-60                |      1589 |   8.8  |        8.52 |         1.31 |
| 60-80                |      1588 |   8.99 |        8.61 |         1.21 |
| 80-100 (out of form) |      1589 |   8.96 |        8.69 |         1.21 |

## Highest batting form pressure going into an IPL match (examples)
| player_name     | match_date          |   baseline_runs |   recent_runs |   recent_sr |   low_streak |   ipp |   runs |   balls |
|:----------------|:--------------------|----------------:|--------------:|------------:|-------------:|------:|-------:|--------:|
| Sunil Narine    | 2023-05-11 00:00:00 |            10   |           1.4 |        50   |            7 | 100   |      6 |       5 |
| Sunil Narine    | 2023-05-04 00:00:00 |            10.4 |           1.2 |        46.2 |            6 | 100   |      1 |       2 |
| Mitchell Marsh  | 2023-04-24 00:00:00 |            20.3 |           1.2 |        31.6 |            5 |  99.9 |     25 |      15 |
| Rohit Sharma    | 2023-05-12 00:00:00 |            20.8 |           2.4 |        44.4 |            5 |  99.9 |     29 |      18 |
| Sunil Narine    | 2023-04-23 00:00:00 |            10.8 |           1.2 |        54.5 |            5 |  99.9 |      0 |       3 |
| Daniel Sams     | 2022-05-17 00:00:00 |            12.5 |           2.2 |        61.1 |            8 |  99.8 |     15 |      11 |
| Abhinav Manohar | 2025-04-23 00:00:00 |            15.5 |           3   |        51.7 |            6 |  99.8 |     43 |      37 |
| Abhinav Manohar | 2025-03-30 00:00:00 |            15.9 |           2.6 |        50   |            5 |  99.8 |      4 |       6 |

## Highest bowling form pressure going into an IPL match (examples)
| player_name      | match_date          |   baseline_econ |   recent_econ |   recent_wkts_per24 |   dry_streak |    ipp |   runs |   balls |   wkts |
|:-----------------|:--------------------|----------------:|--------------:|--------------------:|-------------:|-------:|-------:|--------:|-------:|
| Shahbaz Ahmed    | 2023-05-18 00:00:00 |            9.47 |         15.33 |                   0 |            7 | 100    |     38 |      18 |      1 |
| Umesh Yadav      | 2024-03-24 00:00:00 |            8.35 |         12.1  |                   0 |            7 |  99.98 |     31 |      18 |      2 |
| Marcus Stoinis   | 2025-06-01 00:00:00 |            9.22 |         12.97 |                   0 |           11 |  99.95 |     14 |       6 |      1 |
| Romario Shepherd | 2026-04-27 00:00:00 |           10.18 |         16.5  |                   0 |            5 |  99.94 |     21 |      12 |      0 |
| Romario Shepherd | 2026-04-30 00:00:00 |           10.18 |         14.43 |                   0 |            6 |  99.92 |     30 |      24 |      2 |
| FazalHaq Farooqi | 2025-05-18 00:00:00 |            8.19 |         11.59 |                   0 |            5 |  99.91 |     39 |      18 |      0 |
| Sunil Narine     | 2023-04-29 00:00:00 |            7.25 |          9.94 |                   0 |            5 |  99.87 |     24 |      18 |      1 |
| Marcus Stoinis   | 2025-05-24 00:00:00 |            9.16 |         12.26 |                   0 |           10 |  99.87 |     21 |       9 |      0 |