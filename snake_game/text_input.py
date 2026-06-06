"""Текстовое поле с кареткой, выделением и буфером обмена.

Чистая логика без pygame: координаты/шрифт передаются методам там, где
нужны для отрисовки и попадания мышью. Работа с системным буфером обмена
выполняется снаружи (game), здесь только операции над текстом."""


def _allowed(ch: str) -> bool:
    return ch.isalpha() or ch.isdigit() or ch in " -_"


class TextInput:
    def __init__(self, text: str = "", max_len: int = 14):
        self.max_len = max_len
        self.text = text[:max_len]
        self.caret = len(self.text)
        self.sel_anchor: int | None = None  # начало выделения; выделение = [min,max)

    # --- Выделение ---

    def has_selection(self) -> bool:
        return self.sel_anchor is not None and self.sel_anchor != self.caret

    def sel_range(self) -> tuple[int, int]:
        if self.sel_anchor is None:
            return self.caret, self.caret
        return (min(self.sel_anchor, self.caret), max(self.sel_anchor, self.caret))

    def selected_text(self) -> str:
        a, b = self.sel_range()
        return self.text[a:b]

    def delete_selection(self) -> bool:
        if not self.has_selection():
            self.sel_anchor = None
            return False
        a, b = self.sel_range()
        self.text = self.text[:a] + self.text[b:]
        self.caret = a
        self.sel_anchor = None
        return True

    def select_all(self):
        self.sel_anchor = 0
        self.caret = len(self.text)

    def clear_selection(self):
        self.sel_anchor = None

    # --- Редактирование ---

    def insert(self, s: str):
        s = "".join(c for c in s if _allowed(c))
        self.delete_selection()
        avail = self.max_len - len(self.text)
        if avail <= 0:
            return
        s = s[:avail]
        self.text = self.text[:self.caret] + s + self.text[self.caret:]
        self.caret += len(s)
        self.sel_anchor = None

    def backspace(self):
        if self.delete_selection():
            return
        if self.caret > 0:
            self.text = self.text[:self.caret - 1] + self.text[self.caret:]
            self.caret -= 1

    def delete(self):
        if self.delete_selection():
            return
        if self.caret < len(self.text):
            self.text = self.text[:self.caret] + self.text[self.caret + 1:]

    def delete_word_left(self):
        if self.delete_selection():
            return
        i = self.caret
        while i > 0 and self.text[i - 1] == " ":
            i -= 1
        while i > 0 and self.text[i - 1] != " ":
            i -= 1
        self.text = self.text[:i] + self.text[self.caret:]
        self.caret = i

    def delete_word_right(self):
        if self.delete_selection():
            return
        i = self.caret
        n = len(self.text)
        while i < n and self.text[i] == " ":
            i += 1
        while i < n and self.text[i] != " ":
            i += 1
        self.text = self.text[:self.caret] + self.text[i:]

    # --- Перемещение каретки ---

    def _set_caret(self, idx: int, extend: bool):
        idx = max(0, min(len(self.text), idx))
        if extend:
            if self.sel_anchor is None:
                self.sel_anchor = self.caret
        else:
            self.sel_anchor = None
        self.caret = idx

    def move(self, delta: int, extend: bool):
        self._set_caret(self.caret + delta, extend)

    def home(self, extend: bool):
        self._set_caret(0, extend)

    def end(self, extend: bool):
        self._set_caret(len(self.text), extend)

    def set_caret(self, idx: int, extend: bool = False):
        self._set_caret(idx, extend)

    # --- Попадание мышью ---

    def index_at_x(self, font, local_x: float) -> int:
        """Индекс каретки по локальной X-координате (0 = начало текста)."""
        best_i = 0
        best_d = abs(local_x)
        acc = 0
        for i in range(1, len(self.text) + 1):
            acc = font.size(self.text[:i])[0]
            d = abs(local_x - acc)
            if d < best_d:
                best_d = d
                best_i = i
        return best_i
