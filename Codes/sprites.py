"""All pygame.sprite.Sprite subclasses: walls, pellets, Pacman, ghosts."""

from collections import deque

import pygame

from . import config


class Wall(pygame.sprite.Sprite):
    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: tuple[int, int, int],
    ) -> None:
        super().__init__()
        self.image = pygame.Surface((width, height))
        self.image.fill(color)
        self.rect = self.image.get_rect()
        self.rect.left = x
        self.rect.top = y


class Block(pygame.sprite.Sprite):
    def __init__(
        self,
        color: tuple[int, int, int],
        width: int,
        height: int,
    ) -> None:
        super().__init__()
        self.image = pygame.Surface((width, height))
        self.image.fill(config.WHITE)
        self.image.set_colorkey(config.WHITE)
        pygame.draw.ellipse(self.image, color, (0, 0, width, height))
        self.rect = self.image.get_rect()


class Player(pygame.sprite.Sprite):
    change_x: int = 0
    change_y: int = 0

    def __init__(self, x: int, y: int, filename: str) -> None:
        super().__init__()
        self.image = pygame.image.load(filename).convert()
        self.rect = self.image.get_rect()
        self.rect.left = x
        self.rect.top = y
        self.prev_x = x
        self.prev_y = y
        self.recent_positions = deque(maxlen=config.RECENT_LEN)

    def prevdirection(self) -> None:
        self.prev_x = self.change_x
        self.prev_y = self.change_y

    def changespeed(self, x: int, y: int) -> None:
        self.change_x += x
        self.change_y += y

    def update(self, walls, gate) -> None:
        old_x = self.rect.left
        old_y = self.rect.top

        self._move_horizontal(old_x, walls)
        self._move_vertical(old_y, walls)
        self._handle_gate_collision(old_x, old_y, gate)

    def _move_horizontal(self, old_x, walls) -> None:
        self.rect.left += self.change_x
        if pygame.sprite.spritecollide(self, walls, False):
            self.rect.left = old_x

    def _move_vertical(self, old_y, walls) -> None:
        self.rect.top += self.change_y
        if pygame.sprite.spritecollide(self, walls, False):
            self.rect.top = old_y
    
    def _handle_gate_collision(self, old_x, old_y, gate) -> None:
        has_gate = gate is not False
        if has_gate == False:
            return

        collided = pygame.sprite.spritecollide(self, gate, False)
        if collided:
            self.rect.left = old_x
            self.rect.top = old_y

class Ghost(Player):
    def changespeed( self, directions, ghost_name, turn, steps, last_turn ) -> list[int]:
        try:
            return self._next_direction( directions, ghost_name, turn, steps, last_turn )
        except IndexError as error:
            print(f"Ghost path error: {error}")
            return [0, 0]

    def _next_direction( self, directions, ghost_name, turn, steps, last_turn ):
        duration = directions[turn][2]
        if steps < duration:
            return self._continue_direction(directions, turn, steps)

        return self._change_direction( directions, ghost_name, turn, last_turn )

    def _continue_direction(self, directions, turn, steps):
        self.change_x = directions[turn][0]
        self.change_y = directions[turn][1]
        return [turn, steps + 1]

    def _change_direction( self, directions, ghost_name, turn, last_turn ):
        turn = self._next_turn(turn, ghost_name, last_turn)
        self.change_x = directions[turn][0]
        self.change_y = directions[turn][1]
        return [turn, 0]

    def _next_turn( self, turn, ghost_name, last_turn ):
        has_more_turns = turn < last_turn
        if has_more_turns:
            return turn + 1

        is_clyde = ghost_name == "clyde"
        if is_clyde:
            return 2

        return 0

    
