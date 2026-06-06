"""Визуальные эффекты: градиентный фон, снег и стеклянные панели (liquid glass)."""

import math
import random

import pygame


# --- Палитра (фиолетовая тема liquid glass) ---
BG_TOP = (26, 16, 46)
BG_BOTTOM = (78, 44, 124)
# Бело-яркая тема для максимальной читаемости (фон остаётся ночным городом).
ACCENT = (226, 232, 245)
ACCENT_BRIGHT = (255, 255, 255)
TEXT = (255, 255, 255)
TEXT_DIM = (196, 204, 220)
SNAKE_BODY = (170, 120, 255)
SNAKE_HEAD = (214, 180, 255)
FOOD = (255, 110, 180)
PANEL_TINT = (150, 95, 230)
GLASS_BORDER = (216, 188, 255)

# --- Цвета арены (slither-режим) ---
ARENA_TOP = (16, 10, 30)
ARENA_BOTTOM = (32, 18, 56)
ARENA_GRID = (120, 90, 180)
BOUNDARY = (236, 120, 150)

# Цвет змейки игрока (яркий бирюзово-фиолетовый, выделяется среди ботов).
PLAYER_COLOR = (120, 230, 220)
PLAYER_HEAD = (200, 255, 250)

# Палитра для ботов — насыщенные различимые оттенки.
BOT_COLORS = [
    (255, 130, 90),
    (120, 200, 255),
    (255, 200, 90),
    (170, 130, 255),
    (120, 235, 150),
    (255, 120, 180),
    (140, 160, 255),
    (255, 160, 110),
    (110, 220, 200),
    (210, 130, 255),
    (255, 110, 110),
    (160, 255, 120),
]


def make_gradient(size: tuple[int, int], top: tuple = BG_TOP, bottom: tuple = BG_BOTTOM) -> pygame.Surface:
    """Создаёт вертикальный градиент с мягким свечением по центру."""
    w, h = size
    surf = pygame.Surface((w, h))
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        pygame.draw.line(surf, (r, g, b), (0, y), (w, y))

    # Мягкое радиальное свечение по центру для глубины.
    glow = pygame.Surface((w, h), pygame.SRCALPHA)
    radius = int(min(w, h) * 0.55)
    cx, cy = w // 2, int(h * 0.42)
    steps = 28
    for i in range(steps):
        t = i / steps
        rr = int(radius * (1 - t))
        alpha = int(30 * t)
        pygame.draw.circle(glow, (150, 100, 220, alpha), (cx, cy), rr)
    surf.blit(glow, (0, 0))
    return surf


def blur_surface(surface: pygame.Surface, downscale: float = 0.16) -> pygame.Surface:
    """Дешёвое размытие через уменьшение и увеличение (эффект матового стекла)."""
    w, h = surface.get_size()
    sw, sh = max(1, int(w * downscale)), max(1, int(h * downscale))
    small = pygame.transform.smoothscale(surface, (sw, sh))
    return pygame.transform.smoothscale(small, (w, h))


def draw_glass_panel(
    screen: pygame.Surface,
    rect: pygame.Rect,
    radius: int = 18,
    tint: tuple = PANEL_TINT,
    tint_alpha: int = 70,
    border_alpha: int = 120,
    glow: bool = False,
):
    """Рисует панель в стиле liquid glass: размытый фон, полупрозрачная заливка,
    мягкий внутренний блик и тонкая светящаяся рамка."""
    rect = rect.clip(screen.get_rect())
    if rect.width <= 2 or rect.height <= 2:
        return

    # Мягкое свечение вокруг выбранной панели (плавный ореол без жёстких краёв).
    if glow:
        pad = 22
        glow_surf = pygame.Surface((rect.width + pad * 2, rect.height + pad * 2), pygame.SRCALPHA)
        layers = 8
        for i in range(layers):
            t = i / (layers - 1)
            a = int(34 * (1 - t))
            if a <= 0:
                continue
            inset = int(pad * t)
            gr = pygame.Rect(
                inset,
                inset,
                glow_surf.get_width() - inset * 2,
                glow_surf.get_height() - inset * 2,
            )
            pygame.draw.rect(glow_surf, (*ACCENT_BRIGHT, a), gr, border_radius=radius + pad)
        screen.blit(glow_surf, (rect.x - pad, rect.y - pad))

    # Размытый снимок фона под панелью (эффект матового стекла).
    region = screen.subsurface(rect).copy()
    blurred = blur_surface(region).convert_alpha()

    mask = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    blurred.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    screen.blit(blurred, rect.topleft)

    # Полупрозрачная заливка + верхний градиентный блик + двойная рамка.
    overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(overlay, (*tint, tint_alpha), overlay.get_rect(), border_radius=radius)

    # Внутренний верхний блик — мягкий вертикальный градиент сверху.
    hl_h = max(4, int(rect.height * 0.5))
    highlight = pygame.Surface((rect.width, hl_h), pygame.SRCALPHA)
    for y in range(hl_h):
        a = int(40 * (1 - y / hl_h))
        if a <= 0:
            continue
        pygame.draw.line(highlight, (255, 255, 255, a), (0, y), (rect.width, y))
    hl_mask = pygame.Surface((rect.width, hl_h), pygame.SRCALPHA)
    pygame.draw.rect(
        hl_mask, (255, 255, 255, 255), hl_mask.get_rect(),
        border_top_left_radius=radius, border_top_right_radius=radius,
    )
    highlight.blit(hl_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    overlay.blit(highlight, (0, 0))

    # Внешняя тонкая светящаяся рамка + мягкая внутренняя линия для объёма.
    b_alpha = 200 if glow else border_alpha
    pygame.draw.rect(overlay, (*GLASS_BORDER, b_alpha), overlay.get_rect(),
                     width=1, border_radius=radius)
    inner = overlay.get_rect().inflate(-2, -2)
    pygame.draw.rect(overlay, (255, 255, 255, 26), inner, width=1, border_radius=max(2, radius - 1))
    screen.blit(overlay, rect.topleft)


class Snowflake:
    __slots__ = ("x", "y", "radius", "speed", "drift", "phase", "alpha")

    def __init__(self, w: int, h: int):
        self.reset(w, h, randomize_y=True)

    def reset(self, w: int, h: int, randomize_y: bool = False):
        self.x = random.uniform(0, w)
        self.y = random.uniform(-h, 0) if not randomize_y else random.uniform(0, h)
        self.radius = random.uniform(1.0, 3.2)
        self.speed = random.uniform(16, 48)
        self.drift = random.uniform(8, 24)
        self.phase = random.uniform(0, math.tau)
        self.alpha = random.randint(45, 130)


class Snow:
    """Снегопад в экранных координатах с плавным появлением/затуханием.

    intensity 0..1 управляет и скоростью (снег «замирает»), и прозрачностью,
    что даёт мягкий fade при включении/выключении."""

    def __init__(self, w: int, h: int, count: int = 90):
        self.w = w
        self.h = h
        self.flakes = [Snowflake(w, h) for _ in range(count)]
        self.intensity = 1.0
        self.target = 1.0

    def resize(self, w: int, h: int):
        self.w = w
        self.h = h
        for f in self.flakes:
            if f.x > w:
                f.x = random.uniform(0, w)

    def set_active(self, on: bool):
        self.target = 1.0 if on else 0.0

    def update(self, dt: float):
        # Плавное приближение интенсивности к цели.
        self.intensity += (self.target - self.intensity) * min(1.0, dt * 2.6)
        if self.intensity < 0.01:
            self.intensity = 0.0
            return
        scale = self.intensity
        for f in self.flakes:
            f.phase += dt * 1.4
            f.y += f.speed * dt * scale
            f.x += math.sin(f.phase) * f.drift * dt * scale
            if f.y > self.h + 4:
                f.reset(self.w, self.h)
                f.y = -4

    def draw(self, screen: pygame.Surface):
        if self.intensity < 0.02:
            return
        flake_surf = pygame.Surface((12, 12), pygame.SRCALPHA)
        k = self.intensity
        for f in self.flakes:
            flake_surf.fill((0, 0, 0, 0))
            r = max(1, int(round(f.radius)))
            a = int(f.alpha * k)
            pygame.draw.circle(flake_surf, (255, 255, 255, a // 3), (6, 6), r + 2)
            pygame.draw.circle(flake_surf, (255, 255, 255, a), (6, 6), r)
            screen.blit(flake_surf, (int(f.x) - 6, int(f.y) - 6))
