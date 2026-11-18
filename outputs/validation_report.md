# Data validation report

## 1. Total runs per delivery = runs + extras1_runs + extras_2_runs
- Won-by-runs matches (no DLS): 400; first-innings minus second-innings total equals the stated margin in **99.8%**
- Mismatches (1): 28962 (off by -10; result: 'India Won Super Over By 10 Runs')
  -> a margin quoted from a Super Over on a tied match is not a data error; regular innings are a tie.
- Won-by-wickets matches: 401; 10 minus second-innings wickets equals the stated margin in **99.8%**; chasing total exceeds first-innings total in **99.8%**

## 2. Is extras_type == 'other' a no-ball? (test using over structure)
- Scenario A: other = legal: completed overs containing an 'other' ball that have exactly 6 legal balls = **0.0%** (n=216); all completed overs = 99.3%
- Scenario B: other = no-ball: completed overs containing an 'other' ball that have exactly 6 legal balls = **100.0%** (n=216); all completed overs = 100.0%

## 3. Revised innings lengths (first_inn_revised_overs / second_inn_revised_overs)
- Innings 1: 25 played innings with a revised value. Legal balls <= value (read as BALLS): **100%**; reached the value exactly: 60% (the rest are chases won early, all-outs or rain-stopped games). Read as overs the values would be 30-114 overs (impossible in T20); read as balls they are 5-19 overs -> values are BALLS.
- Innings 2: 23 played innings with a revised value. Legal balls <= value (read as BALLS): **100%**; reached the value exactly: 57% (the rest are chases won early, all-outs or rain-stopped games). Read as overs the values would be 30-114 overs (impossible in T20); read as balls they are 5-19 overs -> values are BALLS.
- revised_target: 23 matches. Equals first-innings total + 1 in 35% (others are DLS-adjusted). In every chase won by wickets the chasing total reaches it: **100%** -> it is the runs-to-WIN target.
- Per-match detail: outputs/validation_revised_matches.csv

## 4. Structural checks
- Duplicate (match, innings, innings_ball_num) keys: 0
- Innings with >120 legal balls: 0; with >10 wickets: 0
- Matches with only one innings recorded: 22
- Matches without deliveries (abandoned/no result): 16
- Competitions classified as IPL: ['IPL 2022', 'IPL 2023', 'IPL 2024', 'IPL 2025', 'IPL 2026']
- Deliveries by group: {'T20I': 106315, 'IPL': 87673, 'Other T20': 6973}
- Stage values: {'League': 620, 'Others': 226, 'Final': 12, 'Qualifier': 10, 'Super 4': 6, 'Eliminator': 5, 'Semi Final': 4}; knock_out flag set on 31 matches