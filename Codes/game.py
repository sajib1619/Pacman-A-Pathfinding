"""Level setup and the main game loop.

Wires together the maze, sprites, ghost forecasting, fear field, and planner
each tick, then draws the result (including debug overlays for the fear
field, unsafe candidates, and forecasted ghost paths).
"""

import pygame

from . import config
from .engine import screen, clock, font, small_font, background
from .sprites import Player, Ghost, Block
from .maze import setupRoomOne, setupGate
from .grid import build_walkable_cells, snap_to_grid, bfs_distances
from .graph import compute_articulations, iter_pockets
from .ghost_forecast import ghost_direction_meta, forecast_ghost_timelines, ghost_earliest_arrivals
from .fear_field import build_fear_field
from .pathfinding import emergency_move
from .planner import choose_safest_move
from .ghost_tables import (
    Pinky_directions, Blinky_directions, Inky_directions, Clyde_directions,
    pl, bl, il, cl,
)

w, p_h, m_h, b_h, i_w, c_w = config.w, config.p_h, config.m_h, config.b_h, config.i_w, config.c_w
STEP = config.STEP
LOOKAHEAD_TICKS = config.LOOKAHEAD_TICKS
THREAT_NEAR = config.THREAT_NEAR
THREAT_MED = config.THREAT_MED
SAFE_MARGIN = config.SAFE_MARGIN
DANGER_RADIUS = config.DANGER_RADIUS
CHOKE_PENALTY = config.CHOKE_PENALTY
ROLLOUT_DEPTH = config.ROLLOUT_DEPTH
DIR_NAME = config.DIR_NAME


def startGame():
    all_sprites_list = pygame.sprite.RenderPlain()
    block_list = pygame.sprite.RenderPlain()
    monsta_list = pygame.sprite.RenderPlain()
    pacman_collide = pygame.sprite.RenderPlain()
    wall_list = setupRoomOne(all_sprites_list)
    gate = setupGate(all_sprites_list)

    p_turn = p_steps = 0
    b_turn = b_steps = 0
    i_turn = i_steps = 0
    c_turn = c_steps = 0

    Pacman = Player(w, p_h, "images/Trollman.png")
    all_sprites_list.add(Pacman)
    pacman_collide.add(Pacman)

    Blinky = Ghost(w, b_h, "images/Blinky.png"); monsta_list.add(Blinky); all_sprites_list.add(Blinky)
    Pinky  = Ghost(w, m_h, "images/Pinky.png");  monsta_list.add(Pinky);  all_sprites_list.add(Pinky)
    Inky   = Ghost(i_w, m_h, "images/Inky.png"); monsta_list.add(Inky);   all_sprites_list.add(Inky)
    Clyde  = Ghost(c_w, m_h, "images/Clyde.png"); monsta_list.add(Clyde); all_sprites_list.add(Clyde)

    for row in range(19):
        for column in range(19):
            if (row == 7 or row == 8) and (column in (8, 9, 10)):
                continue
            block = Block(config.yellow, 4, 4)
            block.rect.x = (30 * column + 6) + 26
            block.rect.y = (30 * row + 6) + 26
            if pygame.sprite.spritecollide(block, wall_list, False):
                continue
            if pygame.sprite.spritecollide(block, pacman_collide, False):
                continue
            block_list.add(block)
            all_sprites_list.add(block)

    bll = len(block_list)
    score = 0
    done = False

    walkable = build_walkable_cells(
        (Pacman.rect.left, Pacman.rect.top), wall_list, gate, Pacman.rect
    )
    art_points, pockets = compute_articulations(walkable)
    ghosts = [Blinky, Pinky, Inky, Clyde]

    start_cell = (Pacman.rect.left, Pacman.rect.top)
    visited = {start_cell}
    last_move = "STAY"
    mode = "HUNT"

    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                done = True

        # ---- AI decision ----
        pac_cell = snap_to_grid(Pacman.rect.left, Pacman.rect.top)
        ghost_meta = [
            ghost_direction_meta(Blinky, b_turn, b_steps, Blinky_directions, "blinky", bl),
            ghost_direction_meta(Pinky, p_turn, p_steps, Pinky_directions, "pinky", pl),
            ghost_direction_meta(Inky, i_turn, i_steps, Inky_directions, "inky", il),
            ghost_direction_meta(Clyde, c_turn, c_steps, Clyde_directions, "clyde", cl),
        ]
        ghost_timelines = forecast_ghost_timelines(ghost_meta, walkable, LOOKAHEAD_TICKS)
        fear, hard_block = build_fear_field(ghost_timelines, pac_cell, walkable, art_points, pockets)
        hard_block.discard(pac_cell)
        unsafe_candidates = set()
        safe_count = 0
        threat_level = "LOW"
        pellet_bonus = 0.0
        alive_horizon = 0
        reserved_blocked = 0

        if pac_cell in walkable:
            visited.add(pac_cell)
            unvisited = walkable - visited

            # v5: compute preliminary threat to loosen goal filtering when calm.
            ghost_arrival_pre = ghost_earliest_arrivals(ghost_timelines, walkable, LOOKAHEAD_TICKS)
            _mgd = ghost_arrival_pre.get(pac_cell, 999)
            if _mgd <= THREAT_NEAR:
                pre_threat = "HIGH"
            elif _mgd <= THREAT_MED:
                pre_threat = "MED"
            else:
                pre_threat = "LOW"

            # Goal filtering: drop pellets inside pockets whose exit can be
            # reached by a ghost before Pacman can safely return. Under LOW
            # threat, only drop pockets the ghost is already inside/adjacent to.
            filtered = set(unvisited)
            if unvisited:
                unsafe_cells = set()
                pac_dist = bfs_distances([pac_cell], walkable, 80)
                for ap, pocket in iter_pockets(pockets):
                    pd = pac_dist.get(ap)
                    gdv = ghost_arrival_pre.get(ap, 999)
                    if pd is None:
                        continue
                    if pre_threat == "LOW":
                        # Only drop if ghost is already at/adjacent to the pocket exit.
                        if gdv <= 1:
                            unsafe_cells |= (set(pocket) - {ap})
                    else:
                        if gdv <= pd + SAFE_MARGIN:
                            unsafe_cells |= (set(pocket) - {ap})
                filtered = unvisited - unsafe_cells

            goals_used = filtered if filtered else unvisited
            move, mode, unsafe_candidates, safe_count, threat_level, pellet_bonus, alive_horizon, reserved_blocked = choose_safest_move(
                pac_cell, goals_used, walkable, fear, hard_block, ghost_timelines, pockets,
                recent_positions=list(Pacman.recent_positions),
            )
            Pacman.recent_positions.append(pac_cell)

            # Last-resort fallback if all scored moves are terrible.
            if move == (0, 0):
                move = emergency_move(pac_cell, walkable, fear, hard_block)
                mode = "EMERGENCY"

            Pacman.change_x, Pacman.change_y = move
            last_move = DIR_NAME.get(move, f"({move[0]},{move[1]})")

        # ---- Game logic ----
        Pacman.update(wall_list, gate)

        r = Pinky.changespeed(Pinky_directions, False, p_turn, p_steps, pl); p_turn, p_steps = r
        Pinky.changespeed(Pinky_directions, False, p_turn, p_steps, pl); Pinky.update(wall_list, False)

        r = Blinky.changespeed(Blinky_directions, False, b_turn, b_steps, bl); b_turn, b_steps = r
        Blinky.changespeed(Blinky_directions, False, b_turn, b_steps, bl); Blinky.update(wall_list, False)

        r = Inky.changespeed(Inky_directions, False, i_turn, i_steps, il); i_turn, i_steps = r
        Inky.changespeed(Inky_directions, False, i_turn, i_steps, il); Inky.update(wall_list, False)

        r = Clyde.changespeed(Clyde_directions, "clyde", c_turn, c_steps, cl); c_turn, c_steps = r
        Clyde.changespeed(Clyde_directions, "clyde", c_turn, c_steps, cl); Clyde.update(wall_list, False)

        blocks_hit_list = pygame.sprite.spritecollide(Pacman, block_list, True)
        if blocks_hit_list:
            score += len(blocks_hit_list)

        # ---- Draw ----
        screen.fill(config.black)
        wall_list.draw(screen)
        gate.draw(screen)
        all_sprites_list.draw(screen)
        monsta_list.draw(screen)

        # Visualize the fear field, unsafe first-step candidates, and future ghosts.
        max_fear = max(fear.values()) if fear else 1.0
        if max_fear > 0:
            for cell, f in fear.items():
                if f <= 0:
                    continue
                alpha = int(min(150, 25 + 125 * (f / max_fear)))
                overlay = pygame.Surface((STEP, STEP), pygame.SRCALPHA)
                overlay.fill((255, 60, 60, alpha))
                screen.blit(overlay, cell)

        for cell in unsafe_candidates:
            overlay = pygame.Surface((STEP, STEP), pygame.SRCALPHA)
            overlay.fill((255, 120, 0, 115))
            screen.blit(overlay, cell)

        for line in ghost_timelines:
            for cell in line[1:LOOKAHEAD_TICKS + 1]:
                if cell in walkable:
                    pygame.draw.circle(screen, config.purple, (cell[0] + 15, cell[1] + 15), 4)

        text = font.render(f"Score: {score}/{bll}", True, config.red)
        screen.blit(text, [10, 10])

        color = config.red if mode == "EMERGENCY" or mode.startswith("TRAPPED") else (
            config.orange if mode.startswith(("ESCAPE", "AVOID-TRAP", "GHOST-WALL")) else config.yellow)
        move_text = font.render(f"{mode}: {last_move}  safe={safe_count}", True, color)
        screen.blit(move_text, [330, 10])

        threat_color = config.red if threat_level == "HIGH" else (
            config.orange if threat_level == "MED" else config.yellow)
        threat_text = small_font.render(
            f"threat={threat_level}  pellet_bonus={pellet_bonus:+.1f}",
            True, threat_color)
        screen.blit(threat_text, [330, 40])

        wall_text = small_font.render(
            f"ghost-wall on  alive_horizon={alive_horizon}  reserved_blocked={reserved_blocked}",
            True, config.white)
        screen.blit(wall_text, [330, 58])

        v7_text = small_font.render("fc-desync-fix on  swap-guard on", True, config.white)
        screen.blit(v7_text, [330, 76])

        hint = small_font.render(
            f"radius={DANGER_RADIUS}  real-lookahead={LOOKAHEAD_TICKS}t  "
            f"choke={CHOKE_PENALTY:.0f}  rollout={ROLLOUT_DEPTH}",
            True, config.white)
        screen.blit(hint, [10, 588])

        if score == bll:
            doNext("Congratulations, you won!", 145,
                   all_sprites_list, block_list, monsta_list,
                   pacman_collide, wall_list, gate)

        if pygame.sprite.spritecollide(Pacman, monsta_list, False):
            doNext("Game Over", 235,
                   all_sprites_list, block_list, monsta_list,
                   pacman_collide, wall_list, gate)

        pygame.display.flip()
        clock.tick(10)


def doNext(message, left, all_sprites_list, block_list, monsta_list,
           pacman_collide, wall_list, gate):
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                if event.key == pygame.K_RETURN:
                    del all_sprites_list, block_list, monsta_list
                    del pacman_collide, wall_list, gate
                    startGame()

        w2 = pygame.Surface((400, 200))
        w2.set_alpha(10)
        w2.fill((128, 128, 128))
        screen.blit(w2, (100, 200))

        text1 = font.render(message, True, config.white)
        screen.blit(text1, [left, 233])
        text2 = font.render("To play again, press ENTER.", True, config.white)
        screen.blit(text2, [135, 303])
        text3 = font.render("To quit, press ESCAPE.", True, config.white)
        screen.blit(text3, [165, 333])

        pygame.display.flip()
        clock.tick(10)
