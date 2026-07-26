"""Grid-level primitives shared by every other AI module.

Everything here treats the maze as a lattice of STEP-sized cells snapped to
(ORIGIN_X, ORIGIN_Y), independent of any pathfinding strategy.
"""

from collections import deque

import pygame

from . import config

STEP = config.STEP
ORIGIN_X = config.ORIGIN_X
ORIGIN_Y = config.ORIGIN_Y


def snap_to_grid(x, y):
    gx = ORIGIN_X + round((x - ORIGIN_X) / STEP) * STEP
    gy = ORIGIN_Y + round((y - ORIGIN_Y) / STEP) * STEP
    return (gx, gy)


def build_walkable_cells(start, wall_list, gate, pac_rect):
    walkable = set()
    probe = pygame.sprite.Sprite()
    probe.image = pygame.Surface([pac_rect.width, pac_rect.height])
    probe.rect = probe.image.get_rect()

    def is_free(cx, cy):
        probe.rect.left = cx
        probe.rect.top = cy
        if pygame.sprite.spritecollide(probe, wall_list, False):
            return False
        if gate and pygame.sprite.spritecollide(probe, gate, False):
            return False
        return True

    if not is_free(*start):
        return walkable
    walkable.add(start)
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((STEP, 0), (-STEP, 0), (0, STEP), (0, -STEP)):
            nb = (x + dx, y + dy)
            if nb in walkable:
                continue
            if not (0 <= nb[0] <= 606 and 0 <= nb[1] <= 606):
                continue
            if is_free(*nb):
                walkable.add(nb)
                q.append(nb)
    return walkable


def neighbors(cell, walkable):
    out = []
    for dx, dy in ((STEP, 0), (-STEP, 0), (0, STEP), (0, -STEP)):
        nb = (cell[0] + dx, cell[1] + dy)
        if nb in walkable:
            out.append(nb)
    return out


def bfs_distances(sources, walkable, max_dist, blocked=None):
    dist = {}
    q = deque()
    blocked = blocked or set()
    for s in sources:
        if s in walkable and s not in dist and s not in blocked:
            dist[s] = 0
            q.append(s)
    while q:
        node = q.popleft()
        d = dist[node]
        if d >= max_dist:
            continue
        for nb in neighbors(node, walkable):
            if nb in blocked or nb in dist:
                continue
            dist[nb] = d + 1
            q.append(nb)
    return dist
