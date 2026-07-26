"""Colors, layout constants, and every tunable knob for the A* ghost-aware AI.

Nothing in here has behavior -- it's the single place to look when you want
to retune how brave/cautious Pacman is, or change screen layout.
"""

# ---------- Colors ----------
black  = (0, 0, 0)
white  = (255, 255, 255)
blue   = (0, 0, 255)
green  = (0, 255, 0)
red    = (255, 0, 0)
purple = (255, 0, 255)
yellow = (255, 255, 0)
orange = (255, 165, 0)

# ---------- Screen layout ----------
SCREEN_SIZE = [606, 606]

# Sprite start positions, derived from the original maze layout.
w   = 303 - 16
p_h = (7 * 60) + 19
m_h = (4 * 60) + 19
b_h = (3 * 60) + 19
i_w = 303 - 16 - 32
c_w = 303 + (32 - 16)

# ---------- Lattice / pathfinding ----------
STEP = 30
ORIGIN_X = w
ORIGIN_Y = p_h

# --- Tunables ---
DANGER_RADIUS   = 7        # per-ghost fear BFS radius (in grid moves)
LOOKAHEAD_TICKS = 10       # real ghost forecast horizon
FEAR_WEIGHT     = 280.0    # base fear at distance 1
TRAP_PENALTY    = 80.0     # extra cost for low-degree cells near ghosts
IMMINENT_BLOCK  = 1        # BFS distance <= this: hard-blocked (unless no option)
CHOKE_PENALTY   = 140.0    # added to fear of a pocket cell when its guard is threatened
POCKET_LIMIT    = 8        # pockets <= this many cells are treated as traps
SAFE_MARGIN     = 2        # Pacman must beat ghosts to a choke by this many steps
ROLLOUT_DEPTH   = 9        # steps of forward simulation for move scoring
MIN_FREE_CELLS  = 8        # planner needs at least this many safely-reachable cells
TRAP_EXIT_MARGIN = 3       # urgency threshold for leaving a pocket / corridor
PELLET_WEIGHT   = 8.0      # pellet progress is useful, but survival dominates

# --- v5 threat-adaptive scoring ---
THREAT_NEAR = SAFE_MARGIN + 2   # <= this many ticks to a ghost => HIGH threat
THREAT_MED  = 6                 # <= this => MED threat, else LOW
RECENT_LEN  = 6                 # how many recent cells to remember for anti-oscillation

# Weight profile per threat level. Keys: safe_w, margin_w, pellet_w,
# eat_now, eat_rollout, fear_mult, progress_w, revisit_penalty.
THREAT_PROFILE = {
    "LOW":  dict(safe_w=10.0,  margin_w=2.0,  pellet_w=40.0, eat_now=120.0,
                 eat_rollout=25.0, fear_mult=0.3, progress_w=25.0, revisit_penalty=12.0),
    "MED":  dict(safe_w=40.0,  margin_w=8.0,  pellet_w=20.0, eat_now=80.0,
                 eat_rollout=15.0, fear_mult=1.0, progress_w=10.0, revisit_penalty=4.0),
    "HIGH": dict(safe_w=120.0, margin_w=18.0, pellet_w=8.0,  eat_now=35.0,
                 eat_rollout=5.0,  fear_mult=1.5, progress_w=3.0,  revisit_penalty=0.0),
}

# --- v7 dynamic ghost-wall safety ---
# Ghosts are treated as moving obstacles, not just scary cells.  The exact
# forecast cells are blocked at every tick, and MED/HIGH threat adds a short
# one-cell buffer so Pacman does not willingly trail a ghost into a reversal.
GHOST_BUFFER_TICKS = {"LOW": 0, "MED": 2, "HIGH": 4}
GHOST_WALL_MARGIN  = {"LOW": 1, "MED": SAFE_MARGIN, "HIGH": SAFE_MARGIN}
MIN_ALIVE_HORIZON_PROFILE = {"LOW": 3, "MED": 4, "HIGH": 5}

DIR_NAME = {
    (STEP, 0):  "RIGHT",
    (-STEP, 0): "LEFT",
    (0, STEP):  "DOWN",
    (0, -STEP): "UP",
    (0, 0):     "STAY",
}
