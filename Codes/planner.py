"""Turns the fear field + ghost forecasts into a single chosen move.

score_candidate() simulates a short forward rollout for one candidate first
step (survival horizon, safe-reachable-cell count, pellet progress, pocket
escape urgency) and choose_safest_move() picks the best-scoring legal step.
"""

from collections import deque

from . import config
from .grid import neighbors, bfs_distances
from .graph import containing_pocket
from .ghost_forecast import (
    _time_index,
    build_ghost_reservations,
    ghost_cells_by_time,
    ghost_earliest_arrivals,
    ghost_margin_after,
    survival_horizon,
    time_safe_reachable_count,
    transition_blocked_by_ghost_wall,
)

SAFE_MARGIN = config.SAFE_MARGIN
TRAP_EXIT_MARGIN = config.TRAP_EXIT_MARGIN
THREAT_PROFILE = config.THREAT_PROFILE
GHOST_WALL_MARGIN = config.GHOST_WALL_MARGIN
MIN_ALIVE_HORIZON_PROFILE = config.MIN_ALIVE_HORIZON_PROFILE
ROLLOUT_DEPTH = config.ROLLOUT_DEPTH
MIN_FREE_CELLS = config.MIN_FREE_CELLS
THREAT_NEAR = config.THREAT_NEAR
THREAT_MED = config.THREAT_MED
LOOKAHEAD_TICKS = config.LOOKAHEAD_TICKS


def safe_reachable_count(start, walkable, ghost_arrival, time_offset=0, limit=40):
    if start not in walkable:
        return 0
    q = deque([(start, 0)])
    seen = {start}
    while q:
        cell, d = q.popleft()
        if d >= limit:
            continue
        for nb in neighbors(cell, walkable):
            if nb in seen:
                continue
            arrive = time_offset + d + 1
            if arrive + SAFE_MARGIN >= ghost_arrival.get(nb, 999):
                continue
            seen.add(nb)
            q.append((nb, d + 1))
    return len(seen)


def nearest_goal_distance(cell, goals, walkable, limit=80):
    if not goals:
        return 0
    dist = bfs_distances([cell], walkable, limit)
    best = min((dist[g] for g in goals if g in dist), default=limit)
    return best


def escape_status(cell, ghost_arrival, walkable, pockets):
    info = containing_pocket(cell, pockets)
    if info is None:
        return False, None, 999, 999
    ap, pocket = info
    pac_to_exit = bfs_distances([cell], walkable, 80).get(ap, 999)
    ghost_to_exit = ghost_arrival.get(ap, 999)
    urgent = ghost_to_exit <= pac_to_exit + TRAP_EXIT_MARGIN
    return urgent, ap, pac_to_exit, ghost_to_exit


def score_candidate(first, pac_cell, goals, walkable, fear, ghost_by_time,
                    ghost_arrival, pockets, threat="MED", recent_positions=None,
                    reservations=None):
    reserved_blocked = 0
    if first not in walkable:
        return (-1e12, "BLOCKED", 0, 0.0, 0, reserved_blocked)

    if reservations is None:
        reservations = build_ghost_reservations([], walkable, threat, LOOKAHEAD_TICKS)

    prof = THREAT_PROFILE[threat]
    recent_positions = recent_positions or ()
    wall_margin = GHOST_WALL_MARGIN.get(threat, SAFE_MARGIN)
    min_alive_horizon = MIN_ALIVE_HORIZON_PROFILE.get(threat, 4)

    # v7: hard-veto the first step if it treats a ghost cell as passable.  This
    # blocks Pacman from walking into a ghost's current cell, predicted arrival
    # cell, buffered danger cell, or swap-through edge.
    exact_t0 = reservations["exact"][_time_index(reservations["exact"], 0)]
    exact_t1 = reservations["exact"][_time_index(reservations["exact"], 1)]
    edges_t1 = reservations["edges"][_time_index(reservations["edges"], 1)]
    if first in exact_t0 or first in exact_t1 or (first, pac_cell) in edges_t1:
        return (-1e12, "GHOST-WALL", 0, 0.0, 0, 1)
    if transition_blocked_by_ghost_wall(pac_cell, first, 1, reservations,
                                        walkable, use_buffer=True,
                                        margin=wall_margin):
        # The exact ghost cells are clear, but the buffer/cushion says this is
        # still a bad idea.  Do not tie all such moves together: rank them by
        # how long they survive without the buffer, so an unavoidable emergency
        # still picks the least-certain capture instead of an arbitrary cell.
        loose_horizon = survival_horizon(first, 1, walkable, reservations,
                                         ROLLOUT_DEPTH, threat, use_buffer=False)
        loose_safe = time_safe_reachable_count(first, 1, walkable, reservations,
                                               18, threat, use_buffer=False)
        loose_margin = ghost_margin_after(first, 1, reservations)
        score = (-1e11 + loose_horizon * 1000000.0 + loose_safe * 10000.0
                 + loose_margin * 100.0 - fear.get(first, 0.0))
        return (score, f"GHOST-WALL/{threat}", loose_safe, 0.0,
                loose_horizon, 1)

    urgent, exit_cell, pac_exit, ghost_exit = escape_status(first, ghost_arrival, walkable, pockets)
    alive_horizon = survival_horizon(first, 1, walkable, reservations,
                                     ROLLOUT_DEPTH, threat)
    best_safe = time_safe_reachable_count(first, 1, walkable, reservations,
                                          24, threat)
    best_margin = ghost_margin_after(first, 1, reservations)
    pellet_bonus = 0.0

    eaten0 = frozenset([first]) if goals and first in goals else frozenset()
    alive_paths = [(first, 1, 0.0, eaten0)]
    eat_rollout = prof["eat_rollout"]

    for _ in range(ROLLOUT_DEPTH):
        next_paths = []
        for cell, current_time, reward, eaten in alive_paths:
            arrival_time = current_time + 1
            if arrival_time > reservations["horizon"]:
                continue
            options = neighbors(cell, walkable) + [cell]
            for nb in options:
                if transition_blocked_by_ghost_wall(cell, nb, arrival_time,
                                                    reservations, walkable,
                                                    use_buffer=True,
                                                    margin=wall_margin):
                    reserved_blocked += 1
                    continue

                arrival_margin = ghost_margin_after(nb, arrival_time, reservations)
                local_reward = reward
                local_reward += max(0, arrival_margin) * 1.5
                local_reward += time_safe_reachable_count(nb, arrival_time,
                                                          walkable, reservations,
                                                          18, threat) * 0.35
                local_reward -= fear.get(nb, 0.0) * 0.03

                new_eaten = eaten
                if goals and nb in goals and nb not in eaten:
                    local_reward += eat_rollout
                    new_eaten = frozenset(set(eaten) | {nb})

                if urgent and exit_cell is not None:
                    local_reward -= nearest_goal_distance(nb, {exit_cell}, walkable, 40) * 18.0

                next_paths.append((nb, arrival_time, local_reward, new_eaten))
                best_margin = max(best_margin, arrival_margin)

        if not next_paths:
            alive_paths = []
            break
        next_paths.sort(key=lambda item: item[2], reverse=True)
        alive_paths = next_paths[:18]
        best_safe = max(
            best_safe,
            max(time_safe_reachable_count(p[0], p[1], walkable, reservations, 24, threat)
                for p in alive_paths)
        )

    if goals:
        dist_first = nearest_goal_distance(first, goals, walkable, 80)
        pellet_bonus = -dist_first * prof["pellet_w"]
        if first in goals:
            pellet_bonus += prof["eat_now"]
        dist_pac = nearest_goal_distance(pac_cell, goals, walkable, 80)
        pellet_bonus += (dist_pac - dist_first) * prof["progress_w"]

    if not alive_paths:
        score = -5e10 + alive_horizon * 100000.0 + best_safe * 1000.0 - fear.get(first, 0.0)
        return (score, f"TRAPPED/{threat}", best_safe, pellet_bonus,
                alive_horizon, reserved_blocked)

    if alive_horizon < min_alive_horizon:
        # A move that leads to a short forced capture is worse than any move
        # with a durable path, but if every move is bad this still picks the
        # one that survives longest.
        score = (-1e9 + alive_horizon * 1000000.0 + best_safe * 10000.0
                 + pellet_bonus * 0.05 - fear.get(first, 0.0))
        return (score, f"TRAPPED/{threat}", best_safe, pellet_bonus,
                alive_horizon, reserved_blocked)

    mode_base = "ESCAPE" if urgent else (
        "AVOID-TRAP" if best_safe < MIN_FREE_CELLS else "HUNT"
    )
    mode = f"{mode_base}/{threat}"
    survival_score = 100000.0
    escape_score = best_safe * prof["safe_w"] + best_margin * prof["margin_w"]
    best_future = max(p[2] for p in alive_paths)
    score = (survival_score + escape_score + best_future + pellet_bonus
             - fear.get(first, 0.0) * prof["fear_mult"])

    if recent_positions and prof["revisit_penalty"] > 0 and first in recent_positions:
        score -= prof["revisit_penalty"]

    if urgent and exit_cell is not None:
        before = nearest_goal_distance(pac_cell, {exit_cell}, walkable, 40)
        after = nearest_goal_distance(first, {exit_cell}, walkable, 40)
        score += (before - after) * 500.0
        if after >= before:
            score -= 750.0

    return (score, mode, best_safe, pellet_bonus, alive_horizon, reserved_blocked)

def choose_safest_move(pac_cell, goals, walkable, fear, hard_block, ghost_timelines,
                       pockets, recent_positions=None):
    options = [n for n in neighbors(pac_cell, walkable) if n not in hard_block]
    if not options:
        options = neighbors(pac_cell, walkable)
    if not options:
        return (0, 0), "DONE", set(), 0, "LOW", 0.0, 0, 0

    ghost_by_time = ghost_cells_by_time(ghost_timelines)
    ghost_arrival = ghost_earliest_arrivals(ghost_timelines, walkable, LOOKAHEAD_TICKS)

    min_ghost_dist = ghost_arrival.get(pac_cell, 999)
    if min_ghost_dist <= THREAT_NEAR:
        threat = "HIGH"
    elif min_ghost_dist <= THREAT_MED:
        threat = "MED"
    else:
        threat = "LOW"

    reservations = build_ghost_reservations(ghost_timelines, walkable, threat,
                                            LOOKAHEAD_TICKS)

    scored = []
    for nb in options:
        score, mode, safe_count, pellet_bonus, alive_horizon, reserved_blocked = score_candidate(
            nb, pac_cell, goals, walkable, fear, ghost_by_time, ghost_arrival,
            pockets, threat=threat, recent_positions=recent_positions,
            reservations=reservations,
        )
        scored.append((score, nb, mode, safe_count, pellet_bonus,
                       alive_horizon, reserved_blocked))

    scored.sort(reverse=True, key=lambda item: (item[0], item[5], item[3]))
    best_score, best, mode, safe_count, pellet_bonus, alive_horizon, _blocked = scored[0]
    unsafe = {nb for score, nb, _mode, _safe, _pb, _h, _rb in scored if score < 0}
    reserved_blocked_total = sum(item[6] for item in scored)
    return ((best[0] - pac_cell[0], best[1] - pac_cell[1]), mode, unsafe,
            safe_count, threat, pellet_bonus, alive_horizon, reserved_blocked_total)
