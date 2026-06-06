"""ИИ-контроллер для змеек-ботов (компетентное поведение).

Бот не хранит позицию — он управляет обычным Snake, выставляя ему
target_heading и boosting. Поведение: блуждание, поиск ближайшей еды,
уход от чужих тел и границы мира, иногда агрессивная подрезка игрока.
Боты намеренно умные: реагируют сразу, целятся точно — но обыгрываемые."""

import math
import random


BOT_NAMES = [
    "Питон", "Кобра", "Гадюка", "Уж", "Анаконда", "Мамба", "Эфа",
    "Полоз", "Аспид", "Гюрза", "Удав", "Медянка", "Тайпан", "Щитомордник",
    "Веретеница", "Стрела", "Вьюн", "Зигзаг", "Шнурок", "Спираль",
    "Турбо", "Хищник", "Молния", "Призрак", "Вираж",
]


def random_bot_name(used: set) -> str:
    pool = [n for n in BOT_NAMES if n not in used]
    if not pool:
        return f"Бот-{random.randint(10, 99)}"
    return random.choice(pool)


def _ang_diff(a, b):
    d = (a - b + math.pi) % math.tau - math.pi
    return d


class BotController:
    """Бот движется к дальним путевым точкам и сворачивает к еде по пути.

    Навигация по waypoint'ам делает движение целеустремлённым и прямым —
    змейки не наматывают круги на месте. Анти-залипание перевыбирает цель,
    если бот долго почти не смещается."""

    def __init__(self, aggressive: bool = False):
        self.aggressive = aggressive
        self.vision = random.uniform(300, 520)
        self.boost_timer = 0.0
        self.waypoint: tuple[float, float] | None = None
        self.waypoint_timer = 0.0
        self.last_pos: tuple[float, float] | None = None
        self.stuck_timer = 0.0

    def _new_waypoint(self, x, y, world):
        # Дальняя точка внутри мира, желательно подальше от текущей позиции.
        r_max = world.radius * 0.8
        for _ in range(4):
            ang = random.uniform(-math.pi, math.pi)
            dist = random.uniform(r_max * 0.45, r_max)
            tx = math.cos(ang) * dist
            ty = math.sin(ang) * dist
            if math.hypot(tx - x, ty - y) > 300:
                break
        self.waypoint = (tx, ty)
        self.waypoint_timer = random.uniform(4.0, 8.0)

    def update(self, snake, world, dt: float):
        if not snake.alive:
            return

        x, y = snake.x, snake.y
        snake.boosting = False

        # 1) Избегание границы мира (центр в 0,0).
        dist_c = math.hypot(x, y)
        margin = world.radius - (snake.radius + 150)
        if dist_c > margin:
            snake.set_target_heading(math.atan2(-y, -x))
            self.waypoint = None  # после границы выберем новую цель
            return

        # 2) Избегание чужих тел: смотрим вперёд и отталкиваемся.
        look = snake.radius * 3 + snake.speed * 0.45
        fx = x + math.cos(snake.heading) * look
        fy = y + math.sin(snake.heading) * look
        avoid_x = avoid_y = 0.0
        threat = False
        for (sx, sy, sr, other) in world.nearby_segments(x, y, look + snake.radius + 40, snake):
            dh = math.hypot(sx - x, sy - y)
            df = math.hypot(sx - fx, sy - fy)
            danger = sr + snake.radius + 26
            if dh < danger * 1.6 or df < danger:
                threat = True
                wgt = 1.0 / max(1.0, min(dh, df))
                avoid_x += (x - sx) * wgt
                avoid_y += (y - sy) * wgt
        if threat and (avoid_x or avoid_y):
            snake.set_target_heading(math.atan2(avoid_y, avoid_x))
            if snake.mass > 30 and random.random() < 0.04:
                snake.boosting = True
            return

        # 3) Агрессия: подрезать игрока, заходя ему в голову.
        if self.aggressive and world.player and world.player.alive:
            px, py = world.player.x, world.player.y
            if math.hypot(px - x, py - y) < self.vision * 1.2:
                lead = 60
                tx = px + math.cos(world.player.heading) * lead
                ty = py + math.sin(world.player.heading) * lead
                snake.set_target_heading(math.atan2(ty - y, tx - x))
                self.boost_timer -= dt
                if self.boost_timer <= 0 and snake.mass > 40:
                    snake.boosting = random.random() < 0.5
                    self.boost_timer = random.uniform(0.6, 1.6)
                return

        # 4) Навигация по waypoint'ам + сворачивание к еде по курсу.
        self.waypoint_timer -= dt
        if (self.waypoint is None or self.waypoint_timer <= 0
                or math.hypot(self.waypoint[0] - x, self.waypoint[1] - y) < 140):
            self._new_waypoint(x, y, world)

        tx, ty = self.waypoint
        pellet = world.nearest_pellet(x, y, self.vision)
        if pellet is not None:
            ang_food = math.atan2(pellet.y - y, pellet.x - x)
            # Сворачиваем к еде, только если она примерно по курсу (без разворотов).
            if abs(_ang_diff(ang_food, snake.heading)) < 1.5:
                tx, ty = pellet.x, pellet.y

        # 5) Анти-залипание: если почти не двигаемся — новая цель.
        if self.last_pos is not None:
            moved = math.hypot(x - self.last_pos[0], y - self.last_pos[1])
            if moved < snake.speed * dt * 0.35:
                self.stuck_timer += dt
                if self.stuck_timer > 1.2:
                    self._new_waypoint(x, y, world)
                    self.stuck_timer = 0.0
            else:
                self.stuck_timer = 0.0
        self.last_pos = (x, y)

        snake.set_target_heading(math.atan2(ty - y, tx - x))
