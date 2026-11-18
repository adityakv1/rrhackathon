# Validation evidence

## 1. Does the pressure index separate pressure from ordinary situations? (batting view, all balls)
|   decile |   balls |   strike_rate |   dismissal_% |   dot_% |   boundary_% |   mean_|WPA| |   death_overs_% |   knockout_% |
|---------:|--------:|--------------:|--------------:|--------:|-------------:|-------------:|----------------:|-------------:|
|        1 |   19273 |       145.686 |         6.05  |  36.191 |       19.805 |        0.004 |          21.725 |        0.752 |
|        2 |   19271 |       141.389 |         5.433 |  35.961 |       18.613 |        0.007 |          16.699 |        0.913 |
|        3 |   19271 |       138.208 |         5.604 |  36.791 |       18.245 |        0.008 |          14.929 |        2.667 |
|        4 |   19271 |       137.217 |         5.392 |  36.843 |       17.871 |        0.01  |          12.407 |        3.472 |
|        5 |   19271 |       138.768 |         4.976 |  36.807 |       18.224 |        0.012 |          13.414 |        3.783 |
|        6 |   19271 |       137.502 |         5.21  |  37.87  |       18.536 |        0.013 |          14.244 |        3.129 |
|        7 |   19269 |       138.751 |         5.293 |  37.963 |       18.953 |        0.016 |          15.611 |        3.285 |
|        8 |   19273 |       139.247 |         5.132 |  37.716 |       18.861 |        0.018 |          17.724 |        3.58  |
|        9 |   19270 |       139.408 |         5.579 |  37.753 |       19.071 |        0.022 |          19.746 |        4.499 |
|       10 |   19272 |       139.275 |         5.921 |  36.602 |       18.69  |        0.029 |          22.494 |       10.539 |

High-pressure balls (top 30%) carry 2.3x the average win-probability swing of ordinary balls; dismissal rate 5.5% vs 5.4%.
Chart: figures/pressure_separation.png

## 2. Batters: rank uncertainty (100 match-level bootstrap draws)
|   final_rank |   rank | player_name      | confidence   |   bagged_cup |   median_rank |   rank_p05 |   rank_p95 |   p_top10 |
|-------------:|-------:|:-----------------|:-------------|-------------:|--------------:|-----------:|-----------:|----------:|
|            1 |      1 | Suryakumar Yadav | High         |         1.76 |           1   |       1    |       3.05 |      1    |
|            2 |      2 | Abhishek Sharma  | Medium       |         1.08 |           3   |       1    |      12    |      0.87 |
|            3 |      4 | Heinrich Klaasen | Low          |         0.94 |           5   |       2    |      16.05 |      0.77 |
|            4 |      5 | Phil Salt        | High         |         0.92 |           5   |       2    |      30.1  |      0.7  |
|            5 |      3 | Rinku Singh      | Low          |         0.92 |           6   |       3    |      17.05 |      0.86 |
|            6 |      6 | Sai Sudharsan    | Medium       |         0.82 |           7.5 |       2    |      19.05 |      0.69 |
|            7 |      7 | Tim David        | Medium       |         0.79 |           8   |       2    |      30.05 |      0.58 |
|            8 |      8 | Cameron Green    | Medium       |         0.66 |          12   |       2.95 |      38.1  |      0.42 |
|            9 |      9 | Shubman Gill     | High         |         0.58 |          13   |       4    |      35.35 |      0.38 |
|           10 |     12 | Yashasvi Jaiswal | High         |         0.55 |          13   |       3    |      43.05 |      0.33 |
|           11 |     10 | Shreyas Iyer     | Medium       |         0.55 |          14   |       4    |      42.1  |      0.34 |
|           12 |     11 | Rovman Powell    | Medium       |         0.54 |          15   |       4    |      38    |      0.31 |
|           13 |     14 | Virat Kohli      | High         |         0.44 |          17.5 |       5    |      47    |      0.18 |
|           14 |     13 | Dinesh Karthik   | Low          |         0.42 |          18   |       4.95 |      48.05 |      0.2  |
|           15 |     15 | Pathum Nissanka  | High         |         0.42 |          18.5 |       5    |      45    |      0.19 |

## 2. Bowlers: rank uncertainty (100 match-level bootstrap draws)
|   final_rank |   rank | player_name         | confidence   |   bagged_cup |   median_rank |   rank_p05 |   rank_p95 |   p_top10 |
|-------------:|-------:|:--------------------|:-------------|-------------:|--------------:|-----------:|-----------:|----------:|
|            1 |      1 | Sunil Narine        | Low          |         1.15 |           5   |       1    |      21.05 |      0.81 |
|            2 |      2 | Kuldeep Yadav       | Medium       |         1.03 |           5   |       1    |      22.1  |      0.78 |
|            3 |      3 | Axar Patel          | Medium       |         0.94 |           7.5 |       1    |      26.05 |      0.66 |
|            4 |      7 | Jasprit Bumrah      | Medium       |         0.94 |           7   |       1    |      28.05 |      0.66 |
|            5 |      4 | Adam Zampa          | Medium       |         0.92 |           7   |       1    |      27.05 |      0.66 |
|            6 |      5 | Krunal Pandya       | Medium       |         0.89 |           8   |       1.95 |      23    |      0.6  |
|            7 |      9 | Rashid Khan         | High         |         0.86 |           9   |       1    |      33.05 |      0.61 |
|            8 |      6 | Mitchell Santner    | Medium       |         0.84 |           9   |       1    |      29    |      0.55 |
|            9 |      8 | Mohammed Shami      | Medium       |         0.81 |           9   |       2    |      28.1  |      0.59 |
|           10 |     10 | Trent Boult         | High         |         0.72 |          11   |       3    |      29    |      0.48 |
|           11 |     11 | Mujeeb Ur Rahman    | Low          |         0.69 |          11   |       3    |      29.2  |      0.43 |
|           12 |     12 | Bhuvneshwar Kumar   | High         |         0.62 |          14   |       3    |      35    |      0.38 |
|           13 |     13 | Ravichandran Ashwin | Medium       |         0.54 |          16.5 |       5    |      35    |      0.24 |
|           14 |     14 | Josh Hazlewood      | High         |         0.53 |          15   |       2    |      44.05 |      0.33 |
|           15 |     16 | Mohammad Nawaz      | Low          |         0.47 |          18   |       2.95 |      44    |      0.23 |

## 3. Temporal stability: rate on 2022-24, check against 2025-26
|                                                 |   batters |   bowlers |
|:------------------------------------------------|----------:|----------:|
| players                                         |    42     |    38     |
| old estimate -> later pressure scoring/economy  |     0.407 |     0.033 |
| A (own level) -> later pressure scoring/economy |     0.344 |     0.402 |
| normal level only -> later                      |     0.319 |     0.616 |
| old CUP -> later                                |     0.341 |    -0.111 |
| A CUP -> later                                  |     0.386 |     0.089 |
| old CUP -> later survival/wickets               |    -0.091 |     0.099 |
| A CUP -> later survival/wickets                 |    -0.292 |     0.17  |
| partial r: raw pressure record | normal         |     0.267 |    -0.144 |
| CUP 2022-24 vs CUP 2025-26 (spearman)           |     0.346 |     0.151 |

Partial r > 0 means pressure performance carries information about future pressure performance beyond general ability.