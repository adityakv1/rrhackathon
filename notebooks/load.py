import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Dataset location
DATA_PATH = "../data/raw/"

# Load datasets
competitions = pd.read_csv(DATA_PATH + "competitions.csv")
teams = pd.read_csv(DATA_PATH + "teams.csv")
matches = pd.read_csv(DATA_PATH + "matches.csv")
ball = pd.read_csv(DATA_PATH + "ball_by_ball.csv")
playing_eleven = pd.read_csv(DATA_PATH + "playing_eleven.csv")
player_mapping = pd.read_csv(
    DATA_PATH + "competition_team_player_mapping.csv"
)

print("All datasets loaded successfully!")
datasets = {
    "Competitions": competitions,
    "Teams": teams,
    "Matches": matches,
    "Ball by Ball": ball,
    "Playing Eleven": playing_eleven,
    "Player Mapping": player_mapping
}

for name, df in datasets.items():
    print("\n", "=" * 50)
    print(name)
    print("Rows:", df.shape[0])
    print("Columns:", df.shape[1])
    print(df.columns.tolist())

print("Competition formats:")
print(competitions["match_format"].value_counts())

print("\nCompetition seasons:")
print(competitions["season"].value_counts())

print("\nMatch stages:")
print(matches["stage"].value_counts())

print("\nInnings distribution:")
print(ball["innings"].value_counts())

# Check the number of matches containing Super Overs

super_over = ball[ball["innings"] > 2]

print("Super Over deliveries:", len(super_over))

print("Matches with Super Overs:")
print(super_over["match_id"].nunique())

print("Innings-wise Super Over distribution:")
print(super_over.groupby("innings")["match_id"].nunique())
# Check missing values in each dataset

for name, df in datasets.items():
    print("\n", name)
    print(df.isnull().sum()[df.isnull().sum() > 0])

print("Duplicate matches:", matches.duplicated().sum())

print("Duplicate ball-by-ball rows:", ball.duplicated().sum())

print("Duplicate player mapping rows:", player_mapping.duplicated().sum())
print("Matches in matches.csv:", matches["match_id"].nunique())

print("Matches in ball_by_ball.csv:", ball["match_id"].nunique())

print("Matches without ball-by-ball data:",
      len(set(matches["match_id"]) - set(ball["match_id"])))
# Check whether a delivery is uniquely identified

delivery_duplicates = ball.duplicated(
    subset=["match_id", "innings", "innings_ball_num"]
).sum()

print("Duplicate delivery keys:", delivery_duplicates)
# Find matches that have no ball-by-ball records

matches_with_no_balls = matches[
    ~matches["match_id"].isin(ball["match_id"])
]

print("Matches without ball-by-ball data:")
print(
    matches_with_no_balls[
        ["match_id", "comp_id", "match_date",
         "home_team", "away_team", "stage", "result"]
    ].to_string(index=False)
)

# Regular innings
regular_innings = ball[ball["innings"].isin([1, 2])].copy()

# Super Over innings
super_over = ball[ball["innings"].isin([3, 4])].copy()

print("Regular deliveries:", len(regular_innings))
print("Super Over deliveries:", len(super_over))
print(regular_innings[
    ["runs", "extras_type", "extras1_runs", "extras_2_runs"]
].head(15))
print("Extras types:")
print(regular_innings["extras_type"].value_counts(dropna=False))

print("\nRuns distribution:")
print(regular_innings["runs"].value_counts().sort_index())

# Examine scoring by extras type

extras_analysis = regular_innings.groupby(
    "extras_type", dropna=False
).agg(
    deliveries=("runs", "count"),
    batter_runs=("runs", "sum"),
    extras1=("extras1_runs", "sum"),
    extras2=("extras_2_runs", "sum")
)

extras_analysis["total_runs"] = (
    extras_analysis["batter_runs"]
    + extras_analysis["extras1"]
    + extras_analysis["extras2"]
)

print(extras_analysis)
# Inspect unusual scoring records

print("Leg-bye deliveries with batter runs:")
print(
    regular_innings[
        (regular_innings["extras_type"] == "legbyes") &
        (regular_innings["runs"] != 0)
    ][[
        "match_id", "innings", "runs",
        "extras_type", "extras1_runs", "extras_2_runs"
    ]].head(10)
)

print("\nOther extras:")
print(
    regular_innings[
        regular_innings["extras_type"] == "other"
    ][[
        "runs", "extras_type",
        "extras1_runs", "extras_2_runs"
    ]].head(10)
)

print("\nNo extras but non-zero extra runs:")
print(
    regular_innings[
        regular_innings["extras_type"].isna() &
        (
            (regular_innings["extras1_runs"] != 0) |
            (regular_innings["extras_2_runs"] != 0)
        )
    ][[
        "runs", "extras_type",
        "extras1_runs", "extras_2_runs"
    ]].head(10)
)
# Flag unusual scoring records

regular_innings["scoring_anomaly"] = False

# Leg-byes should not have batter runs
regular_innings.loc[
    (regular_innings["extras_type"] == "legbyes") &
    (regular_innings["runs"] > 0),
    "scoring_anomaly"
] = True

# Extras recorded without an extras type
regular_innings.loc[
    regular_innings["extras_type"].isna() &
    (
        (regular_innings["extras1_runs"] > 0) |
        (regular_innings["extras_2_runs"] > 0)
    ),
    "scoring_anomaly"
] = True

print("Suspicious deliveries:",
      regular_innings["scoring_anomaly"].sum())

print(regular_innings[
    regular_innings["scoring_anomaly"]
][[
    "match_id", "innings", "runs",
    "extras_type", "extras1_runs", "extras_2_runs"
]])

quality_report = {
    "total_deliveries": len(ball),
    "duplicate_deliveries": ball.duplicated().sum(),
    "duplicate_delivery_keys": ball.duplicated(
        subset=["match_id", "innings", "innings_ball_num"]
    ).sum(),
    "missing_ball_by_ball_matches": 16,
    "suspicious_scoring_records": int(
        regular_innings["scoring_anomaly"].sum()
    )
}

print(pd.Series(quality_report))

# Examine delivery types and legal delivery indicators

print("Extras types:")
print(regular_innings["extras_type"].value_counts(dropna=False))

print("\nOverstep records:")
print(
    regular_innings[
        regular_innings["extras_type"] == "Overstep"
    ][["runs", "extras1_runs", "extras_2_runs"]].head(10)
)

print("\nWide records:")
print(
    regular_innings[
        regular_innings["extras_type"] == "wide"
    ][["runs", "extras1_runs", "extras_2_runs"]].head(10)
)
# Create a column indicating whether a ball counts as faced

regular_innings["ball_faced"] = (
    regular_innings["extras_type"] != "wide"
).astype(int)

# Check our results
print("Total deliveries:", len(regular_innings))
print("Balls faced:", regular_innings["ball_faced"].sum())
print("Wides:", (regular_innings["extras_type"] == "wide").sum())

batting_stats = regular_innings.groupby(
    ["striker_id", "striker_name"]
).agg(
    runs=("runs", "sum"),
    balls_faced=("ball_faced", "sum"),
    fours=("is_four", "sum"),
    sixes=("is_six", "sum")
).reset_index()

# Calculate strike rate
batting_stats["strike_rate"] = (
    batting_stats["runs"] /
    batting_stats["balls_faced"].replace(0, np.nan)
) * 100

# Display top 10 run scorers
print(
    batting_stats.sort_values(
        "runs", ascending=False
    ).head(10).to_string(index=False)
)
print("Wicket indicator distribution:")
print(regular_innings["is_wicket"].value_counts(dropna=False))

print("\nDismissal types:")
print(regular_innings["dismissal_type"].value_counts(dropna=False))

dismissals = (
    regular_innings[
        regular_innings["is_wicket"] == 1
    ]
    .groupby("dismissed_player_id")
    .size()
    .reset_index(name="dismissals")
)

print(dismissals.head())

print("Wicket indicator:")
print(regular_innings["is_wicket"].value_counts(dropna=False))

print("\nWickets without dismissed player ID:")
print(
    regular_innings[
        (regular_innings["is_wicket"] == 1) &
        (regular_innings["dismissed_player_id"].isna())
    ].shape[0]
)

# Merge dismissal counts with batting statistics

batting_stats = batting_stats.merge(
    dismissals,
    left_on="striker_id",
    right_on="dismissed_player_id",
    how="left"
)

# Players with no dismissals get zero
batting_stats["dismissals"] = (
    batting_stats["dismissals"].fillna(0)
)

# Calculate batting average
batting_stats["batting_average"] = (
    batting_stats["runs"] /
    batting_stats["dismissals"].replace(0, np.nan)
)

# Display top 10 by batting average
print(
    batting_stats[
        batting_stats["dismissals"] >= 10
    ].sort_values(
        "batting_average", ascending=False
    )[[
        "striker_name", "runs", "dismissals",
        "batting_average", "strike_rate"
    ]].head(10).to_string(index=False)
)

# Calculate each player's score in each innings

batting_innings = regular_innings.groupby(
    ["striker_id", "striker_name", "match_id", "innings"]
).agg(
    innings_runs=("runs", "sum"),
    balls_faced=("ball_faced", "sum")
).reset_index()

print(batting_innings.head(10))

consistency_stats = batting_innings.groupby(
    ["striker_id", "striker_name"]
).agg(
    innings_played=("innings_runs", "count"),
    average_score=("innings_runs", "mean"),
    median_score=("innings_runs", "median"),
    score_std=("innings_runs", "std"),
    scores_30_plus=("innings_runs", lambda x: (x >= 30).sum()),
    scores_50_plus=("innings_runs", lambda x: (x >= 50).sum()),
    ducks=("innings_runs", lambda x: (x == 0).sum())
).reset_index()

# Add total batting statistics to consistency statistics

player_consistency = consistency_stats.merge(
    batting_stats[
        ["striker_id", "runs", "balls_faced",
         "strike_rate", "batting_average"]
    ],
    on="striker_id",
    how="left"
)

# Filter players with sufficient batting opportunities

qualified_batters = player_consistency[
    (player_consistency["innings_played"] >= 20) &
    (player_consistency["balls_faced"] >= 300)
].copy()

print("Qualified batters:", len(qualified_batters))

# Display the most consistent qualified batters

print(
    qualified_batters.sort_values(
        "score_std"
    )[[
        "striker_name",
        "innings_played",
        "runs",
        "balls_faced",
        "average_score",
        "score_std",
        "scores_30_plus",
        "scores_50_plus",
        "ducks"
    ]].head(15).to_string(index=False)
)

qualified_batters["30_plus_rate"] = (
    qualified_batters["scores_30_plus"] /
    qualified_batters["innings_played"]
) * 100

qualified_batters["duck_rate"] = (
    qualified_batters["ducks"] /
    qualified_batters["innings_played"]
) * 100

print(
    qualified_batters.sort_values(
        "30_plus_rate", ascending=False
    )[[
        "striker_name",
        "innings_played",
        "average_score",
        "strike_rate",
        "30_plus_rate",
        "duck_rate"
    ]].head(15).to_string(index=False)
)
# Explore competition names and formats

print(
    competitions[
        ["comp_name", "match_format", "season"]
    ].sort_values(
        ["match_format", "season"]
    ).to_string(index=False)
)
# Count matches by competition

match_competitions = matches.merge(
    competitions[
        ["comp_id", "comp_name", "match_format", "season"]
    ],
    on="comp_id",
    how="left"
)

print(
    match_competitions.groupby(
        ["comp_name", "match_format"]
    ).size().sort_values(
        ascending=False
    ).head(25)
)
# Attach competition information to every match

match_info = matches.merge(
    competitions[
        ["comp_id", "comp_name", "match_format", "season"]
    ],
    on="comp_id",
    how="left"
)

# Attach competition information to ball-by-ball data

all_data = regular_innings.merge(
    match_info[
        ["match_id", "comp_id", "comp_name",
         "match_format", "season"]
    ],
    on="match_id",
    how="left"
)

print("Total records:", len(all_data))

print("\nCompetition formats:")
print(all_data["match_format"].value_counts())

print("\nTop competitions by delivery count:")
print(all_data["comp_name"].value_counts().head(15))
# Create competition categories

all_data["competition_group"] = np.select(
    [
        all_data["comp_name"].str.contains(
            "IPL", case=False, na=False
        ),
        all_data["match_format"] == "T20I"
    ],
    [
        "IPL",
        "T20I"
    ],
    default="Other T20"
)

# Check distribution

print(
    all_data.groupby("competition_group").agg(
        deliveries=("match_id", "size"),
        matches=("match_id", "nunique"),
        competitions=("comp_name", "nunique")
    )
)
# Find IPL matches missing from our ball-by-ball dataset
# Identify IPL competitions
ipl_competitions = competitions[
    competitions["comp_name"].str.contains(
        "IPL", case=False, na=False
    )
]

# Extract IPL competition IDs
ipl_comp_ids = ipl_competitions["comp_id"].unique()

# Identify IPL matches
ipl_matches = matches[
    matches["comp_id"].isin(ipl_comp_ids)
]

# Identify IPL match IDs
ipl_match_ids = ipl_matches["match_id"].unique()

# Create IPL ball-by-ball dataset
ipl_ball = ball[
    ball["match_id"].isin(ipl_match_ids)
].copy()

# Keep regular innings
ipl_regular = ipl_ball[
    ipl_ball["innings"].isin([1, 2])
].copy()
ipl_matches_missing = ipl_matches[
    ~ipl_matches["match_id"].isin(
        ipl_regular["match_id"]
    )
]

print(
    ipl_matches_missing[
        ["match_id", "match_date", "home_team",
         "away_team", "stage", "result"]
    ].to_string(index=False)
)

print("\nNumber of missing IPL matches:",
      len(ipl_matches_missing))

# Aggregate batting performance by player and competition

competition_batting = all_data.groupby(
    ["striker_id", "striker_name", "competition_group"]
).agg(
    runs=("runs", "sum"),
    balls_faced=("ball_faced", "sum"),
    fours=("is_four", "sum"),
    sixes=("is_six", "sum"),
    matches=("match_id", "nunique")
).reset_index()

# Calculate strike rate

competition_batting["strike_rate"] = (
    competition_batting["runs"] /
    competition_batting["balls_faced"].replace(0, np.nan)
) * 100

print(competition_batting.head(15))

# Count dismissals by player and competition

dismissals_by_comp = (
    all_data[
        (all_data["is_wicket"] == 1) &
        (all_data["dismissed_player_id"].notna())
    ]
    .groupby([
        "dismissed_player_id",
        "competition_group"
    ])
    .size()
    .reset_index(name="dismissals")
)

print(dismissals_by_comp.head(10))

# Merge dismissals into batting performance table

competition_batting = competition_batting.merge(
    dismissals_by_comp,
    left_on=["striker_id", "competition_group"],
    right_on=["dismissed_player_id", "competition_group"],
    how="left"
)

competition_batting["dismissals"] = (
    competition_batting["dismissals"].fillna(0)
)

# Calculate batting average

competition_batting["batting_average"] = (
    competition_batting["runs"] /
    competition_batting["dismissals"].replace(0, np.nan)
)

print(
    competition_batting[
        ["striker_name", "competition_group",
         "runs", "dismissals",
         "batting_average", "strike_rate"]
    ].head(20).to_string(index=False)
)
# Calculate individual batting innings

competition_innings = all_data.groupby(
    [
        "striker_id",
        "striker_name",
        "competition_group",
        "match_id",
        "innings"
    ]
).agg(
    innings_runs=("runs", "sum"),
    balls_faced=("ball_faced", "sum")
).reset_index()

print(competition_innings.head(10))

competition_consistency = competition_innings.groupby(
    ["striker_id", "striker_name", "competition_group"]
).agg(
    innings_played=("innings_runs", "count"),
    average_score=("innings_runs", "mean"),
    median_score=("innings_runs", "median"),
    score_std=("innings_runs", "std"),
    scores_30_plus=("innings_runs", lambda x: (x >= 30).sum()),
    scores_50_plus=("innings_runs", lambda x: (x >= 50).sum()),
    ducks=("innings_runs", lambda x: (x == 0).sum())
).reset_index()

# Calculate contribution rates

competition_consistency["30_plus_rate"] = (
    competition_consistency["scores_30_plus"] /
    competition_consistency["innings_played"]
) * 100

competition_consistency["duck_rate"] = (
    competition_consistency["ducks"] /
    competition_consistency["innings_played"]
) * 100

print(competition_consistency.head(15).to_string(index=False))
# Combine batting performance and consistency metrics

batting_profile = competition_batting.merge(
    competition_consistency,
    on=[
        "striker_id",
        "striker_name",
        "competition_group"
    ],
    how="left"
)

print("Batting profile shape:", batting_profile.shape)

print(batting_profile.head(10).to_string(index=False))
# Calculate scoring contribution rates

batting_profile["50_plus_rate"] = (
    batting_profile["scores_50_plus"] /
    batting_profile["innings_played"]
) * 100

batting_profile["boundary_runs"] = (
    batting_profile["fours"] * 4 +
    batting_profile["sixes"] * 6
)

batting_profile["boundary_percentage"] = (
    batting_profile["boundary_runs"] /
    batting_profile["runs"].replace(0, np.nan)
) * 100

print(
    batting_profile[[
        "striker_name",
        "competition_group",
        "runs",
        "batting_average",
        "strike_rate",
        "average_score",
        "30_plus_rate",
        "50_plus_rate",
        "duck_rate",
        "boundary_percentage"
    ]].head(15).to_string(index=False)
)
qualified_batting = batting_profile[
    (batting_profile["innings_played"] >= 15) &
    (batting_profile["balls_faced"] >= 200)
].copy()

print("Qualified batting profiles:", len(qualified_batting))

print(
    qualified_batting[
        [
            "striker_name",
            "competition_group",
            "innings_played",
            "runs",
            "batting_average",
            "strike_rate",
            "30_plus_rate",
            "50_plus_rate",
            "duck_rate"
        ]
    ].sort_values(
        by="innings_played",
        ascending=False
    ).head(20).to_string(index=False)
)

# Check dismissal types
print("DISMISSAL TYPES")
print(
    regular_innings[
        regular_innings["is_wicket"] == 1
    ]["dismissal_type"]
    .value_counts(dropna=False)
)

# Check extras types
print("\nEXTRAS TYPES")
print(
    regular_innings["extras_type"]
    .value_counts(dropna=False)
)

# Inspect the extras columns
print("\nEXTRAS BREAKDOWN")
print(
    regular_innings.groupby(
        "extras_type",
        dropna=False
    )[["runs", "extras1_runs", "extras_2_runs"]]
    .sum()
)
# Inspect examples of each extras type

for extra in ["Overstep", "wide", "byes", "legbyes", "other", "Penalty"]:

    print(f"\n========== {extra} ==========")

    sample = regular_innings[
        regular_innings["extras_type"] == extra
    ][
        [
            "match_id",
            "innings",
            "overid",
            "striker_name",
            "bowler_name",
            "runs",
            "extras_type",
            "extras1_runs",
            "extras_2_runs",
            "is_four",
            "is_six",
            "is_wicket",
            "dismissal_type"
        ]
    ].head(5)

    print(sample.to_string(index=False))
print(
    regular_innings[
        regular_innings["extras_type"].isna() &
        (
            (regular_innings["extras1_runs"] != 0) |
            (regular_innings["extras_2_runs"] != 0)
        )
    ][
        [
            "match_id",
            "striker_name",
            "bowler_name",
            "runs",
            "extras1_runs",
            "extras_2_runs"
        ]
    ].to_string(index=False)
)
# Examine all combinations of extras and runs

print(
    regular_innings.groupby(
        [
            "extras_type",
            "runs",
            "extras1_runs",
            "extras_2_runs"
        ],
        dropna=False
    ).size()
    .reset_index(name="delivery_count")
    .sort_values(
        by="delivery_count",
        ascending=False
    )
    .to_string(index=False)
)
other_deliveries = regular_innings[
    regular_innings["extras_type"] == "other"
]

print(
    other_deliveries[
        [
            "match_id",
            "innings",
            "overid",
            "over_ball_num",
            "striker_name",
            "bowler_name",
            "runs",
            "extras1_runs",
            "extras_2_runs",
            "is_wicket",
            "dismissal_type"
        ]
    ].to_string(index=False)
)

# Create a copy of regular innings
bowling_data = regular_innings.copy()

# 1. Identify wides and no-balls
bowling_data["is_wide"] = (
    bowling_data["extras_type"] == "wide"
).astype(int)

bowling_data["is_no_ball"] = (
    bowling_data["extras_type"] == "Overstep"
).astype(int)

# 2. Legal deliveries
bowling_data["legal_ball"] = (
    (bowling_data["is_wide"] == 0) &
    (bowling_data["is_no_ball"] == 0)
).astype(int)

# 3. Runs conceded by bowler
bowling_data["bowler_runs"] = (
    bowling_data["runs"].fillna(0)
    + bowling_data["extras1_runs"].fillna(0).where(
        bowling_data["extras_type"].isin(["wide", "Overstep"]), 0
    )
    + bowling_data["extras_2_runs"].fillna(0).where(
        bowling_data["extras_type"].isin(["wide", "Overstep"]), 0
    )
)

# 4. Wickets credited to bowler
bowler_wicket_types = [
    "Caught",
    "Bowled",
    "LBW",
    "Stump",
    "Hit Wicket"
]

bowling_data["bowler_wicket"] = (
    bowling_data["dismissal_type"]
    .isin(bowler_wicket_types)
).astype(int)

# 5. Diagnostic: other extras
bowling_data["other_extra"] = (
    bowling_data["extras_type"] == "other"
).astype(int)

print("Bowling data created!")
print(
    bowling_data[
        [
            "bowler_name",
            "legal_ball",
            "bowler_runs",
            "bowler_wicket",
            "other_extra"
        ]
    ].head(10)
)

bowling_stats = bowling_data.groupby(
    ["bowler_id", "bowler_name"]
).agg(
    legal_balls=("legal_ball", "sum"),
    runs_conceded=("bowler_runs", "sum"),
    wickets=("bowler_wicket", "sum"),
    other_extras=("other_extra", "sum")
).reset_index()

# Economy rate
bowling_stats["economy"] = (
    bowling_stats["runs_conceded"] /
    (bowling_stats["legal_balls"] / 6)
)

# Bowling average
bowling_stats["bowling_average"] = (
    bowling_stats["runs_conceded"] /
    bowling_stats["wickets"].replace(0, np.nan)
)

# Bowling strike rate
bowling_stats["bowling_strike_rate"] = (
    bowling_stats["legal_balls"] /
    bowling_stats["wickets"].replace(0, np.nan)
)

print(
    bowling_stats.sort_values(
        "wickets",
        ascending=False
    ).head(20).to_string(index=False)
)
# Total runs scored by each batting team in each innings
innings_totals = regular_innings.groupby(
    ["match_id", "innings"]
).agg(
    team_runs=(
        "runs",
        "sum"
    ),
    extras1=(
        "extras1_runs",
        "sum"
    ),
    extras2=(
        "extras_2_runs",
        "sum"
    )
).reset_index()

innings_totals["team_total"] = (
    innings_totals["team_runs"]
    + innings_totals["extras1"]
    + innings_totals["extras2"]
)

# Runs currently charged to bowlers
bowler_totals = bowling_data.groupby(
    ["match_id", "innings"]
).agg(
    bowler_runs=("bowler_runs", "sum")
).reset_index()

# Compare the two
validation = innings_totals.merge(
    bowler_totals,
    on=["match_id", "innings"],
    how="inner"
)

validation["unallocated_runs"] = (
    validation["team_total"]
    - validation["bowler_runs"]
)

print("Total innings checked:", len(validation))

print("\nTOTAL TEAM RUNS:")
print(validation["team_total"].sum())

print("\nTOTAL BOWLER RUNS:")
print(validation["bowler_runs"].sum())

print("\nRUNS NOT CHARGED TO BOWLERS:")
print(validation["unallocated_runs"].sum())

print("\nLARGEST UNALLOCATED RUN DIFFERENCES:")
print(
    validation.sort_values(
        "unallocated_runs",
        ascending=False
    ).head(10).to_string(index=False)
)
# Check delivery numbering for other extras

other_data = regular_innings[
    regular_innings["extras_type"] == "other"
].copy()

print("OTHER EXTRAS: DELIVERY NUMBER DISTRIBUTION")

print(
    other_data["over_ball_num"]
    .value_counts()
    .sort_index()
)

print("\nOTHER EXTRAS: LEGAL BALL INDICATOR")

print(
    other_data.groupby("over_ball_num")
    .size()
)

print("\nOTHER EXTRAS: SAMPLE RECORDS")

print(
    other_data[
        [
            "match_id",
            "innings",
            "overid",
            "over_ball_num",
            "innings_ball_num",
            "runs",
            "extras1_runs",
            "extras_2_runs"
        ]
    ].head(20).to_string(index=False)
)
print("OTHER EXTRAS: OVER BALL NUMBER")

print(
    other_data["over_ball_num"]
    .value_counts()
    .sort_index()
)

print("\nOTHER EXTRAS: COUNTS BY BALL NUMBER")

print(
    other_data.groupby(
        "over_ball_num"
    ).agg(
        deliveries=("match_id", "size"),
        total_runs=("runs", "sum"),
        extra1=("extras1_runs", "sum"),
        extra2=("extras_2_runs", "sum")
    ).to_string()
)
print(
    other_data[
        [
            "extras_type",
            "extras1_runs",
            "extras_2_runs",
            "pace_or_spin",
            "delivery_style",
            "dismissal_type"
        ]
    ].value_counts(dropna=False).head(20)
)
# Full distribution of delivery styles for other extras

print(
    other_data["delivery_style"]
    .value_counts(dropna=False)
)

print("\nDelivery style and extras breakdown:")

print(
    other_data.groupby(
        ["delivery_style", "extras1_runs", "extras_2_runs"],
        dropna=False
    ).size().reset_index(name="count")
    .sort_values("count", ascending=False)
    .to_string(index=False)
)
print(
    "Total other deliveries:", len(other_data)
)

print(
    "Beamer deliveries:",
    (other_data["delivery_style"] == "Beamer").sum()
)

print(
    "Other extras with missing delivery style:",
    other_data["delivery_style"].isna().sum()
)
# Inspect other extras with ball number above 6

print(
    other_data[
        other_data["over_ball_num"] > 6
    ][
        [
            "match_id",
            "innings",
            "overid",
            "over_ball_num",
            "innings_ball_num",
            "bowler_name",
            "runs",
            "extras1_runs",
            "extras_2_runs",
            "delivery_style",
            "bowl_speed"
        ]
    ].to_string(index=False)
)
print([
    col for col in regular_innings.columns
    if any(
        word in col.lower()
        for word in ["noball", "no_ball", "wide", "penalty", "extra"]
    )
])
# Scenario A: Treat "other" as unresolved
scenario_a = bowling_data.copy()

# Scenario B: Treat "other" as a no-ball
scenario_b = bowling_data.copy()

scenario_b["legal_ball"] = (
    (scenario_b["is_wide"] == 0) &
    (scenario_b["is_no_ball"] == 0) &
    (scenario_b["other_extra"] == 0)
).astype(int)

scenario_b["bowler_runs"] = (
    scenario_b["runs"].fillna(0)
    + scenario_b["extras1_runs"].fillna(0).where(
        scenario_b["extras_type"].isin(
            ["wide", "Overstep", "other"]
        ), 0
    )
    + scenario_b["extras_2_runs"].fillna(0).where(
        scenario_b["extras_type"].isin(
            ["wide", "Overstep", "other"]
        ), 0
    )
)


def calculate_bowling_metrics(data):
    stats = data.groupby(
        ["bowler_id", "bowler_name"]
    ).agg(
        legal_balls=("legal_ball", "sum"),
        runs_conceded=("bowler_runs", "sum"),
        wickets=("bowler_wicket", "sum")
    ).reset_index()

    stats["economy"] = (
        stats["runs_conceded"] /
        (stats["legal_balls"] / 6)
    )

    stats["bowling_average"] = (
        stats["runs_conceded"] /
        stats["wickets"].replace(0, np.nan)
    )

    stats["bowling_strike_rate"] = (
        stats["legal_balls"] /
        stats["wickets"].replace(0, np.nan)
    )

    return stats


metrics_a = calculate_bowling_metrics(scenario_a)
metrics_b = calculate_bowling_metrics(scenario_b)

print("SCENARIO A — Other unresolved")
print(metrics_a.nlargest(10, "wickets").to_string(index=False))

print("\nSCENARIO B — Other treated as no-ball")
print(metrics_b.nlargest(10, "wickets").to_string(index=False))
# Attach competition information to bowling data
bowling_comp = scenario_a.merge(
    all_data[["match_id", "competition_group"]].drop_duplicates(),
    on="match_id",
    how="left"
)

# Calculate bowling performance separately by competition
competition_bowling = bowling_comp.groupby(
    ["bowler_id", "bowler_name", "competition_group"]
).agg(
    matches=("match_id", "nunique"),
    legal_balls=("legal_ball", "sum"),
    runs_conceded=("bowler_runs", "sum"),
    wickets=("bowler_wicket", "sum")
).reset_index()

# Calculate bowling metrics
competition_bowling["economy"] = (
    competition_bowling["runs_conceded"] /
    (competition_bowling["legal_balls"] / 6)
)

competition_bowling["bowling_average"] = (
    competition_bowling["runs_conceded"] /
    competition_bowling["wickets"].replace(0, np.nan)
)

competition_bowling["bowling_strike_rate"] = (
    competition_bowling["legal_balls"] /
    competition_bowling["wickets"].replace(0, np.nan)
)

# Focus on IPL
ipl_bowling = competition_bowling[
    competition_bowling["competition_group"] == "IPL"
].copy()

# Show the leading IPL wicket-takers
print(
    ipl_bowling.nlargest(20, "wickets")[
        [
            "bowler_name", "matches", "legal_balls",
            "runs_conceded", "wickets", "economy",
            "bowling_average", "bowling_strike_rate"
        ]
    ].to_string(index=False)
)
# Minimum sample qualification
qualified_bowling = competition_bowling[
    (competition_bowling["matches"] >= 10) &
    (competition_bowling["legal_balls"] >= 300)
].copy()

# Sort by competition and wickets
qualified_bowling = qualified_bowling.sort_values(
    ["competition_group", "wickets"],
    ascending=[True, False]
)

for competition in ["IPL", "T20I", "Other T20"]:

    print(f"\n========== {competition} ==========")

    result = qualified_bowling[
        qualified_bowling["competition_group"] == competition
    ][[
        "bowler_name",
        "matches",
        "legal_balls",
        "runs_conceded",
        "wickets",
        "economy",
        "bowling_average",
        "bowling_strike_rate"
    ]].head(20)

    print(result.to_string(index=False))
other_t20 = competition_bowling[
    competition_bowling["competition_group"] == "Other T20"
].copy()

print("Total bowler profiles:", len(other_t20))

print("\nTop 20 by matches:")
print(
    other_t20.sort_values("matches", ascending=False)[
        ["bowler_name", "matches", "legal_balls", "wickets", "economy"]
    ].head(20).to_string(index=False)
)

print("\nTop 20 by legal balls:")
print(
    other_t20.sort_values("legal_balls", ascending=False)[
        ["bowler_name", "matches", "legal_balls", "wickets", "economy"]
    ].head(20).to_string(index=False)
)
print("Profiles with at least 10 matches:",
      (other_t20["matches"] >= 10).sum())

print("Profiles with at least 300 legal balls:",
      (other_t20["legal_balls"] >= 300).sum())

print("Profiles passing both:",
      (
          (other_t20["matches"] >= 10) &
          (other_t20["legal_balls"] >= 300)
      ).sum())
# Competition-specific sample requirements
minimum_samples = {
    "IPL": {"matches": 15, "legal_balls": 300},
    "T20I": {"matches": 15, "legal_balls": 300},
    "Other T20": {"matches": 4, "legal_balls": 72}
}

qualified_profiles = []

for competition, thresholds in minimum_samples.items():

    temp = competition_bowling[
        (competition_bowling["competition_group"] == competition) &
        (competition_bowling["matches"] >= thresholds["matches"]) &
        (competition_bowling["legal_balls"] >= thresholds["legal_balls"])
    ].copy()

    qualified_profiles.append(temp)

qualified_bowling = pd.concat(
    qualified_profiles,
    ignore_index=True
)

# Display top 20 for each competition
for competition in ["IPL", "T20I", "Other T20"]:

    print(f"\n========== {competition} ==========")

    result = qualified_bowling[
        qualified_bowling["competition_group"] == competition
    ].sort_values("wickets", ascending=False).head(20)

    print(
        result[[
            "bowler_name", "matches", "legal_balls",
            "runs_conceded", "wickets", "economy",
            "bowling_average", "bowling_strike_rate"
        ]].to_string(index=False)
    )
# Create one record per bowler per match innings
bowling_spells = bowling_comp.groupby(
    [
        "bowler_id",
        "bowler_name",
        "competition_group",
        "match_id",
        "innings"
    ]
).agg(
    spell_balls=("legal_ball", "sum"),
    spell_runs=("bowler_runs", "sum"),
    spell_wickets=("bowler_wicket", "sum")
).reset_index()

# Economy for each individual spell
bowling_spells["spell_economy"] = (
    bowling_spells["spell_runs"] /
    (bowling_spells["spell_balls"] / 6)
).replace([np.inf, -np.inf], np.nan)

print(bowling_spells.head(10))
bowling_consistency = bowling_spells.groupby(
    ["bowler_id", "bowler_name", "competition_group"]
).agg(
    spells=("match_id", "count"),

    average_wickets=("spell_wickets", "mean"),
    median_wickets=("spell_wickets", "median"),
    wicket_variation=("spell_wickets", "std"),

    wicketless_spells=(
        "spell_wickets",
        lambda x: (x == 0).sum()
    ),

    two_plus_wicket_spells=(
        "spell_wickets",
        lambda x: (x >= 2).sum()
    ),

    average_spell_economy=("spell_economy", "mean"),
    median_spell_economy=("spell_economy", "median"),
    economy_variation=("spell_economy", "std")

).reset_index()

# Convert counts into percentages
bowling_consistency["wicketless_spell_rate"] = (
    bowling_consistency["wicketless_spells"] /
    bowling_consistency["spells"] * 100
)

bowling_consistency["two_plus_wicket_rate"] = (
    bowling_consistency["two_plus_wicket_spells"] /
    bowling_consistency["spells"] * 100
)

print(bowling_consistency.head(10))
for competition in ["IPL", "T20I", "Other T20"]:

    print(f"\n========== {competition} BOWLING CONSISTENCY ==========")

    result = bowling_consistency[
        bowling_consistency["competition_group"] == competition
    ].sort_values(
        "two_plus_wicket_rate",
        ascending=False
    ).head(15)

    print(
        result[[
            "bowler_name",
            "spells",
            "average_wickets",
            "wicketless_spell_rate",
            "two_plus_wicket_rate",
            "average_spell_economy",
            "economy_variation"
        ]].to_string(index=False)
    )
# Get only players who passed our competition-specific
# minimum sample requirements
qualified_keys = qualified_bowling[
    ["bowler_id", "competition_group"]
].drop_duplicates()

# Keep consistency data for qualified players only
qualified_consistency = bowling_consistency.merge(
    qualified_keys,
    on=["bowler_id", "competition_group"],
    how="inner"
)

# Display top performers by competition
for competition in ["IPL", "T20I", "Other T20"]:

    print(f"\n========== {competition} ==========")

    result = qualified_consistency[
        qualified_consistency["competition_group"] == competition
    ].sort_values(
        "two_plus_wicket_rate",
        ascending=False
    ).head(15)

    print(
        result[[
            "bowler_name",
            "spells",
            "average_wickets",
            "wicketless_spell_rate",
            "two_plus_wicket_rate",
            "average_spell_economy",
            "economy_variation"
        ]].to_string(index=False)
    )
print("Minimum overid:", bowling_comp["overid"].min())
print("Maximum overid:", bowling_comp["overid"].max())

print(
    sorted(bowling_comp["overid"].dropna().unique())
)
# Make a copy of our bowling dataset
phase_data = bowling_comp.copy()

# Classify each delivery by over
phase_data["phase"] = np.select(
    [
        phase_data["overid"].between(1, 6),
        phase_data["overid"].between(7, 16),
        phase_data["overid"].between(17, 20)
    ],
    [
        "Powerplay",
        "Middle",
        "Death"
    ],
    default="Unknown"
)

# Check the classification
print(phase_data["phase"].value_counts())
phase_bowling = phase_data.groupby(
    [
        "bowler_id",
        "bowler_name",
        "competition_group",
        "phase"
    ]
).agg(
    matches=("match_id", "nunique"),
    innings=("innings", "count"),
    legal_balls=("legal_ball", "sum"),
    runs_conceded=("bowler_runs", "sum"),
    wickets=("bowler_wicket", "sum")
).reset_index()

# Calculate phase-specific economy
phase_bowling["economy"] = (
    phase_bowling["runs_conceded"] /
    (phase_bowling["legal_balls"] / 6)
).replace([np.inf, -np.inf], np.nan)

# Calculate bowling average
phase_bowling["bowling_average"] = (
    phase_bowling["runs_conceded"] /
    phase_bowling["wickets"].replace(0, np.nan)
)

# Calculate bowling strike rate
phase_bowling["bowling_strike_rate"] = (
    phase_bowling["legal_balls"] /
    phase_bowling["wickets"].replace(0, np.nan)
)
for competition in ["IPL", "T20I", "Other T20"]:

    for phase in ["Powerplay", "Middle", "Death"]:

        print(f"\n========== {competition} | {phase} ==========")

        result = phase_bowling[
            (phase_bowling["competition_group"] == competition) &
            (phase_bowling["phase"] == phase)
        ].sort_values(
            "wickets",
            ascending=False
        ).head(15)

        print(
            result[[
                "bowler_name",
                "matches",
                "legal_balls",
                "wickets",
                "economy",
                "bowling_average",
                "bowling_strike_rate"
            ]].to_string(index=False)
        )
# Create a copy
qualified_phase = phase_bowling.copy()

# Competition-specific phase sample thresholds
phase_thresholds = {
    "IPL": {"matches": 10, "legal_balls": 60},
    "T20I": {"matches": 10, "legal_balls": 60},
    "Other T20": {"matches": 3, "legal_balls": 18}
}

qualified_phase_list = []

for competition, threshold in phase_thresholds.items():

    temp = qualified_phase[
        (qualified_phase["competition_group"] == competition) &
        (qualified_phase["matches"] >= threshold["matches"]) &
        (qualified_phase["legal_balls"] >= threshold["legal_balls"])
    ].copy()

    qualified_phase_list.append(temp)

qualified_phase = pd.concat(
    qualified_phase_list,
    ignore_index=True
)

# Calculate wickets per 24 legal balls
qualified_phase["wickets_per_24_balls"] = (
    qualified_phase["wickets"] /
    qualified_phase["legal_balls"].replace(0, np.nan)
) * 24

# Display rankings
for competition in ["IPL", "T20I", "Other T20"]:

    for phase in ["Powerplay", "Middle", "Death"]:

        print(f"\n========== {competition} | {phase} ==========")

        result = qualified_phase[
            (qualified_phase["competition_group"] == competition) &
            (qualified_phase["phase"] == phase)
        ].sort_values(
            "wickets_per_24_balls",
            ascending=False
        ).head(10)

        print(
            result[[
                "bowler_name",
                "matches",
                "legal_balls",
                "wickets",
                "wickets_per_24_balls",
                "economy",
                "bowling_average"
            ]].to_string(index=False)
        )
print(
    phase_data[[
        "match_id",
        "innings",
        "overid",
        "innings_ball_num",
        "batting_team_id",
        "bowling_team_id",
        "runs",
        "is_wicket",
        "dismissal_type"
    ]].head(15).to_string(index=False)
)
print(
    matches[[
        "match_id",
        "result",
        "win_team_id",
        "first_inn_revised_overs",
        "second_inn_revised_overs",
        "revised_target"
    ]].head(10).to_string(index=False)
)
# Check the values and ranges of revised innings lengths
print("First innings revised overs:")
print(matches["first_inn_revised_overs"].describe())

print("\nSecond innings revised overs:")
print(matches["second_inn_revised_overs"].describe())

print("\nDistinct first innings revised values:")
print(sorted(matches["first_inn_revised_overs"].dropna().unique()))

print("\nDistinct second innings revised values:")
print(sorted(matches["second_inn_revised_overs"].dropna().unique()))