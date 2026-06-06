"""Главный игровой цикл и машина состояний (slither.io с ботами).

Управление в игре — только мышь: курсор задаёт направление, левая кнопка
мыши — ускорение. Клавиатура используется для ввода имени и ESC."""

from enum import Enum

import pygame

from background import CityBackground
from camera import Camera
from effects import Snow, make_gradient
from menu import (
    Menu,
    MenuAction,
    create_game_over_menu,
    create_leaderboard_menu,
    create_main_menu,
)
from player_profile import MAX_NICK_LEN, ProfileManager
from score_manager import ScoreManager
from settings import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    FPS,
    MIN_HEIGHT,
    MIN_WIDTH,
    Settings,
)
from skins import is_custom
from text_input import TextInput
from ui_manager import UIManager
from world import World


class GameState(Enum):
    MENU = "menu"
    SHOP = "shop"
    NICKNAME = "nickname"
    PLAYING = "playing"
    GAME_OVER = "game_over"
    LEADERBOARD = "leaderboard"


class Game:
    def __init__(self):
        pygame.init()
        self.settings = Settings()
        self.score_manager = ScoreManager()
        self.profile = ProfileManager()
        self.state = GameState.MENU
        self.running = True

        self.main_menu = create_main_menu()
        self.game_over_menu = create_game_over_menu()
        self.leaderboard_menu = create_leaderboard_menu()
        self._leaderboard_return = GameState.MENU

        self.shop_sel = 0
        self.nick_sel = 0
        self.nick_input = TextInput(self.profile.nickname, MAX_NICK_LEN)
        self.nick_dragging = False
        self._nick_last_click = 0
        self._clip_fallback = ""

        self.world: World | None = None
        self.score = 0
        self.last_score_high = False
        self.death_snapshot: list[tuple] = []

        self.screen = pygame.display.set_mode((DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Змейка.io")
        try:
            pygame.scrap.init()
        except Exception:
            pass

        self.city = CityBackground(*self.screen.get_size())
        self.snow = Snow(*self.screen.get_size())
        self.ui = UIManager(self.screen)
        self.camera = Camera(*self.screen.get_size())
        self.clock = pygame.time.Clock()

        self.current_theme = self.profile.map_theme
        self.ui.set_theme(self.current_theme)
        self.arena_bg = make_gradient(self.screen.get_size(),
                                      self.current_theme["arena_top"],
                                      self.current_theme["arena_bottom"])

    def _on_resize(self, width: int, height: int):
        width = max(MIN_WIDTH, width)
        height = max(MIN_HEIGHT, height)
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        self.arena_bg = make_gradient((width, height),
                                      self.current_theme["arena_top"],
                                      self.current_theme["arena_bottom"])
        self.city.resize(width, height)
        self.snow.resize(width, height)
        self.ui.resize(self.screen)
        self.camera.resize(width, height)

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    self._on_resize(event.w, event.h)
                else:
                    self._handle_event(event)

            # Снег всегда обновляется (экранные координаты) с плавным fade
            # к цели включения; так он естественно падает и в игре.
            self.snow.set_active(self.profile.snow_on)
            self.snow.update(dt)

            if self.state == GameState.PLAYING:
                self._update_playing(dt)

            self._draw()
            pygame.display.flip()

        pygame.quit()

    # --- Маршрутизация событий ---

    def _handle_event(self, event: pygame.event.Event):
        if self.state == GameState.MENU:
            self._handle_menu_state(event, self.main_menu)
        elif self.state == GameState.SHOP:
            self._handle_shop(event)
        elif self.state == GameState.NICKNAME:
            self._handle_nickname(event)
        elif self.state == GameState.PLAYING:
            self._handle_playing_input(event)
        elif self.state == GameState.GAME_OVER:
            self._handle_menu_state(event, self.game_over_menu)
        elif self.state == GameState.LEADERBOARD:
            self._handle_menu_state(event, self.leaderboard_menu)

    # --- Меню (мышь + клавиатура) ---

    def _menu_index_at(self, pos):
        for i, rect in enumerate(self.ui.menu_item_rects):
            if rect.collidepoint(pos):
                return i
        return None

    def _handle_menu_state(self, event: pygame.event.Event, menu: Menu):
        # Тумблеры снега/мерцания в лобби (только в главном меню).
        if (menu is self.main_menu and event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1):
            tg = self.ui.lobby_toggles
            if tg.get("snow") and tg["snow"].collidepoint(event.pos):
                self.profile.toggle_snow()
                return
            if tg.get("flicker") and tg["flicker"].collidepoint(event.pos):
                self.profile.flicker_on = not self.profile.flicker_on
                self.profile.save()
                return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.state == GameState.LEADERBOARD:
                self.state = self._leaderboard_return
            elif self.state == GameState.GAME_OVER:
                self.state = GameState.MENU
                self.main_menu.selected = 0
            return

        if event.type == pygame.MOUSEMOTION:
            # Подсветка следует за курсором и сбрасывается над пустотой.
            idx = self._menu_index_at(event.pos)
            menu.selected = idx if idx is not None else -1
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            idx = self._menu_index_at(event.pos)
            if idx is not None:
                menu.selected = idx
                self._process_menu_action(menu.confirm())
            return

        if self.ui.handle_menu_input(event, menu):
            self._process_menu_action(menu.confirm())

    # --- Магазин ---

    def _shop_hover(self, pos):
        for key in self.ui.shop_order:
            rect = self.ui.shop_rects.get(key)
            if rect and rect.collidepoint(pos):
                return self.ui.shop_order.index(key)
        return -1

    def _shop_cycle(self, key: str, direction: int):
        if key == "skin":
            self.profile.cycle_skin(direction)
            self.shop_sel = 0
        elif key == "color":
            self.profile.cycle_color(direction)
        elif key == "count":
            self.profile.cycle_custom_count(direction)
        elif key == "palette":
            self.profile.cycle_custom_slot_color(direction)
        elif key == "map":
            self.profile.cycle_map(direction)
        elif key == "snow":
            self.profile.toggle_snow()

    def _handle_shop(self, event: pygame.event.Event):
        order = self.ui.shop_order
        r = self.ui.shop_rects
        n = max(1, len(order))

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = GameState.MENU
                self.main_menu.selected = 0
            elif event.key in (pygame.K_w, pygame.K_UP):
                self.shop_sel = (len(order) - 1) if self.shop_sel < 0 else (self.shop_sel - 1) % n
            elif event.key in (pygame.K_s, pygame.K_DOWN):
                self.shop_sel = 0 if self.shop_sel < 0 else (self.shop_sel + 1) % n
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                if 0 <= self.shop_sel < len(order):
                    self._shop_cycle(order[self.shop_sel], -1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                if 0 <= self.shop_sel < len(order):
                    self._shop_cycle(order[self.shop_sel], 1)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if 0 <= self.shop_sel < len(order):
                    key = order[self.shop_sel]
                    if key == "play":
                        self._start_game()
                    elif key == "back":
                        self.state = GameState.MENU
                        self.main_menu.selected = 0
            return

        if event.type == pygame.MOUSEMOTION:
            self.shop_sel = self._shop_hover(event.pos)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key in ("skin", "color", "count", "palette", "map", "snow"):
                if r.get(key + "_l") and r[key + "_l"].collidepoint(event.pos):
                    self._shop_cycle(key, -1)
                    return
                if r.get(key + "_r") and r[key + "_r"].collidepoint(event.pos):
                    self._shop_cycle(key, 1)
                    return
            if r.get("snow") and r["snow"].collidepoint(event.pos):
                self.profile.toggle_snow()
                return
            for i, sw in enumerate(r.get("palette_swatches", [])):
                if sw.collidepoint(event.pos):
                    self.profile.set_custom_slot(i)
                    return
            if r.get("play") and r["play"].collidepoint(event.pos):
                self._start_game()
            elif r.get("back") and r["back"].collidepoint(event.pos):
                self.state = GameState.MENU
                self.main_menu.selected = 0

    # --- Ввод имени ---

    def _clip_get(self) -> str:
        try:
            data = pygame.scrap.get(pygame.SCRAP_TEXT)
            if data:
                return data.decode("utf-8", "ignore").replace("\x00", "")
        except Exception:
            pass
        return self._clip_fallback

    def _clip_set(self, s: str):
        self._clip_fallback = s
        try:
            pygame.scrap.put(pygame.SCRAP_TEXT, s.encode("utf-8"))
        except Exception:
            pass

    def _handle_nickname(self, event: pygame.event.Event):
        ti = self.nick_input
        font = self.ui.font_large

        if event.type == pygame.TEXTINPUT:
            ti.insert(event.text)
            return

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = mods & pygame.KMOD_CTRL
            shift = mods & pygame.KMOD_SHIFT
            if ctrl:
                if event.key == pygame.K_a:
                    ti.select_all()
                elif event.key == pygame.K_c:
                    self._clip_set(ti.selected_text())
                elif event.key == pygame.K_x:
                    self._clip_set(ti.selected_text())
                    ti.delete_selection()
                elif event.key == pygame.K_v:
                    ti.insert(self._clip_get())
                elif event.key == pygame.K_BACKSPACE:
                    ti.delete_word_left()
                elif event.key == pygame.K_DELETE:
                    ti.delete_word_right()
                return
            if event.key == pygame.K_BACKSPACE:
                ti.backspace()
            elif event.key == pygame.K_DELETE:
                ti.delete()
            elif event.key == pygame.K_LEFT:
                ti.move(-1, bool(shift))
            elif event.key == pygame.K_RIGHT:
                ti.move(1, bool(shift))
            elif event.key == pygame.K_HOME:
                ti.home(bool(shift))
            elif event.key == pygame.K_END:
                ti.end(bool(shift))
            elif event.key == pygame.K_TAB:
                self.nick_sel = (self.nick_sel + 1) % 3
            elif event.key == pygame.K_RETURN:
                self._save_nick_and_back()
            elif event.key == pygame.K_ESCAPE:
                self._save_nick_and_back()
            return

        if event.type == pygame.MOUSEMOTION:
            if self.nick_dragging:
                local_x = event.pos[0] - self.ui.nick_text_origin
                ti.set_caret(ti.index_at_x(font, local_x), extend=True)
            else:
                r = self.ui.nick_rects
                if r.get("box") and r["box"].collidepoint(event.pos):
                    self.nick_sel = 0
                elif r.get("ok") and r["ok"].collidepoint(event.pos):
                    self.nick_sel = 1
                elif r.get("back") and r["back"].collidepoint(event.pos):
                    self.nick_sel = 2
                else:
                    self.nick_sel = -1
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            r = self.ui.nick_rects
            if r.get("box") and r["box"].collidepoint(event.pos):
                self.nick_sel = 0
                now = pygame.time.get_ticks()
                local_x = event.pos[0] - self.ui.nick_text_origin
                idx = ti.index_at_x(font, local_x)
                if self._nick_last_click and now - self._nick_last_click < 400:
                    ti.select_all()
                    self.nick_dragging = False
                else:
                    ti.set_caret(idx, extend=False)
                    ti.sel_anchor = idx
                    self.nick_dragging = True
                self._nick_last_click = now
            elif r.get("ok") and r["ok"].collidepoint(event.pos):
                self._save_nick_and_back()
            elif r.get("back") and r["back"].collidepoint(event.pos):
                self._save_nick_and_back()
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.nick_dragging = False

    def _save_nick_and_back(self):
        self.profile.set_nickname(self.nick_input.text)
        self.nick_input = TextInput(self.profile.nickname, MAX_NICK_LEN)
        self.nick_dragging = False
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass
        self.state = GameState.MENU
        self.main_menu.selected = 0

    # --- Игровой ввод (только мышь) ---

    def _handle_playing_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.state = GameState.MENU
            self.main_menu.selected = 0

    # --- Переходы меню ---

    def _process_menu_action(self, action: MenuAction):
        if action in (MenuAction.START, MenuAction.PLAY_AGAIN):
            self._start_game()
        elif action == MenuAction.SHOP:
            self.state = GameState.SHOP
            self.shop_sel = 0
        elif action == MenuAction.NICKNAME:
            self.nick_input = TextInput(self.profile.nickname, MAX_NICK_LEN)
            self.nick_sel = 0
            self.nick_dragging = False
            try:
                pygame.key.start_text_input()
            except Exception:
                pass
            self.state = GameState.NICKNAME
        elif action == MenuAction.LEADERBOARD:
            self._leaderboard_return = self.state
            self.state = GameState.LEADERBOARD
            self.leaderboard_menu.selected = 0
        elif action == MenuAction.QUIT:
            self.running = False
        elif action == MenuAction.MAIN_MENU:
            self.state = GameState.MENU
            self.main_menu.selected = 0
        elif action == MenuAction.BACK:
            if self.state == GameState.LEADERBOARD:
                self.state = self._leaderboard_return

    def _start_game(self):
        self.current_theme = self.profile.map_theme
        self.ui.set_theme(self.current_theme)
        self.arena_bg = make_gradient(self.screen.get_size(),
                                      self.current_theme["arena_top"],
                                      self.current_theme["arena_bottom"])
        custom = self.profile.custom_palette if is_custom(self.profile.skin_id) else None
        self.world = World(
            self.settings.world_radius,
            self.settings.bot_count,
            player_skin=self.profile.skin_id,
            player_color=self.profile.color_rgb,
            player_name=self.profile.nickname,
            player_custom=custom,
        )
        self.camera.snap_to(self.world.player.x, self.world.player.y)
        self.score = 0
        self.state = GameState.PLAYING

    def _update_playing(self, dt: float):
        if not self.world:
            return
        player = self.world.player

        mx, my = pygame.mouse.get_pos()
        target = self.camera.to_world(mx, my)
        boost = pygame.mouse.get_pressed()[0]

        self.world.update(dt, target, boost)
        self.camera.update(player.x, player.y, player.radius, dt)
        self.score = player.score

        if self.world.player_dead:
            self._end_game()

    def _end_game(self):
        self.death_snapshot = list(self.world.death_ranking) if self.world else []
        self.last_score_high = self.score_manager.add_score(self.score, self.profile.nickname)
        self.state = GameState.GAME_OVER
        self.game_over_menu.selected = 0

    # --- Отрисовка ---

    def _draw(self):
        if self.state == GameState.PLAYING and self.world:
            self.screen.blit(self.arena_bg, (0, 0))
            self.ui.draw_world(self.world, self.camera)
            # Снег в экранных координатах — падает независимо от камеры.
            self.snow.draw(self.screen)
            self.ui.draw_hud(self.world, self.score)
            return

        t = pygame.time.get_ticks() / 1000.0
        self.city.draw(self.screen, t, self.profile.flicker_on)
        self.snow.draw(self.screen)

        if self.state == GameState.MENU:
            self.ui.draw_menu(self.main_menu, self.score_manager.get_top(15),
                              self.profile.snow_on, self.profile.flicker_on)
        elif self.state == GameState.SHOP:
            self.ui.draw_shop(self.profile, self.shop_sel)
        elif self.state == GameState.NICKNAME:
            caret_on = (pygame.time.get_ticks() // 500) % 2 == 0
            self.ui.draw_nickname(self.nick_input, caret_on, self.nick_sel)
        elif self.state == GameState.GAME_OVER:
            self.ui.draw_game_over(self.game_over_menu, self.score, self.last_score_high,
                                   self.score_manager.best_score(), self.death_snapshot)
        elif self.state == GameState.LEADERBOARD:
            self.ui.draw_leaderboard(self.leaderboard_menu, self.score_manager.get_top())