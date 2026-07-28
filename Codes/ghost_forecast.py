from collections import deque
from dataclasses import dataclass

import pygame

from . import config
from .grid import neighbors, snap_to_grid
import logging

LOGGER = logging.getLogger(__name__)


SAFE_MARGIN = config.SAFE_MARGIN
GHOST_BUFFER_TICKS = config.GHOST_BUFFER_TICKS
GHOST_WALL_MARGIN = config.GHOST_WALL_MARGIN

Cell = tuple[int, int]
Direction = tuple[int, int, int]
GhostTimeline = list[Cell]

@dataclass
class GhostMeta:
    """Stores the current scripted movement state of a ghost."""

    ghost: pygame.sprite.Sprite
    turn: int
    steps: int
    directions: list[Direction]
    name: str
    last_index: int

def ghost_direction_meta(
    ghost: pygame.sprite.Sprite,
    turn: int,
    steps: int,
    directions: list[Direction],
    name: str,
    last_index: int,
) -> GhostMeta:
    """Create movement metadata for a ghost."""
    return GhostMeta(
        ghost=ghost,
        turn=turn,
        steps=steps,
        directions=directions,
        name=name,
        last_index=last_index,
    )


def advance_ghost_meta(
    meta: GhostMeta,
) -> tuple[int, int, int, int]:
    """Advance one step through a ghost's movement table."""
    try:
        return _advance_meta(meta)
    except IndexError:
        LOGGER.exception("Invalid ghost direction table.")
        return (0, 0, 0, 0)

def _advance_meta(
    meta: GhostMeta,
) -> tuple[int, int, int, int]:
    """Advance the current movement state."""
    limit = meta.directions[meta.turn][2]

    if meta.steps < limit:
        return _continue_direction(meta)

    return _change_direction(meta)

def _continue_direction(
    meta: GhostMeta,
) -> tuple[int, int, int, int]:
    """Continue moving in the current direction."""
    dx, dy, _ = meta.directions[meta.turn]
    return (meta.turn, meta.steps + 1, dx, dy)

def _change_direction(
    meta: GhostMeta,
) -> tuple[int, int, int, int]:
    """Switch to the next scripted direction."""
    turn = _next_turn(meta)
    dx, dy, _ = meta.directions[turn]
    return (turn, 0, dx, dy)

def _next_turn(meta: GhostMeta) -> int:
    """Return the next direction index."""
    is_last_direction = meta.turn >= meta.last_index

    if not is_last_direction:
        return meta.turn + 1

    is_clyde = meta.name == "clyde"

    if is_clyde:
        return 2

    return 0

