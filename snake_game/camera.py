"""Камера: преобразование мировых координат в экранные и обратно.

Камера плавно следует за головой игрока и слегка отдаляется по мере
роста змейки, чтобы держать обзор."""


class Camera:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.cx = 0.0
        self.cy = 0.0
        self.zoom = 1.0
        self._target_zoom = 1.0

    def resize(self, width: int, height: int):
        self.width = width
        self.height = height

    def snap_to(self, x: float, y: float):
        self.cx = x
        self.cy = y

    def update(self, target_x: float, target_y: float, player_radius: float, dt: float):
        # Плавное следование за головой.
        follow = min(1.0, dt * 6.0)
        self.cx += (target_x - self.cx) * follow
        self.cy += (target_y - self.cy) * follow

        # Чем толще змейка, тем сильнее отдаляем камеру (в пределах).
        self._target_zoom = max(0.62, min(1.15, 1.15 - (player_radius - 7.0) * 0.022))
        self.zoom += (self._target_zoom - self.zoom) * min(1.0, dt * 3.0)

    def to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return (
            (wx - self.cx) * self.zoom + self.width / 2,
            (wy - self.cy) * self.zoom + self.height / 2,
        )

    def to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return (
            (sx - self.width / 2) / self.zoom + self.cx,
            (sy - self.height / 2) / self.zoom + self.cy,
        )

    def visible_bounds(self, pad: float = 60.0) -> tuple[float, float, float, float]:
        """Видимая область в мировых координатах (с запасом для отсечения)."""
        half_w = self.width / 2 / self.zoom + pad
        half_h = self.height / 2 / self.zoom + pad
        return (self.cx - half_w, self.cy - half_h, self.cx + half_w, self.cy + half_h)
