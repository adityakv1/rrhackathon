"""Central configuration: paths, thresholds and cricket-domain constants."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

REGULAR_INNINGS = (1, 2)          # 3/4 are Super Overs, analysed separately
T20_MAX_BALLS = 120

# Credited to the bowler. RunOut / Retire Out / Obstructing are NOT.
BOWLER_WICKETS = {"Caught", "Bowled", "LBW", "Stump", "Hit Wicket"}
NOT_BATTER_DISMISSALS = {"Retire Out"}  # not a true dismissal for batting average

# extras_type values. 'other' is resolved empirically in validate.py (see OTHER_AS_NO_BALL).
WIDE = "wide"
NO_BALL = "Overstep"
OTHER = "other"
# Validated in src/validate.py check 2: with 'other' as a no-ball, 100% of completed overs
# containing one have exactly 6 legal balls (0% if treated as legal). Its scoring pattern
# (bat runs + 1 extra) also matches 'Overstep'. So Scenario B is now the evidence-based baseline;
# set False to reproduce the earlier Scenario A numbers.
OTHER_AS_NO_BALL = True

PHASES = {"Powerplay": (1, 6), "Middle": (7, 16), "Death": (17, 20)}

QUAL_BATTING = {"innings": 15, "balls": 200}
QUAL_BOWLING = {"IPL": (15, 300), "T20I": (15, 300), "Other T20": (4, 72)}
QUAL_PHASE = {"IPL": (10, 60), "T20I": (10, 60), "Other T20": (3, 18)}
