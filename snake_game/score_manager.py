"""Таблица рекордов (TOP-5) с именами игроков, хранится в scores.json.

Формат: {"scores": [{"name": str, "score": int}, ...]}.
Поддерживается старый формат (список чисел) для обратной совместимости."""

import json
from pathlib import Path


# Затравочные «фейковые» игроки, чтобы таблица всегда выглядела живой.
# Реальные результаты игрока сортируются в общий список наравне с ними.
FAKE_PLAYERS = [
    ("ЗмеиныйКороль", 4820),
    ("Vortex", 4310),
    ("Аспид228", 3980),
    ("NeonViper", 3655),
    ("Гадюка_PRO", 3320),
    ("Mamba", 3040),
    ("ТихийУдав", 2780),
    ("Cobra_Kai", 2510),
    ("Питончик", 2275),
    ("GhostSnake", 2030),
    ("Анаконда", 1840),
    ("Slytherin", 1615),
    ("Веретено", 1390),
    ("Зигзаг", 1180),
    ("Малыш_Уж", 970),
]


class ScoreManager:
    MAX_SCORES = 10
    DEFAULT_PATH = Path(__file__).parent / "scores.json"

    def __init__(self, filepath: Path | None = None):
        self.filepath = filepath or self.DEFAULT_PATH
        self.entries: list[dict] = []
        self.load()

    def load(self):
        self.entries = []
        if not self.filepath.exists():
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("scores", [])
            entries = []
            for item in raw:
                if isinstance(item, dict):
                    name = str(item.get("name", "Игрок")) or "Игрок"
                    score = int(item.get("score", 0))
                elif isinstance(item, (int, float)):
                    # Старый формат — только число.
                    name = "Игрок"
                    score = int(item)
                else:
                    continue
                entries.append({"name": name, "score": score})
            self.entries = self._sorted(entries)
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            self.entries = []

    def _sorted(self, entries: list[dict]) -> list[dict]:
        return sorted(entries, key=lambda e: e["score"], reverse=True)[: self.MAX_SCORES]

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"scores": self.entries}, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def add_score(self, score: int, name: str = "Игрок") -> bool:
        """Добавляет результат и хранит TOP-5. True, если попал в таблицу."""
        if score <= 0:
            return False
        entry = {"name": (name or "Игрок")[:14], "score": int(score)}
        self.entries.append(entry)
        self.entries = self._sorted(self.entries)
        self.save()
        return entry in self.entries

    def get_top(self, n: int = 10) -> list[tuple[str, int]]:
        """Реальные результаты, слитые с фейковыми игроками и отсортированные."""
        merged = [(e["name"], e["score"]) for e in self.entries] + list(FAKE_PLAYERS)
        merged.sort(key=lambda e: e[1], reverse=True)
        return merged[:n]

    def best_score(self) -> int:
        """Лучший РЕАЛЬНЫЙ результат игрока (без фейковых)."""
        return self.entries[0]["score"] if self.entries else 0
