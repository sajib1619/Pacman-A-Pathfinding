# Pacman — A* Ghost-Aware AI

A self-playing Pacman built on the classic pygame base, with a full autonomous agent driving Pacman instead of the
keyboard. The agent doesn't just chase the nearest pellet — it forecasts
where each ghost is actually going, treats them as moving obstacles, and
refuses to wander into corridors a ghost can seal off behind it.

Watch it play, tweak the danger tolerance in one file, or read through the
planner to see how the decision-making works.

## How the AI thinks

Every tick, Pacman:

1. **Forecasts real ghost movement.** Each ghost follows a deterministic
   scripted direction table, so instead of guessing "ghosts chase greedily,"
   the AI simulates each ghost's table forward N ticks to know exactly
   where it will be.
2. **Builds a fear field.** Every reachable cell gets a danger score based
   on proximity to forecasted ghost positions, decaying with distance.
3. **Finds choke points and pockets.** A structural pass (articulation
   points) identifies dead-ends and corridors with a single exit. If a
   ghost can reach that exit before Pacman can, the entire pocket behind it
   is marked dangerous — Pacman won't enter a trap it can't see coming.
4. **Filters pellet goals.** Pellets sitting in a currently-unsafe pocket
   are dropped from the goal set, so Pacman doesn't detour into danger for
   a snack.
5. **Scores every legal move with a rollout.** For each candidate first
   step, the AI simulates several future ticks against the ghost forecast,
   scoring for survivability, escape routes, and pellet progress — with the
   weighting shifting from "greedy" to "paranoid" as a threat escalates
   from LOW → MED → HIGH.
6. **Falls back gracefully.** If every move looks bad, it picks the one
   that survives longest rather than freezing or picking arbitrarily.

The live fear field, unsafe tiles, and forecasted ghost paths are all drawn
on screen while it plays, so you can see the reasoning as it happens.

## Project structure

```
main.py                     # entry point — python main.py
pacman_ai/
    config.py                # colors, layout, and every AI tunable
    engine.py                 # pygame window / clock / fonts / music bootstrap
    sprites.py                  # Wall, Block, Player, Ghost sprite classes
    ghost_tables.py               # scripted direction tables for each ghost
    maze.py                         # wall + gate layout
    grid.py                          # grid snapping, walkable-cell flood fill, BFS
    graph.py                          # articulation points ("choke points") & pockets
    ghost_forecast.py                   # future ghost-position prediction
    fear_field.py                         # per-cell danger cost
    pathfinding.py                          # weighted A* + emergency fallback move
    planner.py                                # rollout scoring & final move selection
    game.py                                     # level setup + main loop
```

Dependencies flow one direction, so each piece can be read (or tested) on
its own:

```
config, ghost_tables → grid → graph, sprites → ghost_forecast, maze
   → fear_field, planner → pathfinding → game → main
```

## Getting started

### Requirements
- Python 3.9+
- [pygame](https://www.pygame.org/)

```bash
pip install pygame
```

### Assets

Place these next to `main.py` (included in this repo):

```
images/
  Trollman.png
  Blinky.png
  Pinky.png
  Inky.png
  Clyde.png
freesansbold.ttf
pacman.mp3        # optional — game runs fine without it
```

### Run it

```bash
python main.py
```

Press **ESC** at any time to quit. When the game ends, press **ENTER** to
restart or **ESC** to quit.

## Tuning the AI

Every knob that controls how cautious or aggressive Pacman plays lives in
`pacman_ai/config.py` — no other file should need to change:

| Constant | What it controls |
|---|---|
| `DANGER_RADIUS` | How far a ghost's presence is felt in the fear field |
| `FEAR_WEIGHT` | Base danger cost at distance 1 from a ghost |
| `LOOKAHEAD_TICKS` | How far ahead ghost movement is forecast |
| `CHOKE_PENALTY` | Extra cost for pockets a ghost could seal off |
| `SAFE_MARGIN` | How much of a lead Pacman needs over a ghost to use a choke point |
| `ROLLOUT_DEPTH` | How many ticks each candidate move is simulated forward |
| `THREAT_PROFILE` | Per-threat-level (LOW/MED/HIGH) scoring weights |

Turning `FEAR_WEIGHT` and `CHOKE_PENALTY` down makes Pacman noticeably
greedier and more willing to cut it close; turning them up makes it play
very conservatively.

## Credits

- Base game (maze, sprites, ghost movement tables): [hbokmann/Pacman](https://github.com/hbokmann/Pacman)
- A* ghost-aware AI, fear field, choke-point/pocket safety planner: this project

