"""Отрисовка интерфейса (liquid glass) и рендер игрового мира slither.io.

Объёмные «глянцевые» сегменты змей, свечение еды, атмосферная арена,
магазин скинов и экран ввода имени. Все экраны меню работают мышью —
прямоугольники элементов сохраняются для проверки наведения/клика."""

import math

import pygame

from menu import Menu
from skins import (
    GLOW_SKINS,
    color_name,
    color_rgb,
    darken,
    head_color,
    is_custom,
    lighten,
    segment_color,
    skin_name,
    uses_base_color,
)
from effects import (
    ACCENT,
    ACCENT_BRIGHT,
    ARENA_GRID,
    BOUNDARY,
    TEXT,
    TEXT_DIM,
    blur_surface,
    draw_glass_panel,
)

EDGE_MARGIN = 28


def _lerp_color(c1, c2, t: float):
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _q(color, step=6):
    return (color[0] // step * step, color[1] // step * step, color[2] // step * step)


class UIManager:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        pygame.font.init()
        self.font_title = pygame.font.SysFont("segoeui,arial", 58, bold=True)
        self.font_large = pygame.font.SysFont("segoeui,arial", 31, bold=True)
        self.font_medium = pygame.font.SysFont("segoeui,arial", 25, bold=True)
        self.font_small = pygame.font.SysFont("segoeui,arial", 17, bold=True)
        self.font_name = pygame.font.SysFont("segoeui,arial", 15, bold=True)

        self._orb_cache: dict[tuple, pygame.Surface] = {}
        self._glow_cache: dict[tuple, pygame.Surface] = {}
        self._vignette: pygame.Surface | None = None

        # Тема арены (меняется выбором карты).
        self.arena_grid = ARENA_GRID
        self.arena_boundary = BOUNDARY

        # Прямоугольники для управления мышью (заполняются при отрисовке).
        self.menu_item_rects: list[pygame.Rect] = []
        self.settings_arrows: tuple[pygame.Rect, pygame.Rect] | None = None
        self.shop_rects: dict = {}
        self.shop_order: list[str] = []
        self.nick_rects: dict[str, pygame.Rect] = {}
        self.nick_text_origin = 0
        self.nick_inner: tuple[int, int] = (0, 0)
        self._nick_scroll = 0
        self.settings_rects: dict = {}
        self.settings_order: list[str] = []
        self.lobby_toggles: dict[str, pygame.Rect] = {}

    def set_theme(self, theme: dict):
        self.arena_grid = theme["grid"]
        self.arena_boundary = theme["boundary"]

    def resize(self, screen: pygame.Surface):
        self.screen = screen
        self._vignette = None

    def handle_menu_input(self, event: pygame.event.Event, menu: Menu) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        key = event.key
        if key in (pygame.K_w, pygame.K_UP):
            menu.move_up()
        elif key in (pygame.K_s, pygame.K_DOWN):
            menu.move_down()
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            return True
        return False

    # --- Время/анимация ---

    def _now(self) -> float:
        return pygame.time.get_ticks() / 1000.0

    def _pulse(self, speed: float = 2.4) -> float:
        return 0.5 + 0.5 * math.sin(self._now() * speed)

    # --- Текст ---

    def _max_text_width(self, texts: list[str], font) -> int:
        return max((font.size(t)[0] for t in texts), default=0)

    def _fit_card_width(self, labels: list[str], min_w: int, pad: int, font) -> int:
        w, _ = self.screen.get_size()
        needed = self._max_text_width(labels, font) + pad * 2
        max_w = w - EDGE_MARGIN * 2
        return max(min(max(min_w, needed), max_w), 120)

    def _blit_text_fit(self, font, text, color, cx, cy, max_width):
        surf = font.render(text, True, color)
        if max_width > 0 and surf.get_width() > max_width:
            scale = max_width / surf.get_width()
            surf = pygame.transform.smoothscale(
                surf, (max(1, int(surf.get_width() * scale)), max(1, int(surf.get_height() * scale)))
            )
        rect = surf.get_rect(center=(int(cx), int(cy)))
        self.screen.blit(surf, rect)
        return rect

    def _draw_text_center(self, font, text, color, cx, cy):
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(int(cx), int(cy)))
        self.screen.blit(surf, rect)
        return rect

    def _draw_title(self, text: str):
        w, _ = self.screen.get_size()
        cx, cy = w // 2, 92
        pulse = self._pulse(1.6)

        glow = self.font_title.render(text, True, ACCENT)
        pad = 26
        gs = pygame.Surface((glow.get_width() + pad * 2, glow.get_height() + pad * 2), pygame.SRCALPHA)
        gs.blit(glow, (pad, pad))
        gs = blur_surface(gs, 0.26)
        gs.fill((255, 255, 255, int(120 + 70 * pulse)), special_flags=pygame.BLEND_RGBA_MULT)
        self.screen.blit(gs, gs.get_rect(center=(cx, cy)))

        depth = self.font_title.render(text, True, (12, 7, 26))
        self.screen.blit(depth, depth.get_rect(center=(cx, cy + 2)))
        self._draw_text_center(self.font_title, text, TEXT, cx, cy)

    # --- Карточки меню ---

    def _item_geometry(self, count: int, labels: list[str], pad: int = 44,
                       avail_w: int | None = None, center_x: int | None = None):
        w, h = self.screen.get_size()
        region_w = avail_w if avail_w is not None else w
        base = min(int(region_w * 0.86), 460)
        card_w = self._fit_card_width(labels, base, pad, self.font_large)

        # Адаптивная высота/интервал, чтобы все пункты помещались в окне.
        top_reserved = 150
        bottom_reserved = 40
        avail = max(120, h - top_reserved - bottom_reserved)
        card_h = 56
        gap = 10
        total = count * card_h + (count - 1) * gap
        if total > avail:
            scale = avail / total
            card_h = max(34, int(card_h * scale))
            gap = max(4, int(gap * scale))
            total = count * card_h + (count - 1) * gap
        spacing = card_h + gap
        start_y = max(top_reserved, h // 2 - total // 2)
        cx = center_x if center_x is not None else w // 2
        return cx, card_w, card_h, spacing, start_y

    def _selected_aura(self, rect: pygame.Rect):
        """Мягкая пульсирующая подсветка выбранного элемента."""
        pulse = self._pulse(3.0)
        pad = 10
        aura = pygame.Rect(rect.x - pad, rect.y - pad, rect.width + pad * 2, rect.height + pad * 2)
        surf = pygame.Surface(aura.size, pygame.SRCALPHA)
        a = int(50 + 90 * pulse)
        pygame.draw.rect(surf, (*ACCENT_BRIGHT, a), surf.get_rect(),
                         width=2, border_radius=22)
        self.screen.blit(surf, aura.topleft)

    def _draw_card(self, rect: pygame.Rect, label: str, is_sel: bool, action=None):
        if is_sel:
            self._selected_aura(rect)
        draw_glass_panel(
            self.screen, rect, radius=18,
            tint_alpha=120 if is_sel else 56, border_alpha=130, glow=is_sel,
        )
        color = ACCENT_BRIGHT if is_sel else TEXT
        font = self.font_large if is_sel else self.font_medium
        if action is not None and rect.height >= 34:
            icon_cx = rect.left + max(26, rect.height // 2)
            self._draw_icon(icon_cx, rect.centery, max(9, rect.height // 4), action, is_sel)
            self._blit_text_fit(font, label, color, rect.centerx + icon_cx - rect.left - 8,
                                rect.centery, rect.width - (icon_cx - rect.left) * 2 - 18)
        else:
            self._blit_text_fit(font, label, color, rect.centerx, rect.centery, rect.width - 36)

    def _draw_icon(self, cx, cy, r, action, is_sel):
        from menu import MenuAction
        palette = {
            MenuAction.START: (110, 235, 170),
            MenuAction.PLAY_AGAIN: (110, 235, 170),
            MenuAction.SHOP: (255, 190, 90),
            MenuAction.NICKNAME: (130, 190, 255),
            MenuAction.SETTINGS: (190, 160, 255),
            MenuAction.LEADERBOARD: (255, 215, 120),
            MenuAction.QUIT: (255, 120, 130),
            MenuAction.MAIN_MENU: (160, 200, 255),
            MenuAction.BACK: (160, 200, 255),
        }
        col = palette.get(action, ACCENT)
        badge = pygame.Rect(0, 0, r * 2 + 6, r * 2 + 6)
        badge.center = (int(cx), int(cy))
        bg = pygame.Surface(badge.size, pygame.SRCALPHA)
        a = 150 if is_sel else 90
        pygame.draw.rect(bg, (*col, a), bg.get_rect(), border_radius=8)
        self.screen.blit(bg, badge.topleft)
        ink = (20, 14, 32)
        if action in (MenuAction.START, MenuAction.PLAY_AGAIN):
            pygame.draw.polygon(self.screen, ink, [
                (cx - r * 0.5, cy - r * 0.7), (cx - r * 0.5, cy + r * 0.7), (cx + r * 0.7, cy)])
        elif action == MenuAction.SHOP:
            pygame.draw.rect(self.screen, ink,
                             (cx - r * 0.6, cy - r * 0.2, r * 1.2, r * 0.9), border_radius=3)
            pygame.draw.arc(self.screen, ink,
                            (cx - r * 0.45, cy - r * 0.7, r * 0.9, r * 0.9), 0.2, math.pi - 0.2, 2)
        elif action == MenuAction.NICKNAME:
            self._draw_text_center(self.font_small, "Aa", ink, cx, cy)
        elif action == MenuAction.SETTINGS:
            pygame.draw.circle(self.screen, ink, (int(cx), int(cy)), int(r * 0.7), 2)
            pygame.draw.circle(self.screen, ink, (int(cx), int(cy)), max(1, int(r * 0.22)))
        elif action == MenuAction.LEADERBOARD:
            self._star(cx, cy, r * 0.85, ink)
        elif action == MenuAction.QUIT:
            pygame.draw.circle(self.screen, ink, (int(cx), int(cy)), int(r * 0.7), 2)
            pygame.draw.line(self.screen, ink, (cx, cy - r * 0.8), (cx, cy), 2)
        elif action in (MenuAction.MAIN_MENU, MenuAction.BACK):
            pygame.draw.polygon(self.screen, ink, [
                (cx + r * 0.5, cy - r * 0.7), (cx + r * 0.5, cy + r * 0.7), (cx - r * 0.7, cy)])
        else:
            pygame.draw.circle(self.screen, ink, (int(cx), int(cy)), max(1, int(r * 0.4)))

    def _star(self, cx, cy, r, color):
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rad = r if i % 2 == 0 else r * 0.45
            pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
        pygame.draw.polygon(self.screen, color, pts)

    def _draw_menu_items(self, menu, selected, center_x=None, avail_w=None):
        labels = menu.get_labels()
        actions = [a for _, a in menu.items]
        cx, card_w, card_h, spacing, start_y = self._item_geometry(
            len(labels), labels, avail_w=avail_w, center_x=center_x)
        rects = []
        for i, label in enumerate(labels):
            y = start_y + i * spacing
            rect = pygame.Rect(cx - card_w // 2, y, card_w, card_h)
            self._draw_card(rect, label, i == selected, action=actions[i])
            rects.append(rect)
        self.menu_item_rects = rects

    def _draw_side_leaderboard(self, panel: pygame.Rect, entries: list[tuple]):
        draw_glass_panel(self.screen, panel, radius=20, tint_alpha=64, border_alpha=120)
        self._blit_text_fit(self.font_medium, "ТОП-15 ИГРОКОВ", ACCENT_BRIGHT,
                            panel.centerx, panel.top + 26, panel.width - 24)
        if not entries:
            return
        header = 54
        avail = panel.height - header - 12
        rows = len(entries)
        row_h = max(16, min(30, avail // max(1, rows)))
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(panel)
        for i, (name, score) in enumerate(entries):
            ry = panel.top + header + i * row_h + row_h // 2
            # Лидер (#1) — белым, призёры ярче, остальные приглушённо.
            place_col = (255, 255, 255) if i == 0 else (TEXT if i < 3 else TEXT_DIM)
            num = self.font_small.render(f"{i + 1}.", True, place_col)
            self.screen.blit(num, (panel.left + 16, ry - num.get_height() // 2))
            sc = self.font_small.render(str(score), True, ACCENT if i < 3 else TEXT_DIM)
            sc_rect = sc.get_rect(midright=(panel.right - 16, ry))
            self.screen.blit(sc, sc_rect)
            nm = self.font_small.render(name, True, place_col)
            max_nm = sc_rect.left - (panel.left + 44) - 8
            if max_nm > 10 and nm.get_width() > max_nm:
                scale = max_nm / nm.get_width()
                nm = pygame.transform.smoothscale(
                    nm, (max_nm, int(nm.get_height() * scale)))
            self.screen.blit(nm, (panel.left + 44, ry - nm.get_height() // 2))
        self.screen.set_clip(prev_clip)

    def _draw_arrows(self, rect: pygame.Rect, active: bool):
        """Рисует кликабельные стрелки ‹ › по краям карточки, возвращает их rect'ы."""
        aw = 44
        left = pygame.Rect(rect.left + 6, rect.top + 6, aw, rect.height - 12)
        right = pygame.Rect(rect.right - aw - 6, rect.top + 6, aw, rect.height - 12)
        col = ACCENT_BRIGHT if active else TEXT_DIM
        self._draw_text_center(self.font_large, "‹", col, left.centerx, left.centery)
        self._draw_text_center(self.font_large, "›", col, right.centerx, right.centery)
        return left, right

    # --- Экраны меню ---

    def draw_menu(self, menu: Menu, side_entries: list[tuple] | None = None,
                  snow_on: bool = True, flicker_on: bool = True):
        self.settings_arrows = None
        self._draw_title(menu.title)
        w, h = self.screen.get_size()
        panel = None
        center_x = None
        avail_w = None
        if side_entries and w >= 900:
            panel_w = min(330, int(w * 0.27))
            panel = pygame.Rect(w - panel_w - EDGE_MARGIN, 150, panel_w,
                                h - 150 - EDGE_MARGIN)
            left_area = panel.left - EDGE_MARGIN
            center_x = left_area // 2 + EDGE_MARGIN // 2
            avail_w = left_area - EDGE_MARGIN
        self._draw_menu_items(menu, menu.selected, center_x=center_x, avail_w=avail_w)
        if panel:
            self._draw_side_leaderboard(panel, side_entries)
        self._draw_lobby_toggles(snow_on, flicker_on)

    def _draw_lobby_toggles(self, snow_on: bool, flicker_on: bool):
        """Две маленькие кнопки-тумблера (снег/мерцание) в углу лобби."""
        w, h = self.screen.get_size()
        bw, bh = 150, 40
        gap = 12
        x = EDGE_MARGIN
        y = h - EDGE_MARGIN - bh
        defs = [("snow", "Снег", snow_on), ("flicker", "Мерцание", flicker_on)]
        toggles = {}
        for key, label, on in defs:
            rect = pygame.Rect(x, y, bw, bh)
            tint = 110 if on else 44
            draw_glass_panel(self.screen, rect, radius=14, tint_alpha=tint, border_alpha=120)
            dot = pygame.Rect(rect.left + 12, rect.centery - 7, 14, 14)
            pygame.draw.rect(self.screen, (120, 235, 170) if on else (120, 120, 140),
                             dot, border_radius=4)
            col = TEXT if on else TEXT_DIM
            txt = f"{label}: {'Вкл' if on else 'Выкл'}"
            self._blit_text_fit(self.font_small, txt, col,
                                dot.right + (rect.right - dot.right) // 2, rect.centery,
                                rect.right - dot.right - 12)
            toggles[key] = rect
            x += bw + gap
        self.lobby_toggles = toggles

    def draw_leaderboard(self, menu: Menu, entries: list[tuple]):
        self._draw_title(menu.title)
        w, h = self.screen.get_size()

        row_texts = [f"#{i + 1}  {n}   {s}" for i, (n, s) in enumerate(entries)] or ["Пока нет рекордов!"]
        base = min(int(w * 0.72), 520)
        panel_w = self._fit_card_width(row_texts, base, 56, self.font_medium)

        # Адаптивная высота строки, чтобы все записи + кнопка помещались.
        top = 168
        back_h = 56
        bottom = h - EDGE_MARGIN - back_h - 20
        rows = max(len(entries), 1)
        row_h = max(22, min(50, (bottom - top - 44) // rows))
        panel_h = 44 + rows * row_h
        panel = pygame.Rect(w // 2 - panel_w // 2, top, panel_w, panel_h)
        draw_glass_panel(self.screen, panel, radius=22, tint_alpha=66, border_alpha=120)

        font = self.font_medium if row_h >= 34 else self.font_small
        if entries:
            for i, (name, score) in enumerate(entries):
                ry = panel.top + 32 + i * row_h
                place_color = ACCENT_BRIGHT if i == 0 else (ACCENT if i < 3 else TEXT_DIM)
                self._draw_text_center(font, f"#{i + 1}", place_color, panel.left + 44, ry)
                nm = font.render(name, True, TEXT)
                self.screen.blit(nm, (panel.left + 84, ry - nm.get_height() // 2))
                sc = font.render(str(score), True, ACCENT_BRIGHT)
                self.screen.blit(sc, sc.get_rect(midright=(panel.right - 28, ry)))
        else:
            self._blit_text_fit(self.font_medium, "Пока нет рекордов!", TEXT_DIM,
                                panel.centerx, panel.centery, panel_w - 40)

        back_w = self._fit_card_width(["Назад"], 240, 48, self.font_large)
        back_rect = pygame.Rect(w // 2 - back_w // 2, panel.bottom + 20, back_w, back_h)
        self._draw_card(back_rect, "Назад", True)
        self.menu_item_rects = [back_rect]

    def draw_game_over(self, menu: Menu, score: int, is_high_score: bool, best: int,
                       snapshot: list[tuple] | None = None):
        self._draw_title(menu.title)
        w, h = self.screen.get_size()
        cx = w // 2

        info_texts = [f"Счёт: {score}", f"Лучший: {best}", "Новый рекорд!"]
        info_w = self._fit_card_width(info_texts, 380, 44, self.font_large)
        info_h = 92 if is_high_score else 70
        info = pygame.Rect(cx - info_w // 2, 144, info_w, info_h)
        draw_glass_panel(self.screen, info, radius=20, tint_alpha=78, border_alpha=120)
        self._blit_text_fit(self.font_large, f"Счёт: {score}", TEXT,
                            cx, info.top + 26, info_w - 36)
        self._blit_text_fit(self.font_small, f"Лучший: {best}", TEXT_DIM,
                            cx, info.top + 52, info_w - 36)
        if is_high_score:
            self._blit_text_fit(self.font_small, "Новый рекорд!", ACCENT_BRIGHT,
                                cx, info.top + 74, info_w - 36)

        # Снимок живого рейтинга на момент гибели.
        next_y = info.bottom + 16
        if snapshot:
            snap_w = self._fit_card_width(
                [f"#{i+1} {n} {s}" for i, (n, s, _) in enumerate(snapshot)],
                360, 48, self.font_small)
            snap_h = 40 + len(snapshot) * 28
            snap = pygame.Rect(cx - snap_w // 2, next_y, snap_w, snap_h)
            draw_glass_panel(self.screen, snap, radius=16, tint_alpha=60, border_alpha=100)
            self._blit_text_fit(self.font_small, "Рейтинг на момент гибели", ACCENT_BRIGHT,
                                cx, snap.top + 18, snap_w - 24)
            for i, (name, sc, is_player) in enumerate(snapshot):
                ry = snap.top + 38 + i * 28
                col = ACCENT_BRIGHT if is_player else TEXT
                line = self.font_small.render(f"{i + 1}. {name}", True, col)
                self.screen.blit(line, (snap.left + 20, ry - line.get_height() // 2))
                scs = self.font_small.render(str(sc), True, TEXT_DIM)
                self.screen.blit(scs, scs.get_rect(midright=(snap.right - 20, ry)))
            next_y = snap.bottom + 14

        # Кнопки меню — фиксированный столбец под информацией.
        labels = menu.get_labels()
        card_h = 48
        gap = 10
        rects = []
        for i, label in enumerate(labels):
            rect = pygame.Rect(cx - 150, next_y + i * (card_h + gap), 300, card_h)
            self._draw_card(rect, label, i == menu.selected)
            rects.append(rect)
        self.menu_item_rects = rects

    # --- Магазин ---

    def draw_shop(self, profile, selected: int):
        self._draw_title("МАГАЗИН")
        w, h = self.screen.get_size()
        cx = w // 2
        t = self._now()
        skin = profile.skin_id

        # Какие строки показываем (логика зависит от скина).
        value_keys = ["skin"]
        if uses_base_color(skin):
            value_keys.append("color")
        if is_custom(skin):
            value_keys += ["palette", "count"]
        value_keys += ["map", "snow"]
        order = value_keys + ["play", "back"]
        self.shop_order = order
        active_key = order[selected] if 0 <= selected < len(order) else None

        panel_w = min(w - EDGE_MARGIN * 2, 540)
        row_w = min(panel_w, 480)
        n_rows = len(value_keys) + 1  # +1 строка кнопок

        top = 134
        bottom = h - EDGE_MARGIN
        gap = 9
        avail_rows = bottom - top - 22 - 88  # резерв ~88px под превью
        card_h = min(54, max(32, (avail_rows - (n_rows - 1) * gap) // max(1, n_rows)))
        rows_total = n_rows * card_h + (n_rows - 1) * gap
        prev_h = max(88, min(176, bottom - top - rows_total - 22))

        preview = pygame.Rect(cx - panel_w // 2, top, panel_w, prev_h)
        draw_glass_panel(self.screen, preview, radius=22, tint_alpha=60, border_alpha=120)
        # Когда активна строка карты — показываем миниатюру арены, иначе змейку.
        if active_key == "map":
            self._draw_map_thumb(preview.inflate(-28, -22), profile.map_theme)
        else:
            custom = profile.custom_palette if is_custom(skin) else None
            self._draw_preview_snake(preview, skin, profile.color_rgb, t, custom)

        rects: dict = {}
        y = preview.bottom + 16
        for key in value_keys:
            rect = pygame.Rect(cx - row_w // 2, y, row_w, card_h)
            is_sel = order.index(key) == selected
            if key == "skin":
                l, r = self._draw_value_row(rect, "Выберите скин", skin_name(skin), is_sel)
            elif key == "color":
                l, r = self._draw_value_row(rect, "Цвет", color_name(profile.color_index),
                                            is_sel, swatch=profile.color_rgb)
            elif key == "count":
                l, r = self._draw_value_row(rect, "Цветов", str(len(profile.custom_colors)), is_sel)
            elif key == "palette":
                l, r, sw = self._draw_palette_row(rect, profile, is_sel)
                rects["palette_swatches"] = sw
            elif key == "map":
                theme = profile.map_theme
                l, r = self._draw_value_row(rect, "Выберите карту", theme["name"],
                                            is_sel, swatch=theme["boundary"])
            elif key == "snow":
                l, r = self._draw_value_row(rect, "Снег",
                                            "Вкл" if profile.snow_on else "Выкл", is_sel)
            rects[key] = rect
            rects[key + "_l"] = l
            rects[key + "_r"] = r
            y += card_h + gap

        btn_w = (row_w - 14) // 2
        play_rect = pygame.Rect(cx - row_w // 2, y, btn_w, card_h)
        back_rect = pygame.Rect(play_rect.right + 14, y, btn_w, card_h)
        self._draw_card(play_rect, "Играть", order.index("play") == selected)
        self._draw_card(back_rect, "Назад", order.index("back") == selected)
        rects["play"] = play_rect
        rects["back"] = back_rect
        self.shop_rects = rects

    def _draw_value_row(self, rect, caption, value, is_sel, swatch=None):
        if is_sel:
            self._selected_aura(rect)
        draw_glass_panel(self.screen, rect, radius=18,
                         tint_alpha=120 if is_sel else 56, border_alpha=130, glow=is_sel)
        cap = self.font_small.render(caption, True, TEXT_DIM)
        self.screen.blit(cap, (rect.left + 52, rect.top + 6))
        vcx = rect.centerx + (14 if swatch else 0)
        self._blit_text_fit(self.font_medium, value, ACCENT_BRIGHT if is_sel else TEXT,
                            vcx, rect.centery + 4, rect.width - 150)
        if swatch is not None:
            sw = pygame.Rect(0, 0, 20, 20)
            sw.center = (rect.centerx - self.font_medium.size(value)[0] // 2 - 18, rect.centery + 4)
            pygame.draw.rect(self.screen, swatch, sw, border_radius=6)
            pygame.draw.rect(self.screen, lighten(swatch, 0.4), sw, width=1, border_radius=6)
        return self._draw_arrows(rect, True)

    def _draw_palette_row(self, rect, profile, is_sel):
        if is_sel:
            self._selected_aura(rect)
        draw_glass_panel(self.screen, rect, radius=18,
                         tint_alpha=120 if is_sel else 56, border_alpha=130, glow=is_sel)
        cap = self.font_small.render("Палитра", True, TEXT_DIM)
        self.screen.blit(cap, (rect.left + 52, rect.top + 6))
        n = len(profile.custom_colors)
        sw_size = min(26, rect.height - 18)
        total_w = n * (sw_size + 8) - 8
        sx = rect.centerx - total_w // 2
        sy = rect.centery + 4 - sw_size // 2
        swatch_rects = []
        for i, ci in enumerate(profile.custom_colors):
            r = pygame.Rect(sx + i * (sw_size + 8), sy, sw_size, sw_size)
            pygame.draw.rect(self.screen, color_rgb(ci), r, border_radius=5)
            if i == profile.custom_slot:
                pygame.draw.rect(self.screen, (255, 255, 255), r, width=2, border_radius=5)
            else:
                pygame.draw.rect(self.screen, lighten(color_rgb(ci), 0.3), r, width=1, border_radius=5)
            swatch_rects.append(r)
        l, r = self._draw_arrows(rect, True)
        return l, r, swatch_rects

    def _draw_preview_snake(self, rect, skin, base_color, t, custom=None):
        n = 24
        amp = rect.height * 0.22
        r = max(6, int(rect.height * 0.17))
        cy = rect.centery + 4
        margin = r + 12
        span = max(10, rect.width - margin * 2)
        glow = skin in GLOW_SKINS
        pts = []
        for i in range(n):
            x = rect.left + margin + span * (i / (n - 1))
            y = cy + amp * math.sin(i * 0.5 - t * 3.0)
            pts.append((x, y))
        for i in range(n):
            col = segment_color(skin, base_color, n - 1 - i, n, t, custom)
            px, py = pts[i]
            if glow and i % 2 == 0:
                g = self._glow_surf(col, int(r * 0.9))
                self.screen.blit(g, (int(px) - g.get_width() // 2, int(py) - g.get_height() // 2))
            orb = self._orb(col, r)
            self.screen.blit(orb, (int(px) - orb.get_width() // 2, int(py) - orb.get_height() // 2))
        hx, hy = pts[-1]
        hr = int(r * 1.25)
        orb = self._orb(head_color(skin, base_color, custom), hr)
        self.screen.blit(orb, (int(hx) - orb.get_width() // 2, int(hy) - orb.get_height() // 2))
        self._draw_eyes(hx, hy, hr, 0.0)

    def _draw_map_thumb(self, rect, theme):
        """Миниатюра арены: фон-градиент, сетка и цвет границы — вживую."""
        thumb = pygame.Surface(rect.size)
        top = theme["arena_top"]
        bot = theme["arena_bottom"]
        for yy in range(rect.height):
            tt = yy / max(1, rect.height - 1)
            thumb.fill(_lerp_color(top, bot, tt), (0, yy, rect.width, 1))
        grid = theme["grid"]
        step = max(12, rect.width // 9)
        for gx in range(step, rect.width, step):
            pygame.draw.line(thumb, grid, (gx, 0), (gx, rect.height), 1)
        for gy in range(step, rect.height, step):
            pygame.draw.line(thumb, grid, (0, gy), (rect.width, gy), 1)
        # Граница мира — окружность цветом boundary.
        rr = int(min(rect.width, rect.height) * 0.42)
        pygame.draw.circle(thumb, theme["boundary"], (rect.width // 2, rect.height // 2), rr, 3)
        self.screen.blit(thumb, rect.topleft)
        pygame.draw.rect(self.screen, theme["boundary"], thumb.get_rect(topleft=rect.topleft),
                         width=2, border_radius=10)
        self._blit_text_fit(self.font_small, theme["name"], TEXT,
                            rect.centerx, rect.top + 14, rect.width - 16)

    # --- Экран ввода имени ---

    def draw_nickname(self, text_input, caret_on: bool, selected: int):
        self._draw_title("Выберите ваше имя")
        w, h = self.screen.get_size()
        cx = w // 2

        # Поле фиксированной ширины; текст обрезается/прокручивается внутри.
        box_w = min(w - EDGE_MARGIN * 2, 460)
        box = pygame.Rect(cx - box_w // 2, 184, box_w, 76)
        if selected == 0:
            self._selected_aura(box)
        draw_glass_panel(self.screen, box, radius=18, tint_alpha=70, border_alpha=130,
                         glow=(selected == 0))

        pad = 18
        inner_left = box.left + pad
        inner_right = box.right - pad
        inner_w = inner_right - inner_left
        font = self.font_large
        text = text_input.text
        caret_x = font.size(text[:text_input.caret])[0]

        # Прокрутка, чтобы каретка оставалась видимой.
        if caret_x - self._nick_scroll > inner_w:
            self._nick_scroll = caret_x - inner_w
        if caret_x - self._nick_scroll < 0:
            self._nick_scroll = caret_x
        total_w = font.size(text)[0]
        self._nick_scroll = max(0, min(self._nick_scroll, max(0, total_w - inner_w)))
        origin_x = inner_left - self._nick_scroll
        self.nick_text_origin = origin_x
        self.nick_inner = (inner_left, inner_right)

        prev_clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(inner_left, box.top, inner_w, box.height))
        # Выделение.
        if text_input.has_selection():
            a, b = text_input.sel_range()
            xa = origin_x + font.size(text[:a])[0]
            xb = origin_x + font.size(text[:b])[0]
            sel = pygame.Rect(int(xa), box.centery - 18, int(xb - xa), 36)
            sel_surf = pygame.Surface(sel.size, pygame.SRCALPHA)
            sel_surf.fill((*ACCENT_BRIGHT, 90))
            self.screen.blit(sel_surf, sel.topleft)
        # Текст.
        if text:
            surf = font.render(text, True, TEXT)
            self.screen.blit(surf, (origin_x, box.centery - surf.get_height() // 2))
        # Каретка.
        if caret_on:
            cxp = origin_x + caret_x
            pygame.draw.line(self.screen, TEXT, (cxp, box.centery - 18), (cxp, box.centery + 18), 2)
        self.screen.set_clip(prev_clip)

        hint = self.font_small.render(
            "Можно использовать латиницу, кириллицу и цифры в вашем никнейме.",
            True, TEXT_DIM)
        if hint.get_width() > w - EDGE_MARGIN * 2:
            scale = (w - EDGE_MARGIN * 2) / hint.get_width()
            hint = pygame.transform.smoothscale(
                hint, (int(hint.get_width() * scale), int(hint.get_height() * scale)))
        self.screen.blit(hint, hint.get_rect(center=(cx, box.bottom + 24)))

        # Кнопки в ФИКСИРОВАННЫХ позициях (не зависят от длины текста).
        btn_w = min(box_w, 360)
        half = (btn_w - 14) // 2
        by = box.bottom + 56
        ok_rect = pygame.Rect(cx - btn_w // 2, by, half, 54)
        back_rect = pygame.Rect(ok_rect.right + 14, by, half, 54)
        self._draw_card(ok_rect, "ОК", selected == 1)
        self._draw_card(back_rect, "Назад", selected == 2)
        self.nick_rects = {"box": box, "ok": ok_rect, "back": back_rect}

    # --- Рендер мира ---

    def _in_bounds(self, x, y, bounds, margin=0.0):
        return (bounds[0] - margin <= x <= bounds[2] + margin
                and bounds[1] - margin <= y <= bounds[3] + margin)

    def draw_world(self, world, camera):
        t = self._now()
        bounds = camera.visible_bounds()
        self._draw_arena_grid(camera, bounds)
        self._draw_boundary(world, camera)
        self._draw_food(world, camera, bounds, t)

        for s in world.snakes:
            if s.alive and not s.is_player:
                self._draw_snake(s, camera, bounds, t)
        if world.player.alive:
            self._draw_snake(world.player, camera, bounds, t)

        self.screen.blit(self._get_vignette(), (0, 0), special_flags=pygame.BLEND_MULT)

    def _get_vignette(self):
        w, h = self.screen.get_size()
        if self._vignette is not None and self._vignette.get_size() == (w, h):
            return self._vignette
        surf = pygame.Surface((w, h))
        cx, cy = w // 2, h // 2
        max_r = math.hypot(w, h) / 2
        steps = 26
        for i in range(steps):
            tt = i / (steps - 1)
            rr = int(max_r * (1 - tt))
            v = int(150 + 105 * tt)
            pygame.draw.circle(surf, (v, v, v), (cx, cy), max(1, rr))
        self._vignette = surf
        return surf

    def _draw_arena_grid(self, camera, bounds):
        w, h = self.screen.get_size()
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        spacing = 100.0
        left, top, right, bottom = bounds
        color = (*self.arena_grid, 24)
        x = math.floor(left / spacing) * spacing
        while x <= right:
            sx, sy0 = camera.to_screen(x, top)
            _, sy1 = camera.to_screen(x, bottom)
            pygame.draw.line(surf, color, (int(sx), int(sy0)), (int(sx), int(sy1)))
            x += spacing
        y = math.floor(top / spacing) * spacing
        while y <= bottom:
            sx0, sy = camera.to_screen(left, y)
            sx1, _ = camera.to_screen(right, y)
            pygame.draw.line(surf, color, (int(sx0), int(sy)), (int(sx1), int(sy)))
            y += spacing
        self.screen.blit(surf, (0, 0))

    def _draw_boundary(self, world, camera):
        cx, cy = camera.to_screen(0.0, 0.0)
        r = int(world.radius * camera.zoom)
        if r <= 0:
            return
        glow = pygame.Surface((self.screen.get_width(), self.screen.get_height()), pygame.SRCALPHA)
        for i in range(5):
            a = int(70 * (1 - i / 4))
            pygame.draw.circle(glow, (*self.arena_boundary, a), (int(cx), int(cy)), r + i * 4, 3)
        self.screen.blit(glow, (0, 0))
        pygame.draw.circle(self.screen, self.arena_boundary, (int(cx), int(cy)), r, 2)

    def _glow_surf(self, color, r):
        color = _q(color)
        r = max(2, int(r))
        key = (color, r)
        s = self._glow_cache.get(key)
        if s is None:
            size = r * 4 + 2
            s = pygame.Surface((size, size), pygame.SRCALPHA)
            c = (size // 2, size // 2)
            layers = 5
            for i in range(layers - 1, -1, -1):
                tt = i / (layers - 1)
                a = int(80 * (1 - tt))
                rr = int(r * (1 + tt * 1.7))
                if rr > 0:
                    pygame.draw.circle(s, (*color, a), c, rr)
            self._glow_cache[key] = s
        return s

    def _orb(self, color, r):
        color = _q(color)
        r = max(2, int(r))
        key = (color, r)
        s = self._orb_cache.get(key)
        if s is not None:
            return s
        size = r * 2 + 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = (size // 2, size // 2)
        pygame.draw.circle(surf, color, c, r)

        light = lighten(color, 0.6)
        dark = darken(color, 0.5)
        layers = 6
        for i in range(layers):
            tt = i / (layers - 1)
            rr = int(r * (0.92 - 0.58 * tt))
            a = int(46 * (1 - tt))
            if rr > 0 and a > 0:
                pygame.draw.circle(surf, (*light, a), (c[0], c[1] - int(r * 0.26)), rr)
        for i in range(layers):
            tt = i / (layers - 1)
            rr = int(r * (0.94 - 0.55 * tt))
            a = int(42 * (1 - tt))
            if rr > 0 and a > 0:
                pygame.draw.circle(surf, (*dark, a), (c[0], c[1] + int(r * 0.32)), rr)

        sx, sy = c[0] - int(r * 0.32), c[1] - int(r * 0.34)
        for i in range(5):
            tt = i / 4
            rr = max(1, int(r * 0.36 * (1 - tt)))
            a = int(40 + 150 * tt)
            pygame.draw.circle(surf, (255, 255, 255, a), (sx, sy), rr)

        pygame.draw.circle(surf, (*darken(color, 0.35), 150), c, r, max(1, r // 7))

        mask = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), c, r)
        surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self._orb_cache[key] = surf
        return surf

    def _draw_food(self, world, camera, bounds, t):
        zoom = camera.zoom
        for p in world.food.pellets:
            if not self._in_bounds(p.x, p.y, bounds):
                continue
            sx, sy = camera.to_screen(p.x, p.y)
            pulse = 1.0 + 0.22 * math.sin(t * 3.2 + p.phase)
            r = max(2, int(p.radius * zoom * pulse))
            glow = self._glow_surf(p.color, r)
            self.screen.blit(glow, (int(sx) - glow.get_width() // 2,
                                    int(sy) - glow.get_height() // 2))
            core = lighten(p.color, 0.3)
            pygame.draw.circle(self.screen, core, (int(sx), int(sy)), max(2, int(r * 0.72)))
            spark = max(1, int(r * 0.3))
            pygame.draw.circle(self.screen, (255, 255, 255),
                               (int(sx - r * 0.25), int(sy - r * 0.25)), spark)

    def _draw_eyes(self, hx, hy, hr, heading):
        dx, dy = math.cos(heading), math.sin(heading)
        px, py = -dy, dx
        eye_off = hr * 0.5
        eye_fwd = hr * 0.28
        eye_r = max(2, int(hr * 0.44))
        pup_r = max(1, int(eye_r * 0.52))
        for sgn in (-1, 1):
            ex = hx + dx * eye_fwd + px * eye_off * sgn
            ey = hy + dy * eye_fwd + py * eye_off * sgn
            pygame.draw.circle(self.screen, (252, 252, 255), (int(ex), int(ey)), eye_r)
            pcx = ex + dx * eye_r * 0.42
            pcy = ey + dy * eye_r * 0.42
            pygame.draw.circle(self.screen, (28, 18, 42), (int(pcx), int(pcy)), pup_r)
            sp = max(1, int(pup_r * 0.6))
            pygame.draw.circle(self.screen, (255, 255, 255),
                               (int(pcx - pup_r * 0.4), int(pcy - pup_r * 0.4)), sp)

    def _draw_snake(self, s, camera, bounds, t):
        zoom = camera.zoom
        r = max(2, int(s.radius * zoom))
        segs = s.segments
        count = len(segs)
        margin = s.radius + 26
        glow = s.skin in GLOW_SKINS

        custom = getattr(s, "custom_colors", None)
        for idx in range(count - 1, 0, -1):
            sx, sy = segs[idx]
            if not self._in_bounds(sx, sy, bounds, margin):
                continue
            px, py = camera.to_screen(sx, sy)
            col = segment_color(s.skin, s.base_color, idx, count, t, custom)
            if glow and idx % 2 == 0:
                g = self._glow_surf(col, int(r * 0.85))
                self.screen.blit(g, (int(px) - g.get_width() // 2, int(py) - g.get_height() // 2))
            orb = self._orb(col, r)
            self.screen.blit(orb, (int(px) - orb.get_width() // 2, int(py) - orb.get_height() // 2))

        hx, hy = camera.to_screen(s.x, s.y)
        hr = max(3, int(r * 1.22))
        hcol = head_color(s.skin, s.base_color, custom)
        if glow:
            g = self._glow_surf(hcol, hr)
            self.screen.blit(g, (int(hx) - g.get_width() // 2, int(hy) - g.get_height() // 2))
        orb = self._orb(hcol, hr)
        self.screen.blit(orb, (int(hx) - orb.get_width() // 2, int(hy) - orb.get_height() // 2))
        self._draw_eyes(hx, hy, hr, s.heading)

        if hr >= 4 and -40 <= hx <= self.screen.get_width() + 40:
            label = self.font_name.render(s.name, True, TEXT if s.is_player else TEXT_DIM)
            self.screen.blit(label, label.get_rect(center=(int(hx), int(hy - hr - 14))))

    # --- HUD ---

    def draw_hud(self, world, score: int):
        w, h = self.screen.get_size()

        score_text = f"Счёт: {score}"
        sp_w = max(170, self.font_large.size(score_text)[0] + 48)
        score_panel = pygame.Rect(EDGE_MARGIN, 20, sp_w, 52)
        draw_glass_panel(self.screen, score_panel, radius=16, tint_alpha=90, border_alpha=120)
        self._blit_text_fit(self.font_large, score_text, TEXT,
                            score_panel.centerx, score_panel.centery, sp_w - 24)

        self._draw_live_leaderboard(world)
        self._draw_minimap(world)

    def _draw_live_leaderboard(self, world):
        w, _ = self.screen.get_size()
        leaders = world.leaderboard(5)
        rows = []
        for i, s in enumerate(leaders):
            name = s.name if len(s.name) <= 12 else s.name[:11] + "…"
            rows.append((i + 1, name, s.score, s.is_player, s.color))

        panel_w = 240
        panel_h = 56 + len(rows) * 30
        panel = pygame.Rect(w - EDGE_MARGIN - panel_w, 20, panel_w, panel_h)
        draw_glass_panel(self.screen, panel, radius=16, tint_alpha=72, border_alpha=110)
        self._blit_text_fit(self.font_medium, "Лидеры", ACCENT_BRIGHT,
                            panel.centerx, panel.top + 22, panel_w - 24)

        for idx, (rank, name, sc, is_player, color) in enumerate(rows):
            ry = panel.top + 50 + idx * 30
            swatch = pygame.Rect(panel.left + 16, ry - 6, 12, 12)
            pygame.draw.rect(self.screen, color, swatch, border_radius=3)
            # Имя лидера (#1) всегда белое; игрок выделяется ярко.
            txt_color = (255, 255, 255) if rank == 1 else (ACCENT_BRIGHT if is_player else TEXT_DIM)
            label = f"{rank}. {name}"
            surf = self.font_small.render(label, True, txt_color)
            self.screen.blit(surf, (panel.left + 36, ry - 9))
            sc_surf = self.font_small.render(str(sc), True, TEXT_DIM)
            self.screen.blit(sc_surf, sc_surf.get_rect(midright=(panel.right - 16, ry)))

    def _draw_minimap(self, world):
        w, h = self.screen.get_size()
        size = 150
        panel = pygame.Rect(w - EDGE_MARGIN - size, h - EDGE_MARGIN - size, size, size)
        draw_glass_panel(self.screen, panel, radius=16, tint_alpha=66, border_alpha=100)

        cx, cy = panel.center
        mm_r = size * 0.42
        scale = mm_r / world.radius
        pygame.draw.circle(self.screen, self.arena_boundary, (cx, cy), int(mm_r), 1)

        for s in world.snakes:
            if not s.alive:
                continue
            mx = cx + s.x * scale
            my = cy + s.y * scale
            if s.is_player:
                pygame.draw.circle(self.screen, (255, 255, 255), (int(mx), int(my)), 4)
                pygame.draw.circle(self.screen, s.color, (int(mx), int(my)), 2)
            elif getattr(s, "fat", False):
                pygame.draw.circle(self.screen, s.color, (int(mx), int(my)), 4)
            else:
                pygame.draw.circle(self.screen, s.color, (int(mx), int(my)), 2)
