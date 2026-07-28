"""
Builds the soft fear cost field used by A*.

Ghost proximity creates dynamic danger costs.
Choke points and pockets add strategic penalties.
"""


from . import config
from .grid import bfs_distances, neighbors
from .graph import iter_pockets
from .ghost_forecast import forecast_sources


DANGER_RADIUS = config.DANGER_RADIUS
IMMINENT_BLOCK = config.IMMINENT_BLOCK
FEAR_WEIGHT = config.FEAR_WEIGHT
POCKET_LIMIT = config.POCKET_LIMIT
SAFE_MARGIN = config.SAFE_MARGIN
CHOKE_PENALTY = config.CHOKE_PENALTY
TRAP_PENALTY = config.TRAP_PENALTY


Cell = tuple[int, int]
FearField = dict[Cell, float]
HardBlock = set[Cell]


def build_fear_field(
    ghost_timelines: list[list[Cell]],
    pac_cell: Cell,
    walkable: set[Cell],
    art_points: set[Cell],
    pockets: dict,
) -> tuple[FearField, HardBlock]:
    """Create fear values and dangerous cells."""

    fear = {cell: 0.0 for cell in walkable}
    hard_block = set()

    ghost_cells = forecast_sources(ghost_timelines)

    _build_ghost_fear(
        ghost_cells,
        walkable,
        fear,
        hard_block,
    )

    _apply_pocket_penalty(
        pac_cell,
        ghost_cells,
        walkable,
        fear,
        pockets,
    )

    _apply_trap_penalty(
        walkable,
        fear,
    )

    return fear, hard_block

def _build_ghost_fear(
    ghost_cells: list[Cell],
    walkable: set[Cell],
    fear: FearField,
    hard_block: HardBlock,
) -> None:
    """Apply fear caused by nearby ghosts."""

    for ghost_cell in ghost_cells:
        distances = bfs_distances(
            [ghost_cell],
            walkable,
            DANGER_RADIUS,
        )

        _apply_distance_fear(
            distances,
            fear,
            hard_block,
        )

def _apply_distance_fear(
    distances: dict[Cell, int],
    fear: FearField,
    hard_block: HardBlock,
) -> None:
    """Convert ghost distance into fear cost."""

    for cell, distance in distances.items():

        _add_hard_block(
            cell,
            distance,
            hard_block,
        )

        fear[cell] += (
            FEAR_WEIGHT
            / (1.0 + (distance ** 2) * 0.6)
        )


def _add_hard_block(
    cell: Cell,
    distance: int,
    hard_block: HardBlock,
) -> None:
    """Mark extremely dangerous cells."""

    is_imminent = distance <= IMMINENT_BLOCK

    if is_imminent:
        hard_block.add(cell)

def _apply_pocket_penalty(
    pac_cell: Cell,
    ghost_cells: list[Cell],
    walkable: set[Cell],
    fear: FearField,
    pockets: dict,
) -> None:
    """Increase danger for threatened pockets."""

    if pac_cell not in walkable:
        return

    if not ghost_cells:
        return

    pac_dist = bfs_distances(
        [pac_cell],
        walkable,
        40,
    )

    ghost_dist = bfs_distances(
        ghost_cells,
        walkable,
        40,
    )

    for choke, pocket in iter_pockets(pockets):
        _evaluate_pocket(
            choke,
            pocket,
            pac_cell,
            pac_dist,
            ghost_dist,
            fear,
        )

def _evaluate_pocket(
    choke: Cell,
    pocket: set[Cell],
    pac_cell: Cell,
    pac_dist: dict,
    ghost_dist: dict,
    fear: FearField,
) -> None:
    """Evaluate whether a pocket becomes dangerous."""

    if len(pocket) > POCKET_LIMIT * 4:
        return

    pac_time = pac_dist.get(choke)
    ghost_time = ghost_dist.get(choke)

    if pac_time is None or ghost_time is None:
        return

    is_threatened = ghost_time <= pac_time + SAFE_MARGIN

    if is_threatened:
        _increase_pocket_cost(
            choke,
            pocket,
            pac_cell,
            fear,
        )

def _increase_pocket_cost(
    choke: Cell,
    pocket: set[Cell],
    pac_cell: Cell,
    fear: FearField,
) -> None:
    """Apply danger cost to pocket cells."""

    weight = CHOKE_PENALTY

    if len(pocket) <= POCKET_LIMIT:
        weight *= 1.5

    for cell in pocket:

        is_inside_pocket = pac_cell in pocket
        is_choke = cell == choke

        if is_inside_pocket and is_choke:
            continue

        fear[cell] += weight

    if pac_cell not in pocket:
        fear[choke] += weight * 0.5

def _apply_trap_penalty(
    walkable: set[Cell],
    fear: FearField,
) -> None:
    """Penalize low-degree dangerous cells."""

    for cell in walkable:
        degree = len(
            neighbors(cell, walkable)
        )

        if fear[cell] <= 0:
            continue

        fear[cell] += _trap_cost(degree)

def _trap_cost(degree: int) -> float:
    """Return trap penalty based on cell connectivity."""

    if degree <= 1:
        return TRAP_PENALTY * 2

    if degree == 2:
        return TRAP_PENALTY * 0.5

    return 0.0

