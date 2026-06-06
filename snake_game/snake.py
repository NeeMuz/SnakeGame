"""Непрерывная змейка в стиле slither.io.

Голова движется с постоянной скоростью в направлении heading, плавно
поворачивая к target_heading. Тело — это след из точек (path), вдоль
которого с равным шагом расставлены сегменты-кружки. Те же правила
используются и для игрока, и для ботов (бот лишь задаёт target_heading
и boosting через AI-контроллер)."""

import math
import random

from skins import head_color as skin_head_color


BASE_RADIUS = 7.0
MAX_RADIUS = 26.0
FAT_MAX_RADIUS = 42.0
BASE_SPEED = 165.0
BOOST_SPEED = 300.0
TURN_RATE = 4.2          # радиан/сек — базовая скорость поворота
START_MASS = 12.0
MIN_MASS = 6.0
BOOST_MIN_MASS = 14.0    # ниже этой массы ускоряться нельзя
BOOST_DRAIN = 9.0        # масса/сек при ускорении
DROP_MASS = 2.0          # сколько массы накопить, чтобы выронить шарик
SPACING_FACTOR = 0.52
MIN_SEGMENTS = 10
SEG_PER_MASS = 0.55
MAX_SEGMENTS = 240


class Snake:
    def __init__(self, x: float, y: float, heading: float, mass: float = START_MASS,
                 color=None, is_player: bool = False, name: str = "",
                 skin: str = "solid", fat: bool = False, custom_colors=None):
        self.x = float(x)
        self.y = float(y)
        self.heading = float(heading)
        self.target_heading = float(heading)
        self.mass = float(mass)
        self.is_player = is_player
        self.name = name
        self.alive = True
        self.boosting = False

        self.skin = skin
        self.base_color = color or (120, 230, 220)
        self.custom_colors = list(custom_colors) if custom_colors else None
        # color сохраняем для совместимости (мини-карта, шарики, свотчи).
        if self.custom_colors:
            self.color = self.custom_colors[0]
        else:
            self.color = self.base_color
        self.head_color = skin_head_color(skin, self.base_color, self.custom_colors)

        # «Толстый червь»: крупнее, медленнее поворачивает, роняет больше еды.
        self.fat = fat
        self.turn_mult = 0.5 if fat else 1.0
        self.speed_mult = 0.9 if fat else 1.0
        self.scatter_mult = 2.6 if fat else 1.0
        self.max_radius = FAT_MAX_RADIUS if fat else MAX_RADIUS

        self.radius = self._radius_for_mass()
        self.speed = BASE_SPEED
        self._drain_accum = 0.0
        self.spawn_protect = 1.2  # секунды неуязвимости после появления
        self.pending_drops: list[tuple[float, float, float, tuple]] = []

        # Стартовый след позади головы, чтобы змейка сразу имела длину.
        self.points: list[list[float]] = []
        back = self._target_length() + 40.0
        step = 4.0
        n = int(back / step)
        for i in range(n, -1, -1):
            d = i * step
            self.points.append([self.x - math.cos(heading) * d,
                                 self.y - math.sin(heading) * d])
        self.segments: list[tuple[float, float]] = []
        self._rebuild_segments()

    # --- Производные величины ---

    def _radius_for_mass(self) -> float:
        return min(self.max_radius, BASE_RADIUS + math.sqrt(max(0.0, self.mass)) * 0.95)

    def _segment_count(self) -> int:
        return min(MAX_SEGMENTS, int(MIN_SEGMENTS + self.mass * SEG_PER_MASS))

    def _spacing(self) -> float:
        return max(2.0, self.radius * SPACING_FACTOR)

    def _target_length(self) -> float:
        return self._segment_count() * self._spacing()

    @property
    def score(self) -> int:
        return int(self.mass)

    @property
    def head(self) -> tuple[float, float]:
        return (self.x, self.y)

    # --- Управление ---

    def steer_towards(self, tx: float, ty: float):
        """Задаёт желаемое направление к точке (tx, ty)."""
        self.target_heading = math.atan2(ty - self.y, tx - self.x)

    def set_target_heading(self, angle: float):
        self.target_heading = angle

    # --- Обновление ---

    def update(self, dt: float):
        if not self.alive:
            return

        if self.spawn_protect > 0:
            self.spawn_protect -= dt

        # Плавный поворот к целевому направлению.
        diff = (self.target_heading - self.heading + math.pi) % (2 * math.pi) - math.pi
        turn = TURN_RATE * (BASE_RADIUS / self.radius) ** 0.5 * self.turn_mult * dt
        if diff > turn:
            diff = turn
        elif diff < -turn:
            diff = -turn
        self.heading += diff

        # Ускорение тратит массу и роняет шарики.
        boosting = self.boosting and self.mass > BOOST_MIN_MASS
        if boosting:
            self.speed = BOOST_SPEED * self.speed_mult
            drained = BOOST_DRAIN * dt
            self.mass -= drained
            self._drain_accum += drained
            if self._drain_accum >= DROP_MASS:
                self._drain_accum -= DROP_MASS
                if self.segments:
                    tx, ty = self.segments[-1]
                    self.pending_drops.append((tx, ty, DROP_MASS * 0.6, self.color))
        else:
            self.speed = BASE_SPEED * self.speed_mult

        # Движение головы.
        self.x += math.cos(self.heading) * self.speed * dt
        self.y += math.sin(self.heading) * self.speed * dt
        self.points.append([self.x, self.y])

        self.radius = self._radius_for_mass()
        self._rebuild_segments()

    def _rebuild_segments(self):
        pts = self.points
        if len(pts) == 1:
            self.segments = [(pts[0][0], pts[0][1])]
            return

        seg_count = self._segment_count()
        spacing = self._spacing()

        segs = [(pts[-1][0], pts[-1][1])]  # сегмент-голова
        acc = 0.0
        next_at = spacing
        i = len(pts) - 1
        while i > 0 and len(segs) < seg_count:
            x1, y1 = pts[i]
            x0, y0 = pts[i - 1]
            dx, dy = x0 - x1, y0 - y1
            d = math.hypot(dx, dy)
            if d <= 1e-9:
                i -= 1
                continue
            while next_at <= acc + d and len(segs) < seg_count:
                r = (next_at - acc) / d
                segs.append((x1 + dx * r, y1 + dy * r))
                next_at += spacing
            acc += d
            i -= 1

        self.segments = segs

        # Подрезаем лишние точки следа (оставляем небольшой запас).
        if i > 2:
            del self.points[: i - 2]

    def grow(self, value: float):
        self.mass += value

    def die(self):
        self.alive = False

    def scatter_food(self):
        """Возвращает список (x, y, value, color) — еда из тела погибшей змейки."""
        drops = []
        if not self.segments:
            return drops
        total = max(1.0, self.mass * 0.55 * self.scatter_mult)
        # Распределяем массу по части сегментов (через один), чтобы не было кучи.
        chosen = self.segments[::2] or self.segments
        per = total / len(chosen)
        for (sx, sy) in chosen:
            jx = sx + random.uniform(-self.radius, self.radius)
            jy = sy + random.uniform(-self.radius, self.radius)
            drops.append((jx, jy, per, self.color))
        return drops
