"""Builds the soft "fear" cost field A* plans against, plus a hard-block set
for cells that are imminently unsafe.
"""

from . import config
from .grid import bfs_distances, neighbors
from .graph import iter_pockets
from .ghost_forecast import forecast_sources

DANGER_RADIUS  = config.DANGER_RADIUS
IMMINENT_BLOCK = config.IMMINENT_BLOCK
FEAR_WEIGHT    = config.FEAR_WEIGHT
POCKET_LIMIT   = config.POCKET_LIMIT
SAFE_MARGIN    = config.SAFE_MARGIN
CHOKE_PENALTY  = config.CHOKE_PENALTY
TRAP_PENALTY   = config.TRAP_PENALTY


def build_fear_field(ghost_timelines, pac_cell, walkable, art_points, pockets):
    fear = {c: 0.0 for c in walkable}
    hard_block = set()

    ghost_cells = forecast_sources(ghost_timelines)

    # Per-ghost proximity fear.
    for gc in ghost_cells:
        dist = bfs_distances([gc], walkable, DANGER_RADIUS)
        for cell, d in dist.items():
            if d <= IMMINENT_BLOCK:
                hard_block.add(cell)
            penalty = FEAR_WEIGHT / (1.0 + (d ** 2) * 0.6)
            fear[cell] += penalty

    # Choke / pocket penalty: if a ghost can reach a choke point at least
    # as quickly (within SAFE_MARGIN) as Pacman, every cell in the pocket
    # behind that choke gets a heavy penalty. This makes entire dead-end
    # regions expensive BEFORE Pacman commits.
    if pac_cell in walkable and ghost_cells:
        pac_dist = bfs_distances([pac_cell], walkable, 40)
        ghost_dist = bfs_distances(ghost_cells, walkable, 40)
        for ap, pocket in iter_pockets(pockets):
            if len(pocket) > POCKET_LIMIT * 4:
                continue  # too big to be a real trap
            pd = pac_dist.get(ap)
            gd = ghost_dist.get(ap)
            if pd is None or gd is None:
                continue
            # If Pacman is already inside the pocket, he needs the exit to stay
            # attractive; penalize deeper cells but not the choke itself.
            if gd <= pd + SAFE_MARGIN:
                weight = CHOKE_PENALTY
                if len(pocket) <= POCKET_LIMIT:
                    weight *= 1.5
                for cell in pocket:
                    if pac_cell in pocket and cell == ap:
                        continue
                    fear[cell] += weight
                if pac_cell not in pocket:
                    fear[ap] += weight * 0.5

    # Trap-degree penalty (also fires for cells with 0 ghost fear but sitting
    # in a small pocket -- keeps Pacman from wandering into isolated corners).
    for cell in walkable:
        degree = len(neighbors(cell, walkable))
        near_ghost = fear[cell] > 0
        if degree <= 1 and near_ghost:
            fear[cell] += TRAP_PENALTY * 2
        elif degree == 2 and near_ghost:
            fear[cell] += TRAP_PENALTY * 0.5

    return fear, hard_block
