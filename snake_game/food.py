"""Еда (шарики-пеллеты) и поле еды с пространственной сеткой.

FoodField хранит все пеллеты, поддерживает целевое количество (респаун
со временем) и предоставляет быстрые запросы соседних пеллетов через
сетку ячеек, чтобы поедание не было O(n)."""

import math
import random

from effects import FOOD


CELL = 120.0


def _pellet_radius(value: float) -> float:
    return max(3.0, min(11.0, 3.0 + value * 0.7))


class Pellet:
    __slots__ = ("x", "y", "value", "color", "radius", "phase")

    def __init__(self, x: float, y: float, value: float, color):
        self.x = x
        self.y = y
        self.value = value
        self.color = color
        self.radius = _pellet_radius(value)
        self.phase = random.uniform(0.0, math.tau)


class FoodField:
    def __init__(self, world_radius: float, target: int = 550):
        self.world_radius = world_radius
        self.target = target
        self.pellets: list[Pellet] = []
        self._grid: dict[tuple[int, int], list[Pellet]] = {}
        self._spawn_accum = 0.0
        for _ in range(target):
            self.pellets.append(self._random_pellet())
        self.rebuild_grid()

    def _random_point(self) -> tuple[float, float]:
        # Равномерно внутри круга радиуса world_radius.
        r = self.world_radius * math.sqrt(random.random()) * 0.97
        a = random.uniform(0, math.tau)
        return r * math.cos(a), r * math.sin(a)

    def _random_pellet(self) -> Pellet:
        x, y = self._random_point()
        value = random.choice([1.0, 1.0, 1.0, 2.0, 3.0])
        tint = random.choice([
            FOOD, (255, 200, 120), (140, 220, 255),
            (180, 255, 160), (210, 160, 255),
        ])
        return Pellet(x, y, value, tint)

    def add(self, x: float, y: float, value: float, color):
        # Удерживаем внутри круга мира.
        d = math.hypot(x, y)
        if d > self.world_radius * 0.985:
            s = (self.world_radius * 0.985) / d
            x *= s
            y *= s
        self.pellets.append(Pellet(x, y, value, color))

    def maintain(self, dt: float):
        # Плавный респаун до целевого количества.
        if len(self.pellets) < self.target:
            self._spawn_accum += dt * 40.0
            while self._spawn_accum >= 1.0 and len(self.pellets) < self.target:
                self._spawn_accum -= 1.0
                self.pellets.append(self._random_pellet())

    def _key(self, x: float, y: float) -> tuple[int, int]:
        return (int(math.floor(x / CELL)), int(math.floor(y / CELL)))

    def rebuild_grid(self):
        grid: dict[tuple[int, int], list[Pellet]] = {}
        for p in self.pellets:
            grid.setdefault(self._key(p.x, p.y), []).append(p)
        self._grid = grid

    def query(self, x: float, y: float, radius: float) -> list[Pellet]:
        cx, cy = self._key(x, y)
        span = int(radius / CELL) + 1
        out = []
        for gx in range(cx - span, cx + span + 1):
            for gy in range(cy - span, cy + span + 1):
                bucket = self._grid.get((gx, gy))
                if bucket:
                    out.extend(bucket)
        return out

    def nearest(self, x: float, y: float, radius: float):
        best = None
        best_d = radius * radius
        for p in self.query(x, y, radius):
            dx = p.x - x
            dy = p.y - y
            d = dx * dx + dy * dy
            if d < best_d:
                best_d = d
                best = p
        return best

    def remove(self, pellet: Pellet):
        try:
            self.pellets.remove(pellet)
        except ValueError:
            pass
