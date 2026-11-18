# Tournament Stakes Pressure

TSP = P(win competition | win match) - P(win competition | lose match), 0-1 (x100 for 0-100).

## Coverage
| competition_group   |   knockout_exact |   simulated_bilateral |   simulated_ipl |   simulated_round_robin |   simulated_round_robin_final |   structure_unknown |
|:--------------------|-----------------:|----------------------:|----------------:|------------------------:|------------------------------:|--------------------:|
| IPL                 |               40 |                     0 |             702 |                       0 |                             0 |                   0 |
| Other T20           |               12 |                     0 |               0 |                       0 |                             0 |                  48 |
| T20I                |               10 |                   822 |               0 |                      36 |                            36 |                  60 |

## IPL league: TSP by stage of season (stakes should spread out late: must-wins up, dead rubbers to 0)
| block      |   mean |   min |   25% |   50% |   75% |   max |
|:-----------|-------:|------:|------:|------:|------:|------:|
| games 1-14 |    5.9 |   3.7 |   5.8 |   6.1 |   6.2 |   7.7 |
| 15-28      |    5.9 |   2.5 |   4.3 |   6.5 |   7.4 |   8.2 |
| 29-42      |    5.7 |   1   |   4   |   6.1 |   7.7 |   8.5 |
| 43-56      |    5.9 |   0.3 |   4.1 |   6.8 |   8   |   9.2 |
| 57-71      |    6.1 |   0.1 |   3.4 |   6.9 |   8.5 |   9.7 |

IPL league games that were dead rubbers for a team (TSP < 0.5): 87 team-games

IPL knockouts (exact):
| stage      |   tsp_100 |
|:-----------|----------:|
| Eliminator |      25   |
| Final      |     100   |
| Qualifier  |      37.5 |

Highest-stakes IPL league games:
| comp_name   |   match_number | team                        |   points_before |   rank_before |   p_title_if_win |   p_title_if_lose |   tsp_100 |
|:------------|---------------:|:----------------------------|----------------:|--------------:|-----------------:|------------------:|----------:|
| IPL 2024    |             70 | Rajasthan Royals            |              16 |             3 |            0.375 |             0.125 |    25     |
| IPL 2025    |             71 | Royal Challengers Bengaluru |              17 |             3 |            0.375 |             0.125 |    25     |
| IPL 2025    |             70 | Mumbai Indians              |              16 |             4 |            0.358 |             0.121 |    23.725 |
| IPL 2023    |             67 | Chennai Super Kings         |              15 |             2 |            0.349 |             0.129 |    21.959 |
| IPL 2023    |             63 | Mumbai Indians              |              14 |             3 |            0.293 |             0.087 |    20.625 |
| IPL 2023    |             63 | Lucknow Super Giants        |              13 |             4 |            0.221 |             0.041 |    17.966 |
| IPL 2022    |             68 | Rajasthan Royals            |              16 |             3 |            0.292 |             0.114 |    17.834 |
| IPL 2026    |             67 | Sunrisers Hyderabad         |              16 |             3 |            0.3   |             0.125 |    17.538 |
| IPL 2023    |             68 | Lucknow Super Giants        |              15 |             3 |            0.268 |             0.093 |    17.462 |
| IPL 2026    |             63 | Sunrisers Hyderabad         |              14 |             3 |            0.282 |             0.113 |    16.806 |

Rajasthan Royals, last 4 league games each season:
| comp_name   |   match_number |   points_before |   rank_before |   p_title_if_win |   p_title_if_lose |   tsp_100 |
|:------------|---------------:|----------------:|--------------:|-----------------:|------------------:|----------:|
| IPL 2022    |             52 |              12 |             3 |            0.226 |             0.11  |    11.619 |
| IPL 2022    |             58 |              14 |             3 |            0.265 |             0.161 |    10.444 |
| IPL 2022    |             63 |              14 |             3 |            0.23  |             0.083 |    14.65  |
| IPL 2022    |             68 |              16 |             3 |            0.292 |             0.114 |    17.834 |
| IPL 2023    |             52 |              10 |             4 |            0.134 |             0.045 |     8.853 |
| IPL 2023    |             56 |              10 |             5 |            0.069 |             0.012 |     5.669 |
| IPL 2023    |             60 |              12 |             5 |            0.099 |             0.017 |     8.172 |
| IPL 2023    |             66 |              12 |             6 |            0.011 |             0     |     1.1   |
| IPL 2024    |             56 |              16 |             1 |            0.372 |             0.35  |     2.194 |
| IPL 2024    |             61 |              16 |             2 |            0.371 |             0.332 |     3.859 |
| IPL 2024    |             65 |              16 |             2 |            0.364 |             0.303 |     6.106 |
| IPL 2024    |             70 |              16 |             3 |            0.375 |             0.125 |    25     |
| IPL 2025    |             50 |               6 |             8 |            0     |             0     |     0.006 |
| IPL 2025    |             53 |               6 |             8 |            0     |             0     |     0     |
| IPL 2025    |             60 |               6 |             9 |            0     |             0     |     0     |
| IPL 2025    |             63 |               6 |             9 |            0     |             0     |     0     |
| IPL 2026    |             52 |              12 |             3 |            0.246 |             0.102 |    14.388 |
| IPL 2026    |             62 |              12 |             5 |            0.163 |             0.053 |    10.962 |
| IPL 2026    |             64 |              12 |             5 |            0.084 |             0.013 |     7.075 |
| IPL 2026    |             69 |              14 |             5 |            0.125 |             0     |    12.5   |

## Bilateral T20I series: mean TSP by match number in series
|   n |   mean |   count |
|----:|-------:|--------:|
|   1 |   47.4 |     246 |
|   2 |   47.1 |     244 |
|   3 |   38.6 |     218 |
|   4 |   36.7 |      58 |
|   5 |   38.5 |      52 |
|   6 |   50.6 |       2 |
|   7 |  100   |       2 |