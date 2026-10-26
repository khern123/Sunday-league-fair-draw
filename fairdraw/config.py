"""Central configuration for Sunday League Fair Draw."""

# Number of teams to create; supported range is 2 through 4.
NUM_TEAMS = 2
# Display names available for the supported team counts.
TEAM_NAMES = ["Team A", "Team B", "Team C", "Team D"]
# Smallest allowed number of players on any team.
MIN_PLAYERS_PER_TEAM = 3
# Weekday used to calculate the next matchday; Monday is 0 and Sunday is 6.
LEAGUE_WEEKDAY = 6

# Draw-engine version recorded in receipts so results remain reproducible.
ENGINE_VERSION = "1.0"
# Number of seeded random splits scored for each draw.
CANDIDATES = 3000
# Number of highest-scoring candidate splits retained before seed selection.
TOP_POOL = 10
# Share of attendees treated as top players, rounded up by the draw engine.
TOP_FRACTION = 0.25
# Number of previous nights included when calculating repeat-pair penalties.
HISTORY_WINDOW = 8
# Weight applied to each one-night step of historical decay.
DECAY = 0.8

# Weight for differences in average team strength.
W_STRENGTH = 1.0
# Weight for spreading top players across teams.
W_TOP = 2.0
# Weight for penalizing recent repeat pairings.
W_REPEAT = 1.5
# Weight for spreading goalkeepers across teams.
W_KEEPER = 3.0

# Maximum chat messages accepted in one processing run.
MAX_MESSAGES_PER_RUN = 300
# Maximum characters accepted from one chat message.
MAX_CHARS_PER_MESSAGE = 500
# Maximum total chat characters accepted in one processing run.
MAX_TOTAL_CHARS = 30000
# Maximum number of LLM calls permitted during one run.
MAX_LLM_CALLS_PER_RUN = 8
# Maximum parser response tokens allowed per parser call.
MAX_OUTPUT_TOKENS_PARSER = 800
# Maximum announcement response tokens allowed per announcement call.
MAX_OUTPUT_TOKENS_ANNOUNCE = 500
# Maximum LLM calls allowed for one user session before AI actions are disabled.
SESSION_CALL_BUDGET = 20
# Maximum LLM calls allowed in one day before AI actions are disabled.
DAILY_CALL_BUDGET = 100

# Fill from course materials. Do not guess.
input_per_million = None
# Fill from course materials. Do not guess.
cached_input_per_million = None
# Fill from course materials. Do not guess.
output_per_million = None
