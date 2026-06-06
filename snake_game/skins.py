"""Скины и цвета змейки + утилиты цвета.

Скин определяет, как окрашивается каждый сегмент тела. Часть скинов
использует выбранный базовый цвет (solid/stripes/rings/...), часть —
многоцветные с фиксированной палитрой (rainbow/gradient/neon/...), и им
выбор одного статического цвета не нужен. Скин "custom" собирается игроком
из нескольких выбранных цветов."""

import colorsys
import math


def clamp(c) -> int:
    return max(0, min(255, int(c)))


def lighten(color, amount=0.4):
    return tuple(clamp(x + (255 - x) * amount) for x in color)


def darken(color, amount=0.4):
    return tuple(clamp(x * (1 - amount)) for x in color)


def lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(clamp(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (clamp(r * 255), clamp(g * 255), clamp(b * 255))


# Палитра базовых цветов (для скинов, использующих базовый цвет, и кастома).
COLORS = [
    ("Аметист", (170, 120, 255)),
    ("Бирюза", (80, 220, 210)),
    ("Коралл", (255, 120, 120)),
    ("Лайм", (150, 230, 90)),
    ("Золото", (255, 200, 80)),
    ("Небо", (110, 180, 255)),
    ("Роза", (255, 130, 200)),
    ("Мята", (130, 245, 180)),
    ("Огонёк", (255, 150, 70)),
    ("Уголь", (150, 160, 185)),
    ("Изумруд", (60, 200, 140)),
    ("Лаванда", (200, 170, 255)),
    ("Индиго", (110, 120, 230)),
    ("Вишня", (225, 70, 110)),
    ("Сталь", (175, 195, 215)),
    ("Закатный", (255, 170, 110)),
]

# (id, имя, использует ли выбранный базовый цвет).
SKINS = [
    ("solid", "Сплошной", True),
    ("stripes", "Полоски", True),
    ("rings", "Кольца", True),
    ("dual", "Двухцветный", True),
    ("spots", "Пятна", True),
    ("gradient", "Градиент", False),
    ("rainbow", "Радуга", False),
    ("neon", "Неон", False),
    ("fire", "Огонь", False),
    ("ice", "Лёд", False),
    ("sunset", "Закат", False),
    ("ocean", "Океан", False),
    ("aurora", "Аврора", False),
    ("candy", "Леденец", False),
    ("galaxy", "Галактика", False),
    ("custom", "Свой скин", False),
]

SKIN_IDS = [s[0] for s in SKINS]
_USES_COLOR = {s[0]: s[2] for s in SKINS}
_NAME = {s[0]: s[1] for s in SKINS}

# Скины со свечением (bloom) при отрисовке.
GLOW_SKINS = {"rainbow", "neon", "fire", "aurora", "galaxy"}

# Скины для ботов (всё, кроме кастома — у ботов нет своей палитры).
BOT_SKIN_IDS = [s for s in SKIN_IDS if s != "custom"]


def uses_base_color(skin_id: str) -> bool:
    return _USES_COLOR.get(skin_id, False)


def is_custom(skin_id: str) -> bool:
    return skin_id == "custom"


def skin_name(skin_id: str) -> str:
    return _NAME.get(skin_id, skin_id)


def color_name(index: int) -> str:
    return COLORS[index % len(COLORS)][0]


def color_rgb(index: int):
    return COLORS[index % len(COLORS)][1]


def segment_color(skin: str, base, idx: int, count: int, t: float, custom=None):
    """Базовый цвет сегмента idx из count (t — время для анимации)."""
    n = max(1, count)
    if skin == "stripes":
        return base if (idx % 6) < 3 else darken(base, 0.5)
    if skin == "rings":
        return base if (idx % 8) < 4 else lighten(base, 0.62)
    if skin == "dual":
        return base if (idx // 2) % 2 == 0 else darken(base, 0.5)
    if skin == "spots":
        return lighten(base, 0.65) if (idx % 5) == 0 else base
    if skin == "gradient":
        return lerp((175, 120, 255), (90, 230, 215), idx / n)
    if skin == "rainbow":
        return hsv(idx * 0.025 + t * 0.08, 0.85, 1.0)
    if skin == "neon":
        k = 0.5 + 0.5 * math.sin(idx * 0.4 + t * 1.5)
        return lerp((255, 70, 220), (70, 230, 255), k)
    if skin == "fire":
        return [(255, 70, 40), (255, 140, 40), (255, 205, 80)][idx % 3]
    if skin == "ice":
        return lerp((205, 232, 255), (110, 150, 245), idx / n)
    if skin == "sunset":
        pal = [(255, 160, 90), (255, 95, 140), (170, 90, 210)]
        return pal[(idx // 3) % 3]
    if skin == "ocean":
        return lerp((90, 240, 220), (60, 110, 230), 0.5 + 0.5 * math.sin(idx * 0.18))
    if skin == "aurora":
        return hsv(0.33 + 0.25 * (0.5 + 0.5 * math.sin(idx * 0.12 + t * 0.4)), 0.8, 1.0)
    if skin == "candy":
        return (255, 120, 190) if (idx % 4) < 2 else (255, 255, 255)
    if skin == "galaxy":
        if idx % 7 == 0:
            return (225, 215, 255)
        return lerp((70, 55, 150), (60, 110, 210), 0.5 + 0.5 * math.sin(idx * 0.1))
    if skin == "custom":
        pal = custom or [base]
        if not pal:
            pal = [base]
        return pal[(idx // 3) % len(pal)]
    return base  # solid


def head_color(skin: str, base, custom=None):
    if skin == "rainbow":
        return (245, 245, 255)
    if skin == "fire":
        return (255, 220, 120)
    if skin == "ice":
        return (225, 245, 255)
    if skin == "neon":
        return (255, 235, 255)
    if skin == "gradient":
        return lighten((175, 120, 255), 0.4)
    if skin in ("sunset", "candy"):
        return (255, 225, 235)
    if skin in ("ocean", "aurora", "galaxy"):
        return (225, 245, 255)
    if skin == "custom":
        pal = custom or [base]
        return lighten(pal[0] if pal else base, 0.42)
    return lighten(base, 0.42)
