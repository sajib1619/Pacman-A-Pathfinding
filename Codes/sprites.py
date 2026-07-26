"""All pygame.sprite.Sprite subclasses: walls, pellets, Pacman, ghosts."""

from collections import deque

import pygame

from . import config


class Wall(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, color):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface([width, height])
        self.image.fill(color)
        self.rect = self.image.get_rect()
        self.rect.top = y
        self.rect.left = x


class Block(pygame.sprite.Sprite):
    def __init__(self, color, width, height):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface([width, height])
        self.image.fill(config.WHITE)
        self.image.set_colorkey(config.WHITE)
        pygame.draw.ellipse(self.image, color, [0, 0, width, height])
        self.rect = self.image.get_rect()


class Player(pygame.sprite.Sprite):
    change_x = 0
    change_y = 0

    def __init__(self, x, y, filename):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.image.load(filename).convert()
        self.rect = self.image.get_rect()
        self.rect.top = y
        self.rect.left = x
        self.prev_x = x
        self.prev_y = y
        self.recent_positions = deque(maxlen=config.RECENT_LEN)

    def prevdirection(self):
        self.prev_x = self.change_x
        self.prev_y = self.change_y

    def changespeed(self, x, y):
        self.change_x += x
        self.change_y += y

    def update(self, walls, gate):
        old_x = self.rect.left
        self.rect.left = old_x + self.change_x
        old_y = self.rect.top
        new_y = old_y + self.change_y

        if pygame.sprite.spritecollide(self, walls, False):
            self.rect.left = old_x
        else:
            self.rect.top = new_y
            if pygame.sprite.spritecollide(self, walls, False):
                self.rect.top = old_y

        if gate is not False:
            if pygame.sprite.spritecollide(self, gate, False):
                self.rect.left = old_x
                self.rect.top = old_y


class Ghost(Player):
    def changespeed(self, list, ghost, turn, steps, l):
        try:
            z = list[turn][2]
            if steps < z:
                self.change_x = list[turn][0]
                self.change_y = list[turn][1]
                steps += 1
            else:
                if turn < l:
                    turn += 1
                elif ghost == "clyde":
                    turn = 2
                else:
                    turn = 0
                self.change_x = list[turn][0]
                self.change_y = list[turn][1]
                steps = 0
            return [turn, steps]
        except IndexError:
            return [0, 0]
