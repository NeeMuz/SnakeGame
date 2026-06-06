"""Экраны меню с навигацией с клавиатуры."""

from enum import Enum


class MenuAction(Enum):
    NONE = "none"
    START = "start"
    SETTINGS = "settings"
    LEADERBOARD = "leaderboard"
    QUIT = "quit"
    BACK = "back"
    PLAY_AGAIN = "play_again"
    MAIN_MENU = "main_menu"
    SHOP = "shop"
    NICKNAME = "nickname"


class Menu:
    """Меню-список с навигацией W/S."""

    def __init__(self, title: str, items: list[tuple[str, MenuAction]]):
        self.title = title
        self.items = items
        self.selected = 0

    def move_up(self):
        if not self.items:
            return
        self.selected = (len(self.items) - 1 if self.selected < 0
                         else (self.selected - 1) % len(self.items))

    def move_down(self):
        if not self.items:
            return
        self.selected = (0 if self.selected < 0
                         else (self.selected + 1) % len(self.items))

    def confirm(self) -> MenuAction:
        if self.items and 0 <= self.selected < len(self.items):
            return self.items[self.selected][1]
        return MenuAction.NONE

    def get_labels(self) -> list[str]:
        return [label for label, _ in self.items]


def create_main_menu() -> Menu:
    return Menu(
        "ЗМЕЙКА.IO",
        [
            ("Играть", MenuAction.START),
            ("Магазин", MenuAction.SHOP),
            ("Выберите ваше имя", MenuAction.NICKNAME),
            ("Выход", MenuAction.QUIT),
        ],
    )


def create_game_over_menu() -> Menu:
    return Menu(
        "ИГРА ОКОНЧЕНА",
        [
            ("Играть снова", MenuAction.PLAY_AGAIN),
            ("Главное меню", MenuAction.MAIN_MENU),
        ],
    )


def create_leaderboard_menu() -> Menu:
    return Menu(
        "ТАБЛИЦА ЛИДЕРОВ",
        [
            ("Назад", MenuAction.BACK),
        ],
    )
