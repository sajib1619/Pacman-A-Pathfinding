"""Predicts real future ghost positions from their direction tables, and
turns those predictions into time-indexed "reservations" the planner can
check moves against (ghosts as moving walls).
"""

from collections import deque

from . import config
from .grid import neighbors, snap_to_grid

SAFE_MARGIN = config.SAFE_MARGIN
GHOST_BUFFER_TICKS = config.GHOST_BUFFER_TICKS
GHOST_WALL_MARGIN = config.GHOST_WALL_MARGIN


def ghost_direction_meta(ghost, turn, steps, directions, name, last_index):
    return {
        "ghost": ghost,
        "turn": turn,
        "steps": steps,
        "directions": directions,
        "name": name,
        "last_index": last_index,
    }


def advance_ghost_meta(meta):
    """Pure version of Ghost.changespeed() for forecasting future table moves."""
    directions = meta["directions"]
    turn = meta["turn"]
    steps = meta["steps"]
    last_index = meta["last_index"]
    name = meta["name"]
    try:
        limit = directions[turn][2]
        if steps < limit:
            dx, dy = directions[turn][0], directions[turn][1]
            steps += 1
        else:
            if turn < last_index:
                turn += 1
            elif name == "clyde":
                turn = 2
            else:
                turn = 0
            dx, dy = directions[turn][0], directions[turn][1]
            steps = 0
        return turn, steps, dx, dy
    except IndexError:
        return 0, 0, 0, 0


def forecast_ghost_timelines(ghost_meta, walkable, ticks):
    """Return each ghost's predicted grid cell at t=0..ticks.

    This matches the game's actual deterministic direction-table movement, so
    Pacman plans against the ghosts that are really coming, not a guessed chase.
    """
    timelines = []
    for meta in ghost_meta:
        g = meta["ghost"]
        x, y = g.rect.left, g.rect.top
        turn, steps = meta["turn"], meta["steps"]
        local = dict(meta)
        cells = [snap_to_grid(x, y)]
        for _ in range(ticks):
            # v6: match the real game loop, which calls changespeed twice per
            # frame and applies the SECOND call's dx/dy. Advancing only once
            # made the forecast lag ghost turns by 2x, so Pacman walked into
            # ghosts that had actually already turned toward him.
            local["turn"] = turn
            local["steps"] = steps
            turn, steps, _dx1, _dy1 = advance_ghost_meta(local)
            local["turn"] = turn
            local["steps"] = steps
            turn, steps, dx, dy = advance_ghost_meta(local)
            x += dx
            y += dy
            cell = snap_to_grid(x, y)
            if cell not in walkable and cells:
                cell = cells[-1]
            cells.append(cell)
        timelines.append(cells)
    return timelines


def ghost_cells_by_time(ghost_timelines):
    by_time = []
    max_len = max((len(t) for t in ghost_timelines), default=0)
    for t in range(max_len):
        by_time.append({line[min(t, len(line) - 1)] for line in ghost_timelines if line})
    return by_time


def _time_index(seq, t):
    if not seq:
        return 0
    return max(0, min(t, len(seq) - 1))


def build_ghost_reservations(ghost_timelines, walkable, threat, horizon):
    """Build time-indexed ghost obstacles for the safety planner.

    exact[t] contains cells occupied by ghosts at tick t. buffered[t] adds a
    short one-cell no-go halo for MED/HIGH threat. edges[t] contains ghost
    movements from tick t-1 to t, so Pacman can reject swap-through collisions.
    """
    exact = []
    buffered = []
    edges = [set() for _ in range(horizon + 1)]

    for t in range(horizon + 1):
        cells = set()
        for line in ghost_timelines:
            if not line:
                continue
            cell = line[min(t, len(line) - 1)]
            if cell in walkable:
                cells.add(cell)
        exact.append(cells)

    for line in ghost_timelines:
        if not line:
            continue
        for t in range(1, horizon + 1):
            prev = line[min(t - 1, len(line) - 1)]
            cur = line[min(t, len(line) - 1)]
            if prev in walkable and cur in walkable:
                edges[t].add((prev, cur))

    buffer_until = GHOST_BUFFER_TICKS.get(threat, 0)
    for t, cells in enumerate(exact):
        blocked = set(cells)
        if t <= buffer_until:
            for cell in cells:
                blocked.update(neighbors(cell, walkable))
        buffered.append(blocked)

    return {"exact": exact, "buffered": buffered, "edges": edges, "horizon": horizon}


def ghost_margin_after(cell, time_at_cell, reservations):
    """Ticks until a predicted ghost occupies cell, counting from time_at_cell."""
    exact = reservations["exact"]
    for t in range(time_at_cell, len(exact)):
        if cell in exact[t]:
            return t - time_at_cell
    return 999


def transition_blocked_by_ghost_wall(src, dst, arrival_time, reservations, walkable,
                                     use_buffer=True, margin=SAFE_MARGIN):
    """Return True if Pacman cannot safely move src -> dst by arrival_time."""
    if dst not in walkable:
        return True

    exact = reservations["exact"]
    table = reservations["buffered"] if use_buffer else exact
    arrival_idx = _time_index(table, arrival_time)
    depart_idx = _time_index(exact, arrival_time - 1)

    # Do not step into a cell that is occupied now, occupied on arrival, or in
    # the short threat buffer.  Blocking the departure-time occupant is the
    # important "ghost as wall" rule that prevents chasing a ghost's back.
    if dst in exact[depart_idx]:
        return True
    if dst in table[arrival_idx]:
        return True

    # Reject edge swaps: ghost moves dst -> src while Pacman moves src -> dst.
    edge_idx = _time_index(reservations["edges"], arrival_time)
    if (dst, src) in reservations["edges"][edge_idx]:
        return True

    # Require a little time cushion after arrival, without permanently banning
    # cells just because a ghost visited them much earlier in the forecast.
    for extra in range(1, margin + 1):
        future_idx = _time_index(exact, arrival_time + extra)
        if dst in exact[future_idx]:
            return True

    return False


def time_safe_reachable_count(start, start_time, walkable, reservations,
                              limit=40, threat="MED", use_buffer=True):
    """Count cells reachable through time while treating ghosts as obstacles."""
    if start not in walkable:
        return 0
    margin = GHOST_WALL_MARGIN.get(threat, SAFE_MARGIN)
    horizon = reservations["horizon"]
    if transition_blocked_by_ghost_wall(start, start, start_time, reservations,
                                        walkable, use_buffer=use_buffer, margin=margin):
        return 0

    max_depth = min(limit, max(0, horizon - start_time))
    q = deque([(start, start_time, 0)])
    seen_states = {(start, start_time)}
    seen_cells = {start}

    while q:
        cell, t, depth = q.popleft()
        if depth >= max_depth:
            continue
        arrival = t + 1
        for nb in neighbors(cell, walkable) + [cell]:
            if transition_blocked_by_ghost_wall(cell, nb, arrival, reservations,
                                                walkable, use_buffer=use_buffer,
                                                margin=margin):
                continue
            state = (nb, arrival)
            if state in seen_states:
                continue
            seen_states.add(state)
            seen_cells.add(nb)
            q.append((nb, arrival, depth + 1))

    return len(seen_cells)


def survival_horizon(start, start_time, walkable, reservations, max_steps, threat,
                     use_buffer=True):
    """How many future ticks Pacman can keep at least one legal path alive."""
    margin = GHOST_WALL_MARGIN.get(threat, SAFE_MARGIN)
    if start not in walkable:
        return 0
    if transition_blocked_by_ghost_wall(start, start, start_time, reservations,
                                        walkable, use_buffer=use_buffer, margin=margin):
        return 0

    alive = {start}
    horizon = min(max_steps, max(0, reservations["horizon"] - start_time))
    survived = 0
    for step in range(1, horizon + 1):
        arrival = start_time + step
        next_alive = set()
        for cell in alive:
            for nb in neighbors(cell, walkable) + [cell]:
                if transition_blocked_by_ghost_wall(cell, nb, arrival,
                                                    reservations, walkable,
                                                    use_buffer=use_buffer,
                                                    margin=margin):
                    continue
                next_alive.add(nb)
        if not next_alive:
            break
        alive = next_alive
        survived = step
    return survived


def forecast_sources(ghost_timelines):
    cells = set()
    for line in ghost_timelines:
        cells.update(line)
    return [c for c in cells if c is not None]


def ghost_earliest_arrivals(ghost_timelines, walkable, horizon):
    arrivals = {cell: 999 for cell in walkable}
    for line in ghost_timelines:
        for t, cell in enumerate(line[:horizon + 1]):
            if cell in walkable and t < arrivals[cell]:
                arrivals[cell] = t
    return arrivals
