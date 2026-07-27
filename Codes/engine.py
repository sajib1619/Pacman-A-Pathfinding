"""Pygame bootstrap: display, clock, fonts, and background music.

Importing this module has side effects (it opens a window and initializes
the mixer) -- that mirrors the original script and keeps a single shared
`screen`/`clock`/`font` for the rest of the game to draw with.
"""

import pygame

from . import config

pygame.mixer.init()
try:
    pygame.mixer.music.load('pacman.mp3')
    pygame.mixer.music.play(-1, 0.0)
except pygame.error as error:
    print(f"Music could not be loaded: {error}")

pygame.init()
screen = pygame.display.set_mode(config.SCREEN_SIZE)
pygame.display.set_caption('Pacman - A* Pathfinding')
background = pygame.Surface(screen.get_size()).convert()
background.fill(config.BLACK)
clock = pygame.time.Clock()

pygame.font.init()
font = pygame.font.Font("freesansbold.ttf", 22)
small_font = pygame.font.Font("freesansbold.ttf", 13)
