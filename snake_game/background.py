"""Аниме-фон: ночной город, звёздное небо, гавань с отражениями.

Всё рисуется примитивами pygame (без внешних картинок). Статичные слои
(небо, облака, силуэты зданий с окнами, отражения, передний план)
пре-рендерятся в кэш-поверхность при изменении размера. Анимируются лишь
дешёвые слои: мерцание звёзд, блики на воде и тонкие струи дождя."""

import math
import random

import pygame


SKY_TOP = (10, 13, 38)
SKY_MID = (20, 27, 66)
SKY_HORIZON = (54, 48, 92)
WARM_GLOW = (214, 150, 120)

BUILDING_FAR = (52, 58, 92)
BUILDING_NEAR = (24, 28, 52)
WINDOW_COLORS = [(255, 178, 90), (255, 205, 120), (255, 150, 70), (255, 225, 150)]

WATER_TOP = (40, 48, 84)
WATER_BOTTOM = (12, 16, 36)
FOREGROUND = (7, 8, 16)
LAMP_GLOW = (255, 200, 120)


class CityBackground:
    def __init__(self, w: int, h: int):
        self.build(w, h)

    def resize(self, w: int, h: int):
        self.build(w, h)

    # --- Построение статичных слоёв ---

    def build(self, w: int, h: int):
        self.w = max(1, w)
        self.h = max(1, h)
        self.horizon = int(self.h * 0.60)
        self.water_bottom = int(self.h * 0.85)
        rng = random.Random(20240607)

        # Окна, которые мигают (загораются/гаснут) поверх статичного слоя.
        self.blink_windows: list[tuple] = []
        self._blink_cap = 190

        self.static = pygame.Surface((self.w, self.h)).convert()
        self._draw_sky(self.static)
        self._draw_clouds(self.static, rng)
        self.stars = self._gen_stars(rng)

        skyline = self._build_skyline(rng)
        self.static.blit(skyline, (0, 0))
        self._draw_water(self.static, skyline)
        self._draw_foreground(self.static)

    def _draw_sky(self, surf):
        h = self.horizon + int(self.h * 0.08)
        for y in range(self.h):
            if y < h:
                t = y / max(1, h)
                if t < 0.6:
                    c = _lerp(SKY_TOP, SKY_MID, t / 0.6)
                else:
                    c = _lerp(SKY_MID, SKY_HORIZON, (t - 0.6) / 0.4)
            else:
                c = SKY_HORIZON
            pygame.draw.line(surf, c, (0, y), (self.w, y))

        # Тёплое свечение у горизонта (слева от центра).
        glow = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        gx, gy = int(self.w * 0.42), self.horizon
        for i in range(26):
            t = i / 26
            rr = int(self.w * 0.34 * (1 - t))
            a = int(46 * t)
            pygame.draw.ellipse(
                glow, (*WARM_GLOW, a),
                pygame.Rect(gx - rr, gy - rr // 3, rr * 2, rr * 2 // 3),
            )
        surf.blit(glow, (0, 0))

    def _draw_clouds(self, surf, rng):
        clouds = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for _ in range(7):
            cx = rng.uniform(0, self.w)
            cy = rng.uniform(self.h * 0.05, self.horizon * 0.55)
            base_r = rng.uniform(self.w * 0.05, self.w * 0.12)
            tint = rng.choice([(150, 150, 190), (120, 120, 170), (180, 160, 190)])
            for _ in range(6):
                ox = rng.uniform(-base_r, base_r)
                oy = rng.uniform(-base_r * 0.35, base_r * 0.35)
                rr = int(base_r * rng.uniform(0.5, 1.0))
                pygame.draw.circle(clouds, (*tint, 16), (int(cx + ox), int(cy + oy)), rr)
        surf.blit(clouds, (0, 0))

    def _gen_stars(self, rng):
        stars = []
        count = max(80, int(self.w * self.h / 9000))
        top_limit = int(self.horizon * 0.85)
        for _ in range(count):
            x = rng.uniform(0, self.w)
            y = rng.uniform(0, top_limit)
            r = rng.choice([1, 1, 1, 2])
            base = rng.randint(90, 220)
            phase = rng.uniform(0, math.tau)
            speed = rng.uniform(1.0, 3.0)
            stars.append((x, y, r, base, phase, speed))
        return stars

    def _build_skyline(self, rng):
        surf = pygame.Surface((self.w, self.horizon), pygame.SRCALPHA)
        # Два слоя зданий: дальний (светлее) и ближний (темнее).
        self._building_layer(surf, rng, BUILDING_FAR, top_frac=0.42, width=(34, 70),
                             gap=(0, 6), lit_prob=0.30)
        self._building_layer(surf, rng, BUILDING_NEAR, top_frac=0.24, width=(46, 96),
                             gap=(2, 12), lit_prob=0.42)
        return surf

    def _building_layer(self, surf, rng, color, top_frac, width, gap, lit_prob):
        x = -rng.randint(0, 30)
        base = self.horizon
        while x < self.w:
            bw = rng.randint(*width)
            bh = rng.randint(int(self.horizon * top_frac), int(self.horizon * 0.92))
            top = base - bh
            rect = pygame.Rect(x, top, bw, bh + 2)
            pygame.draw.rect(surf, color, rect)
            # Светлый кант сверху для объёма.
            pygame.draw.line(surf, _lighten(color, 0.12), (x, top), (x + bw, top))
            # Антенна на части зданий.
            if rng.random() < 0.25:
                ax = x + bw // 2
                pygame.draw.line(surf, color, (ax, top), (ax, top - rng.randint(8, 24)), 2)
            self._draw_windows(surf, rect, rng, lit_prob, color)
            x += bw + rng.randint(*gap)

    def _draw_windows(self, surf, rect, rng, lit_prob, bcolor):
        margin = 5
        cell_w, cell_h = 7, 9
        gap_w, gap_h = 5, 6
        y = rect.top + margin + 4
        while y + cell_h < rect.bottom - 3:
            x = rect.left + margin
            while x + cell_w < rect.right - margin:
                cell = pygame.Rect(x, y, cell_w, cell_h)
                lit = rng.random() < lit_prob
                # Часть окон делаем «мигающими» — анимируются поверх статики.
                blink = (len(self.blink_windows) < self._blink_cap and
                         rng.random() < (0.32 if lit else 0.05))
                if blink:
                    # Медленные, редкие переключения — город «дышит» спокойно.
                    self.blink_windows.append(
                        (cell, bcolor, rng.choice(WINDOW_COLORS),
                         rng.uniform(0, math.tau), rng.uniform(0.10, 0.34)))
                elif lit:
                    pygame.draw.rect(surf, rng.choice(WINDOW_COLORS), cell)
                x += cell_w + gap_w
            y += cell_h + gap_h

    def _draw_water(self, surf, skyline):
        wh = self.water_bottom - self.horizon
        for i in range(wh):
            t = i / max(1, wh)
            c = _lerp(WATER_TOP, WATER_BOTTOM, t)
            pygame.draw.line(surf, c, (0, self.horizon + i), (self.w, self.horizon + i))

        # Отражение силуэта города.
        refl = pygame.transform.flip(skyline, False, True)
        mask = pygame.Surface(refl.get_size(), pygame.SRCALPHA)
        mask.fill((255, 255, 255, 95))
        refl.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(refl, (0, self.horizon))

        # Затухание отражения вглубь воды.
        fade = pygame.Surface((self.w, wh), pygame.SRCALPHA)
        for i in range(wh):
            t = i / max(1, wh)
            a = int(40 + 150 * t)
            pygame.draw.line(fade, (*WATER_BOTTOM, a), (0, i), (self.w, i))
        surf.blit(fade, (0, self.horizon))

        # Тонкая светлая линия уровня воды у горизонта.
        pygame.draw.line(surf, (90, 110, 150), (0, self.horizon), (self.w, self.horizon))

    def _draw_foreground(self, surf):
        top = self.water_bottom
        pygame.draw.rect(surf, FOREGROUND, (0, top, self.w, self.h - top))

        # Перила: верхний рельс + стойки.
        rail_y = top + int((self.h - top) * 0.28)
        pygame.draw.rect(surf, (12, 13, 22), (0, rail_y, self.w, 8))
        pygame.draw.rect(surf, (12, 13, 22), (0, rail_y + 26, self.w, 5))
        post_gap = max(60, self.w // 14)
        for px in range(post_gap // 2, self.w, post_gap):
            pygame.draw.rect(surf, (10, 11, 18), (px, rail_y, 7, self.h - rail_y))

        # Фонарь слева с тёплым свечением.
        lamp_x = int(self.w * 0.05)
        lamp_top = top - int(self.h * 0.22)
        glow = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for i in range(10):
            t = i / 9
            a = int(60 * (1 - t))
            pygame.draw.circle(glow, (*LAMP_GLOW, a), (lamp_x + 16, lamp_top), int(8 + 34 * t))
        surf.blit(glow, (0, 0))
        pygame.draw.rect(surf, (6, 7, 12), (lamp_x, lamp_top, 6, self.h - lamp_top))
        pygame.draw.line(surf, (6, 7, 12), (lamp_x + 3, lamp_top + 4), (lamp_x + 26, lamp_top + 4), 5)
        pygame.draw.circle(surf, (255, 214, 150), (lamp_x + 30, lamp_top + 6), 6)

        # Зонт-силуэт слева (как на референсе).
        ux = int(self.w * 0.09)
        uy = rail_y - 6
        pygame.draw.polygon(surf, (5, 6, 11),
                            [(ux - 26, uy), (ux + 26, uy), (ux, uy - 26)])
        pygame.draw.line(surf, (5, 6, 11), (ux, uy), (ux, self.h), 3)

        # Урна справа.
        bx = int(self.w * 0.82)
        pygame.draw.rect(surf, (9, 10, 17), (bx, rail_y - 14, 26, 40), border_radius=4)
        pygame.draw.rect(surf, (14, 15, 24), (bx - 3, rail_y - 18, 32, 6), border_radius=3)

    # --- Анимация ---

    def draw(self, screen, t: float, flicker: bool = True):
        screen.blit(self.static, (0, 0))
        self._draw_stars(screen, t)
        self._draw_windows_anim(screen, t, flicker)
        self._draw_water_shimmer(screen, t)

    def _draw_windows_anim(self, screen, t, flicker: bool = True):
        if not flicker:
            # Мерцание выключено — окна горят ровно.
            for (cell, bcolor, lit, phase, rate) in self.blink_windows:
                screen.fill(lit, cell)
            return
        for (cell, bcolor, lit, phase, rate) in self.blink_windows:
            # Окна в основном горят; гаснут редко и плавно (высокий порог).
            on = math.sin(t * rate + phase) > -0.55
            screen.fill(lit if on else bcolor, cell)

    def _draw_stars(self, screen, t):
        for (x, y, r, base, phase, speed) in self.stars:
            a = base * (0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * speed + phase)))
            v = min(255, int(a))
            screen.fill((v, v, v), (int(x), int(y), r, r))

    def _draw_water_shimmer(self, screen, t):
        overlay = pygame.Surface((self.w, self.water_bottom - self.horizon), pygame.SRCALPHA)
        n = 16
        for i in range(n):
            base_x = (i + 0.5) * self.w / n
            sway = 18 * math.sin(t * 1.3 + i)
            x = base_x + sway
            yy = int((self.water_bottom - self.horizon) * (0.15 + 0.7 * ((i * 0.137) % 1.0)))
            a = int(40 + 40 * (0.5 + 0.5 * math.sin(t * 2.0 + i * 1.7)))
            w = 26 + 18 * (0.5 + 0.5 * math.sin(t + i))
            pygame.draw.line(overlay, (255, 210, 150, a),
                             (int(x - w), yy), (int(x + w), yy), 2)
        screen.blit(overlay, (0, self.horizon))


def _lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _lighten(c, amount):
    return tuple(min(255, int(x + (255 - x) * amount)) for x in c)
