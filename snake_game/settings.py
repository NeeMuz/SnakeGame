"""Базовые параметры режима: фиксированные 16 ботов и размер мира."""

# Размеры окна по умолчанию и минимальные ограничения.
DEFAULT_WIDTH = 960
DEFAULT_HEIGHT = 720
MIN_WIDTH = 560
MIN_HEIGHT = 480

# Частота отрисовки/симуляции.
FPS = 60

# Фиксированные параметры мира (настроек больше нет).
BOT_COUNT = 16
WORLD_RADIUS = 2800


class Settings:
    """Хранит фиксированные параметры мира."""

    @property
    def bot_count(self) -> int:
        return BOT_COUNT

    @property
    def world_radius(self) -> int:
        return WORLD_RADIUS
