"""
Grid-level primitives shared by every other AI module.

Everything here treats the maze as a lattice of STEP-sized cells snapped to
(ORIGIN_X, ORIGIN_Y), independent of any pathfinding strategy.
"""

from collections import deque

import pygame

from . import config

STEP = config.STEP
ORIGIN_X = config.ORIGIN_X
ORIGIN_Y = config.ORIGIN_Y
SCREEN_LIMIT = config.SCREEN_SIZE[0]

Cell = tuple[int, int]

CARDINAL_DIRECTIONS = (
    (STEP, 0),
    (-STEP, 0),
    (0, STEP),
    (0, -STEP),
)


def snap_to_grid(x: int, y: int) -> Cell:
    """Snap a pixel position to the nearest grid cell."""
    grid_x = ORIGIN_X + round((x - ORIGIN_X) / STEP) * STEP
    grid_y = ORIGIN_Y + round((y - ORIGIN_Y) / STEP) * STEP
    return (grid_x, grid_y)


def build_walkable_cells(
    start: Cell,
    wall_list: pygame.sprite.Group,
    gate: pygame.sprite.Group | None,
    pac_rect: pygame.Rect,
) -> set[Cell]:
    """Return every reachable walkable grid cell."""
    probe = _create_probe(pac_rect)
    walkable = _initialize_walkable(start, probe, wall_list, gate)
    _expand_walkable(walkable, probe, wall_list, gate)
    return walkable


def neighbors(cell: Cell, walkable: set[Cell]) -> list[Cell]:
    """Return walkable neighboring cells."""
    result = []

    for dx, dy in CARDINAL_DIRECTIONS:
        neighbor = (cell[0] + dx, cell[1] + dy)

        if neighbor in walkable:
            result.append(neighbor)

    return result


def bfs_distances(
    sources: list[Cell],
    walkable: set[Cell],
    max_dist: int,
    blocked: set[Cell] | None = None,
) -> dict[Cell, int]:
    """Compute BFS distance from every source."""
    blocked = blocked or set()
    distances, queue = _initialize_bfs(sources, walkable, blocked)
    _expand_bfs(queue, distances, walkable, blocked, max_dist)
    return distances


# --------------------------------------------------
# Private Helpers
# --------------------------------------------------

def _create_probe(pac_rect: pygame.Rect) -> pygame.sprite.Sprite:
    """Create a collision probe matching Pacman's size."""
    probe = pygame.sprite.Sprite()
    probe.image = pygame.Surface((pac_rect.width, pac_rect.height))
    probe.rect = probe.image.get_rect()
    return probe


def _initialize_walkable(
    start: Cell,
    probe: pygame.sprite.Sprite,
    walls: pygame.sprite.Group,
    gate: pygame.sprite.Group | None,
) -> set[Cell]:
    """Create the initial walkable set."""
    walkable = set()

    if _is_walkable(start, probe, walls, gate) == False:
        return walkable

    walkable.add(start)
    return walkable


def _expand_walkable(
    walkable: set[Cell],
    probe: pygame.sprite.Sprite,
    walls: pygame.sprite.Group,
    gate: pygame.sprite.Group | None,
) -> None:
    """Flood-fill all reachable cells."""
    queue = deque(walkable)

    while queue:
        cell = queue.popleft()
        _visit_neighbors(cell, queue, walkable, probe, walls, gate)


def _visit_neighbors(
    cell: Cell,
    queue: deque,
    walkable: set[Cell],
    probe: pygame.sprite.Sprite,
    walls: pygame.sprite.Group,
    gate: pygame.sprite.Group | None,
) -> None:
    """Visit every neighboring cell."""
    for dx, dy in CARDINAL_DIRECTIONS:
        neighbor = (cell[0] + dx, cell[1] + dy)

        if _can_visit(neighbor, walkable, probe, walls, gate):
            walkable.add(neighbor)
            queue.append(neighbor)


def _can_visit(
    cell: Cell,
    walkable: set[Cell],
    probe: pygame.sprite.Sprite,
    walls: pygame.sprite.Group,
    gate: pygame.sprite.Group | None,
) -> bool:
    """Return whether a cell can be explored."""
    is_new = cell not in walkable
    is_inside = _is_inside_grid(cell)
    is_walkable = _is_walkable(cell, probe, walls, gate)
    return is_new and is_inside and is_walkable


def _is_inside_grid(cell: Cell) -> bool:
    """Return True if the cell lies inside the maze."""
    x, y = cell
    return 0 <= x <= SCREEN_LIMIT and 0 <= y <= SCREEN_LIMIT


def _is_walkable(
    cell: Cell,
    probe: pygame.sprite.Sprite,
    walls: pygame.sprite.Group,
    gate: pygame.sprite.Group | None,
) -> bool:
    """Return True if a cell is free of obstacles."""
    probe.rect.left, probe.rect.top = cell

    hits_wall = pygame.sprite.spritecollide(probe, walls, False)

    if hits_wall:
        return False

    has_gate = gate is not None

    if has_gate == False:
        return True

    hits_gate = pygame.sprite.spritecollide(probe, gate, False)
    return len(hits_gate) == 0


def _initialize_bfs(
    sources: list[Cell],
    walkable: set[Cell],
    blocked: set[Cell],
) -> tuple[dict[Cell, int], deque]:
    """Initialize BFS frontier."""
    distances = {}
    queue = deque()

    for cell in sources:
        is_valid = cell in walkable
        is_blocked = cell in blocked
        is_new = cell not in distances

        if is_valid and is_new and is_blocked == False:
            distances[cell] = 0
            queue.append(cell)

    return distances, queue


def _expand_bfs(
    queue: deque,
    distances: dict[Cell, int],
    walkable: set[Cell],
    blocked: set[Cell],
    max_dist: int,
) -> None:
    """Expand the BFS frontier."""
    while queue:
        cell = queue.popleft()
        _process_bfs_node(cell, queue, distances, walkable, blocked, max_dist)


def _process_bfs_node(
    cell: Cell,
    queue: deque,
    distances: dict[Cell, int],
    walkable: set[Cell],
    blocked: set[Cell],
    max_dist: int,
) -> None:
    """Process one BFS node."""
    distance = distances[cell]

    if distance >= max_dist:
        return

    for neighbor in neighbors(cell, walkable):
        _enqueue_neighbor(neighbor, queue, distances, blocked, distance)


def _enqueue_neighbor(
    neighbor: Cell,
    queue: deque,
    distances: dict[Cell, int],
    blocked: set[Cell],
    distance: int,
) -> None:
    """Add a neighbor to the BFS frontier."""
    is_blocked = neighbor in blocked
    is_seen = neighbor in distances

    if is_blocked or is_seen:
        return

    distances[neighbor] = distance + 1
    queue.append(neighbor)