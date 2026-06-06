"""Игровой мир: змейки (игрок + боты), еда, границы и столкновения.

Мир круглый с центром в (0, 0). Столкновения и поиск соседей ускорены
пространственной сеткой сегментов, чтобы не было O(n^2) по всем точкам
всех змей."""

import math
import random

from bot import BotController, random_bot_name
from food import FoodField
from snake import Snake
from skins import BOT_SKIN_IDS, COLORS


SEG_CELL = 90.0

# Доля «толстых червей» среди ботов и шанс при респауне.
FAT_CHANCE = 0.12


class World:
    def __init__(self, radius: float, bot_count: int,
                 player_skin: str = "solid", player_color=None, player_name: str = "Вы",
                 player_custom=None):
        self.radius = float(radius)
        self.bot_count = bot_count
        self.food = FoodField(self.radius)

        self.used_names: set[str] = set()
        self.snakes: list[Snake] = []
        self.bots: list[tuple[Snake, BotController]] = []

        # Игрок стартует в центре со своим скином/цветом/ником.
        self.player = Snake(0.0, 0.0, random.uniform(-math.pi, math.pi),
                            is_player=True, name=player_name or "Вы",
                            skin=player_skin, color=player_color,
                            custom_colors=player_custom)
        self.snakes.append(self.player)
        self.player_dead = False
        self.death_ranking: list[tuple] = []

        for i in range(bot_count):
            self._spawn_bot(initial=True)

        self._seg_grid: dict[tuple[int, int], list] = {}
        self._rebuild_segment_grid()

    # --- Создание ботов ---

    def _free_position(self) -> tuple[float, float]:
        for _ in range(30):
            r = self.radius * 0.85 * math.sqrt(random.random())
            a = random.uniform(0, math.tau)
            x, y = r * math.cos(a), r * math.sin(a)
            ok = True
            for s in self.snakes:
                if math.hypot(s.x - x, s.y - y) < 260:
                    ok = False
                    break
            if ok:
                return x, y
        return x, y

    def _spawn_bot(self, initial: bool = False):
        x, y = self._free_position()
        color = random.choice(COLORS)[1]
        skin = random.choice(BOT_SKIN_IDS)
        name = random_bot_name(self.used_names)
        self.used_names.add(name)

        fat = random.random() < FAT_CHANCE
        if fat:
            mass = random.uniform(140, 240) if initial else random.uniform(110, 180)
            name = "Толстяк " + name
        else:
            mass = random.uniform(12, 45) if initial else random.uniform(12, 22)

        snake = Snake(x, y, random.uniform(-math.pi, math.pi),
                      mass=mass, color=color, name=name, skin=skin, fat=fat)
        # Толстяки медлительны и неагрессивны; обычные — часто агрессивны.
        aggressive = (not fat) and random.random() < 0.3
        controller = BotController(aggressive=aggressive)
        self.snakes.append(snake)
        self.bots.append((snake, controller))

    # --- Пространственные запросы ---

    def _key(self, x: float, y: float) -> tuple[int, int]:
        return (int(math.floor(x / SEG_CELL)), int(math.floor(y / SEG_CELL)))

    def _rebuild_segment_grid(self):
        grid: dict[tuple[int, int], list] = {}
        for s in self.snakes:
            if not s.alive:
                continue
            sr = s.radius
            for (sx, sy) in s.segments:
                grid.setdefault(self._key(sx, sy), []).append((sx, sy, sr, s))
        self._seg_grid = grid

    def nearby_segments(self, x: float, y: float, radius: float, exclude: Snake):
        cx, cy = self._key(x, y)
        span = int(radius / SEG_CELL) + 1
        out = []
        for gx in range(cx - span, cx + span + 1):
            for gy in range(cy - span, cy + span + 1):
                bucket = self._seg_grid.get((gx, gy))
                if not bucket:
                    continue
                for entry in bucket:
                    if entry[3] is not exclude:
                        out.append(entry)
        return out

    def nearest_pellet(self, x: float, y: float, radius: float):
        return self.food.nearest(x, y, radius)

    # --- Обновление ---

    def update(self, dt: float, player_target: tuple[float, float] | None, player_boost: bool):
        self.food.maintain(dt)

        # 1) Управление игроком.
        if self.player.alive:
            if player_target is not None:
                self.player.steer_towards(*player_target)
            self.player.boosting = player_boost

        # 2) ИИ ботов (использует сетку с прошлого кадра).
        for snake, controller in self.bots:
            controller.update(snake, self, dt)

        # 3) Движение всех змей.
        for s in self.snakes:
            s.update(dt)

        # 4) Шарики, выроненные при ускорении.
        for s in self.snakes:
            if s.pending_drops:
                for (dx, dy, val, col) in s.pending_drops:
                    self.food.add(dx, dy, val, col)
                s.pending_drops.clear()

        # 5) Поедание еды.
        eaten = []
        for s in self.snakes:
            if not s.alive:
                continue
            reach = s.radius + 14
            for p in self.food.query(s.x, s.y, reach):
                if math.hypot(p.x - s.x, p.y - s.y) < s.radius + p.radius:
                    s.grow(p.value)
                    eaten.append(p)
        if eaten:
            for p in set(eaten):
                self.food.remove(p)

        # 6) Сетка сегментов после движения — для столкновений.
        self._rebuild_segment_grid()

        # 7) Столкновения: голова о чужое тело или граница мира.
        to_die = []
        for s in self.snakes:
            if not s.alive:
                continue
            if math.hypot(s.x, s.y) > self.radius - s.radius * 0.5:
                to_die.append(s)
                continue
            if s.spawn_protect > 0:
                continue
            hit = False
            for (sx, sy, sr, other) in self.nearby_segments(s.x, s.y, s.radius + 40, s):
                if math.hypot(sx - s.x, sy - s.y) < sr + s.radius * 0.5:
                    hit = True
                    break
            if hit:
                to_die.append(s)

        # 8) Обработка смертей.
        for s in to_die:
            if not s.alive:
                continue
            if s is self.player:
                # Снимок живой таблицы в момент гибели игрока (включая его).
                self.death_ranking = self._ranking_snapshot()
                self.player_dead = True
            s.die()
            for (dx, dy, val, col) in s.scatter_food():
                self.food.add(dx, dy, val, col)

        if to_die:
            # Удаляем мёртвых ботов и пополняем популяцию.
            alive_bots = []
            removed = 0
            for snake, controller in self.bots:
                if snake.alive:
                    alive_bots.append((snake, controller))
                else:
                    removed += 1
                    self.used_names.discard(snake.name)
            self.bots = alive_bots
            self.snakes = [s for s in self.snakes if s.alive or s is self.player]
            for _ in range(removed):
                self._spawn_bot()
            # Обновляем сетку сегментов после изменений состава.
            self._rebuild_segment_grid()

        # Сетку еды перестраиваем каждый кадр: она отражает актуальный
        # список пеллетов для поедания и ИИ на следующем кадре.
        self.food.rebuild_grid()

    # --- Таблица лидеров (живые змеи) ---

    def leaderboard(self, top: int = 5):
        ranked = sorted(
            [s for s in self.snakes if s.alive],
            key=lambda s: s.mass,
            reverse=True,
        )
        return ranked[:top]

    def _ranking_snapshot(self, top: int = 5):
        """Снимок рейтинга (имя, счёт, это_игрок) в текущий момент."""
        ranked = sorted(self.snakes, key=lambda s: s.mass, reverse=True)
        return [(s.name, int(s.mass), s.is_player) for s in ranked[:top]]
