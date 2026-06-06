"""Профиль игрока: ник, выбранный скин/цвет и палитра кастом-скина.

Хранится в profile.json."""

import json
from pathlib import Path

from skins import COLORS, SKIN_IDS, color_rgb
from maps import MAP_THEMES, theme_by_index

MAX_NICK_LEN = 14
MIN_CUSTOM = 2
MAX_CUSTOM = 6


class ProfileManager:
    DEFAULT_PATH = Path(__file__).parent / "profile.json"

    def __init__(self, filepath: Path | None = None):
        self.filepath = filepath or self.DEFAULT_PATH
        self.nickname = "Игрок"
        self.skin_index = 0
        self.color_index = 0
        # Палитра кастом-скина — список индексов в COLORS.
        self.custom_colors: list[int] = [0, 1, 4]
        self.custom_slot = 0  # активный слот при редактировании (не сохраняется)
        self.map_index = 0
        self.snow_on = True
        self.flicker_on = True
        self.load()

    def load(self):
        if not self.filepath.exists():
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            nick = str(data.get("nickname", self.nickname))[:MAX_NICK_LEN].strip()
            self.nickname = nick or "Игрок"
            self.skin_index = int(data.get("skin_index", 0)) % len(SKIN_IDS)
            self.color_index = int(data.get("color_index", 0)) % len(COLORS)
            cc = data.get("custom_colors")
            if isinstance(cc, list) and cc:
                cleaned = [int(i) % len(COLORS) for i in cc[:MAX_CUSTOM]]
                if len(cleaned) >= MIN_CUSTOM:
                    self.custom_colors = cleaned
            self.map_index = int(data.get("map_index", 0)) % len(MAP_THEMES)
            self.snow_on = bool(data.get("snow_on", True))
            self.flicker_on = bool(data.get("flicker_on", True))
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            pass

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "nickname": self.nickname,
                        "skin_index": self.skin_index,
                        "color_index": self.color_index,
                        "custom_colors": self.custom_colors,
                        "map_index": self.map_index,
                        "snow_on": self.snow_on,
                        "flicker_on": self.flicker_on,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError:
            pass

    @property
    def skin_id(self) -> str:
        return SKIN_IDS[self.skin_index % len(SKIN_IDS)]

    @property
    def color_rgb(self):
        return COLORS[self.color_index % len(COLORS)][1]

    @property
    def custom_palette(self) -> list[tuple]:
        return [color_rgb(i) for i in self.custom_colors]

    @property
    def map_theme(self) -> dict:
        return theme_by_index(self.map_index)

    def cycle_map(self, direction: int):
        self.map_index = (self.map_index + direction) % len(MAP_THEMES)
        self.save()

    def toggle_snow(self):
        self.snow_on = not self.snow_on
        self.save()

    def cycle_skin(self, direction: int):
        self.skin_index = (self.skin_index + direction) % len(SKIN_IDS)
        self.save()

    def cycle_color(self, direction: int):
        self.color_index = (self.color_index + direction) % len(COLORS)
        self.save()

    # --- Кастом-скин ---

    def cycle_custom_count(self, direction: int):
        n = len(self.custom_colors)
        new_n = max(MIN_CUSTOM, min(MAX_CUSTOM, n + direction))
        if new_n > n:
            self.custom_colors.append(self.custom_colors[-1])
        elif new_n < n:
            self.custom_colors = self.custom_colors[:new_n]
        self.custom_slot = min(self.custom_slot, len(self.custom_colors) - 1)
        self.save()

    def set_custom_slot(self, slot: int):
        if 0 <= slot < len(self.custom_colors):
            self.custom_slot = slot

    def cycle_custom_slot_color(self, direction: int):
        if not self.custom_colors:
            return
        slot = self.custom_slot % len(self.custom_colors)
        self.custom_colors[slot] = (self.custom_colors[slot] + direction) % len(COLORS)
        self.save()

    def set_nickname(self, name: str):
        self.nickname = (name[:MAX_NICK_LEN].strip()) or "Игрок"
        self.save()
