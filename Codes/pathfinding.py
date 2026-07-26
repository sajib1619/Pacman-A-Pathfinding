"""Weighted A* over the fear field, and a last-resort emergency move."""

import heapq

from .grid import neighbors, STEP


def weighted_astar(start, goals, walkable, fear, blocked, extra_block=None):
    if not goals or start not in walkable:
        return None
    goals = set(g for g in goals if g in walkable)
    if not goals:
        return None
    if start in goals:
        return [start]
    extra_block = extra_block or set()

    def h(n):
        return min(abs(n[0] - g[0]) + abs(n[1] - g[1]) for g in goals) / STEP

    open_heap = []
    heapq.heappush(open_heap, (h(start), 0.0, start))
    came_from = {start: None}
    gscore = {start: 0.0}

    while open_heap:
        f, g, node = heapq.heappop(open_heap)
        if node in goals:
            path = []
            cur = node
            while cur is not None:
                path.append(cur)
                cur = came_from[cur]
            path.reverse()
            return path
        for nb in neighbors(node, walkable):
            if nb in extra_block and nb not in goals:
                continue
            if nb in blocked and nb not in goals:
                continue
            step_cost = 1.0 + fear.get(nb, 0.0)
            ng = g + step_cost
            if ng < gscore.get(nb, 1e18):
                gscore[nb] = ng
                came_from[nb] = node
                heapq.heappush(open_heap, (ng + h(nb), ng, nb))
    return None


def emergency_move(start, walkable, fear, blocked):
    opts = neighbors(start, walkable)
    if not opts:
        return (0, 0)
    candidates = [n for n in opts if n not in blocked] or opts
    best = min(candidates,
               key=lambda n: (fear.get(n, 0.0), -len(neighbors(n, walkable))))
    return (best[0] - start[0], best[1] - start[1])
