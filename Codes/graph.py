"""Static structural analysis of the walkable lattice.

Finds articulation points ("choke points") and the pockets/dead-ends they
guard, so the AI can reason about which regions a ghost could seal off.
"""

from collections import deque

from .grid import neighbors


def compute_articulations(walkable):
    """Tarjan articulation pass.

    Returns (art_points, pockets), where pockets[ap] contains every component
    exposed when articulation point `ap` is removed. v3 only kept the smallest
    component, which missed several real trap corridors.
    """
    if not walkable:
        return set(), {}
    adj = {c: neighbors(c, walkable) for c in walkable}

    disc = {}
    low = {}
    parent = {}
    art = set()
    timer = [0]

    def dfs(root):
        # Iterative DFS to avoid recursion limits.
        stack = [(root, iter(adj[root]))]
        disc[root] = low[root] = timer[0]; timer[0] += 1
        parent[root] = None
        children_root = 0
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                stack.pop()
                if stack:
                    par = stack[-1][0]
                    low[par] = min(low[par], low[node])
                    if parent[par] is not None and low[node] >= disc[par]:
                        art.add(par)
                continue
            if nxt not in disc:
                parent[nxt] = node
                disc[nxt] = low[nxt] = timer[0]; timer[0] += 1
                stack.append((nxt, iter(adj[nxt])))
                if node is root:
                    children_root += 1
            elif nxt is not parent[node]:
                low[node] = min(low[node], disc[nxt])
        if children_root > 1:
            art.add(root)

    for cell in walkable:
        if cell not in disc:
            dfs(cell)

    pockets = {}
    for ap in art:
        seen_global = {ap}
        components = []
        for nb in adj[ap]:
            if nb in seen_global:
                continue
            comp = set()
            q = deque([nb])
            comp.add(nb); seen_global.add(nb)
            while q:
                x = q.popleft()
                for y in adj[x]:
                    if y in seen_global or y == ap:
                        continue
                    seen_global.add(y); comp.add(y); q.append(y)
            components.append(frozenset(comp))
        if len(components) >= 2:
            pockets[ap] = components
    return art, pockets


def iter_pockets(pockets):
    for ap, comps in pockets.items():
        # Ignore the largest component for each articulation point; that is
        # usually the main maze. The other components are the places that can
        # become sealed traps.
        if not comps:
            continue
        largest = max(comps, key=len)
        for comp in comps:
            if comp is not largest:
                yield ap, comp


def containing_pocket(cell, pockets):
    best = None
    for ap, pocket in iter_pockets(pockets):
        if cell in pocket:
            item = (ap, pocket)
            if best is None or len(pocket) < len(best[1]):
                best = item
    return best
