"""Темы карт (арен): цвета фона, сетки и границы мира.

Используются при игре; выбор сохраняется в profile.json."""

MAP_THEMES = [
    {
        "id": "classic",
        "name": "Аметист",
        "arena_top": (16, 10, 30),
        "arena_bottom": (32, 18, 56),
        "grid": (120, 90, 180),
        "boundary": (236, 120, 150),
    },
    {
        "id": "neon",
        "name": "Неон",
        "arena_top": (6, 16, 20),
        "arena_bottom": (10, 30, 36),
        "grid": (60, 220, 200),
        "boundary": (80, 255, 180),
    },
    {
        "id": "lava",
        "name": "Лава",
        "arena_top": (24, 8, 8),
        "arena_bottom": (52, 16, 12),
        "grid": (190, 90, 60),
        "boundary": (255, 140, 60),
    },
    {
        "id": "ocean",
        "name": "Океан",
        "arena_top": (6, 14, 32),
        "arena_bottom": (10, 26, 58),
        "grid": (70, 130, 220),
        "boundary": (90, 200, 255),
    },
    {
        "id": "forest",
        "name": "Лес",
        "arena_top": (8, 20, 14),
        "arena_bottom": (14, 36, 24),
        "grid": (90, 180, 110),
        "boundary": (150, 230, 120),
    },
    {
        "id": "void",
        "name": "Пустота",
        "arena_top": (10, 10, 14),
        "arena_bottom": (24, 24, 32),
        "grid": (130, 130, 150),
        "boundary": (210, 210, 230),
    },
]

MAP_IDS = [m["id"] for m in MAP_THEMES]


def theme_by_index(index: int) -> dict:
    return MAP_THEMES[index % len(MAP_THEMES)]
