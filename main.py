"""
Universe 25 — Mouse Utopia Experiment
Pygame visualisation

Controls:
  SPACE       pause / resume
  + / -       increase / decrease simulation speed
  R           reset simulation
  ESC         quit
  Left-click  select a mouse to inspect its status
"""

import sys
import time
import pygame

from simulation import (
    World, State, Sex, Mouse,
    GRID_W, GRID_H, STATE_COLORS,
)

# ── Display layout ─────────────────────────────────────────────────────────────
CELL    = 8      # pixels per grid cell
PANEL_W = 240    # right info panel width
GRAPH_H = 150    # bottom population graph height
WIN_W   = GRID_W * CELL + PANEL_W
WIN_H   = GRID_H * CELL + GRAPH_H

# ── Colours ───────────────────────────────────────────────────────────────────
BG       = (10,  14,  20)
PANEL_BG = (14,  18,  28)
GRAPH_BG = (9,   11,  17)
LINE_CLR = (35,  45,  60)
TXT      = (200, 210, 220)
TXT_DIM  = (90,  110, 130)
HILIGHT  = (255, 255, 255)

PHASE_COLORS = [
    (80,  200, 90),    # 0 Growth
    (200, 180, 60),    # 1 Stagnation
    (210, 100, 50),    # 2 Behavioral Sink
    (200,  50, 50),    # 3 Collapse
]
PHASE_NAMES = [
    "I  —  Growth",
    "II  —  Stagnation",
    "III  —  Behavioral Sink",
    "IV  —  Collapse",
]

# State colours used in the graph legend
STATE_GRAPH = {
    'NORMAL':     (70,  200,  90),
    'AGGRESSIVE': (220,  55,  55),
    'WITHDRAWN':  (60,  100, 220),
    'BEAUTIFUL':  (220, 195,  50),
}

# Simulation speeds in days per second
SPEEDS = [1, 3, 7, 15, 30, 60, 120, 250]


# ── App ───────────────────────────────────────────────────────────────────────

class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Universe 25 — Mouse Utopia Simulation")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock  = pygame.time.Clock()

        self.font_s = pygame.font.SysFont("Consolas", 13)
        self.font_m = pygame.font.SysFont("Consolas", 15, bold=True)
        self.font_l = pygame.font.SysFont("Consolas", 20, bold=True)

        self.world:    World         = World()
        self.selected: object        = None   # selected Mouse or None
        self.paused:   bool          = False
        self.spd_idx:  int           = 1      # index into SPEEDS
        self.accum:    float         = 0.0
        self.last_t:   float         = time.time()

        # Persistent surface for the grid area (avoids re-filling every frame)
        self.grid_surf = pygame.Surface((GRID_W * CELL, GRID_H * CELL))

    def reset(self):
        self.world    = World()
        self.selected = None
        self.accum    = 0.0

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw_mice(self):
        surf = self.grid_surf
        surf.fill(BG)

        # Determine highest-priority state and count for each occupied cell
        prio = {State.AGGRESSIVE: 3, State.BEAUTIFUL: 2,
                State.WITHDRAWN: 1,  State.NORMAL: 0}
        cell_info = {}
        for m in self.world.mice:
            gx = max(0, min(GRID_W - 1, int(m.x)))
            gy = max(0, min(GRID_H - 1, int(m.y)))
            k  = (gx, gy)
            if k not in cell_info:
                cell_info[k] = [m.state, 1]
            else:
                cell_info[k][1] += 1
                if prio[m.state] > prio[cell_info[k][0]]:
                    cell_info[k][0] = m.state

        for (gx, gy), (state, cnt) in cell_info.items():
            color = STATE_COLORS[state]
            px    = gx * CELL + CELL // 2
            py    = gy * CELL + CELL // 2
            r     = min(CELL // 2, 2 + int(cnt ** 0.45))
            pygame.draw.circle(surf, color, (px, py), r)

        # Highlight selected mouse
        sel = self.selected
        if sel is not None and sel.alive:
            gx = int(sel.x); gy = int(sel.y)
            px = gx * CELL + CELL // 2
            py = gy * CELL + CELL // 2
            pygame.draw.circle(surf, HILIGHT, (px, py), CELL // 2 + 2, 2)

        self.screen.blit(surf, (0, 0))

    def draw_panel(self):
        ox   = GRID_W * CELL
        rect = pygame.Rect(ox, 0, PANEL_W, GRID_H * CELL)
        pygame.draw.rect(self.screen, PANEL_BG, rect)

        x = ox + 10
        y = 10
        scr = self.screen

        def blit(text, color=TXT, font=None):
            nonlocal y
            f = font or self.font_s
            scr.blit(f.render(text, True, color), (x, y))

        def sep():
            nonlocal y
            pygame.draw.line(scr, LINE_CLR, (x, y), (ox + PANEL_W - 8, y))
            y += 6

        # ── Title ─────────────────────────────────────────────────────────────
        blit("UNIVERSE  25", (220, 195, 55), self.font_l); y += 30
        blit("Mouse Utopia Simulation", TXT_DIM); y += 18
        sep()

        # ── Statistics ────────────────────────────────────────────────────────
        pop = len(self.world.mice)
        blit(f"Day:         {self.world.day:>6}", font=self.font_m); y += 22
        blit(f"Population:  {pop:>6,}", font=self.font_m); y += 22
        blit(f"Total born:  {self.world.total_born:>6,}", TXT_DIM); y += 17
        blit(f"Total died:  {self.world.total_died:>6,}", TXT_DIM); y += 18
        sep()

        # ── Phase ─────────────────────────────────────────────────────────────
        phase = self.world.detect_phase()
        blit(f"Phase: {PHASE_NAMES[phase]}", PHASE_COLORS[phase]); y += 20
        sep()

        # ── Behaviour breakdown ───────────────────────────────────────────────
        blit("Behaviour States:", TXT_DIM); y += 17
        if self.world.hist_states:
            latest = self.world.hist_states[-1]
            for sname, color in STATE_GRAPH.items():
                cnt = latest.get(sname, 0)
                pct = (cnt / pop * 100) if pop > 0 else 0.0
                pygame.draw.circle(scr, color, (x + 6, y + 6), 5)
                blit(f"  {sname:<10} {cnt:>4} ({pct:>4.1f}%)", font=self.font_s)
                y += 17
        sep()

        # ── Selected mouse info ────────────────────────────────────────────────
        blit("Selected Mouse", TXT_DIM, self.font_m); y += 18
        sel = self.selected
        if sel is not None and sel.alive:
            color = STATE_COLORS[sel.state]
            rows = [
                (f"ID:     #{sel.id}",                         TXT),
                (f"Sex:    {'Male' if sel.sex == Sex.MALE else 'Female'}",  TXT),
                (f"Age:    {sel.age} d  ({sel.age / 365:.1f} yr)",         TXT),
                (f"State:  {sel.state.name}",                  color),
                (f"Stress (instant): {sel.stress:.3f}",        TXT),
                (f"Stress (cumul.):  {sel.cum_stress:.3f}",    TXT),
            ]
            if sel.sex == Sex.FEMALE:
                if sel.is_pregnant:
                    rows.append((f"Pregnant: day {sel.preg_days}/{21}", (180, 230, 180)))
                else:
                    rows.append((f"Litters: {sel.litters}", TXT))
                rows.append((f"Children: {sel.children}", TXT))
                if sel.neglecting:
                    rows.append(("Neglecting pups!", (230, 80, 80)))
            for text, clr in rows:
                blit(text, clr); y += 16
        else:
            blit("Click a mouse to inspect", TXT_DIM); y += 16
        sep()

        # ── Controls help ─────────────────────────────────────────────────────
        blit("Controls:", TXT_DIM); y += 15
        for ctrl in [
            "SPACE  —  pause / resume",
            "+  /  -  —  adjust speed",
            "R  —  reset simulation",
            "ESC  —  quit",
        ]:
            blit(ctrl, TXT_DIM); y += 14

        # ── Speed / pause badge ───────────────────────────────────────────────
        badge_y = GRID_H * CELL - 24
        if self.paused:
            badge = "PAUSED"
            bclr  = (240, 180, 40)
        else:
            badge = f"Speed: {SPEEDS[self.spd_idx]}x  (days / s)"
            bclr  = (130, 200, 130)
        scr.blit(self.font_s.render(badge, True, bclr), (x, badge_y))

    def draw_graph(self):
        gy0  = GRID_H * CELL
        gw   = WIN_W
        pygame.draw.rect(self.screen, GRAPH_BG, pygame.Rect(0, gy0, gw, GRAPH_H))

        hist = self.world.hist_pop
        self.screen.blit(
            self.font_s.render("Population History", True, TXT_DIM),
            (50, gy0 + 3))

        if len(hist) < 2:
            return

        ml, mr, mt, mb = 50, 10, 18, 22
        gx0_ = ml;         gx1_ = gw - mr
        gy0_ = gy0 + mt;   gy1_ = gy0 + GRAPH_H - mb
        max_pop = max(max(hist), 1)
        n       = len(hist)

        # Horizontal grid lines & y-axis labels
        for pct in (0.25, 0.5, 0.75, 1.0):
            yp  = gy1_ - int(pct * (gy1_ - gy0_))
            pygame.draw.line(self.screen, LINE_CLR, (gx0_, yp), (gx1_, yp))
            lbl = self.font_s.render(str(int(pct * max_pop)), True, TXT_DIM)
            self.screen.blit(lbl, (gx0_ - lbl.get_width() - 4, yp - 7))

        def x_of(i):
            return gx0_ + int(i / (n - 1) * (gx1_ - gx0_))

        def y_of(v):
            return gy1_ - int(v / max_pop * (gy1_ - gy0_))

        # State breakdown lines
        if self.world.hist_states and len(self.world.hist_states) == n:
            for sname, color in STATE_GRAPH.items():
                spts = [(x_of(i), y_of(self.world.hist_states[i].get(sname, 0)))
                        for i in range(n)]
                pygame.draw.lines(self.screen, color, False, spts, 1)

        # Total population line (drawn on top)
        pts = [(x_of(i), y_of(v)) for i, v in enumerate(hist)]
        pygame.draw.lines(self.screen, (90, 215, 115), False, pts, 2)

        # Day axis labels
        self.screen.blit(self.font_s.render("0", True, TXT_DIM),
                         (gx0_ + 2, gy1_ + 3))
        dlbl = self.font_s.render(f"Day {self.world.day}", True, TXT_DIM)
        self.screen.blit(dlbl, (gx1_ - dlbl.get_width(), gy1_ + 3))

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                k = event.key
                if k == pygame.K_ESCAPE:
                    return False
                elif k == pygame.K_SPACE:
                    self.paused = not self.paused
                elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    self.spd_idx = min(len(SPEEDS) - 1, self.spd_idx + 1)
                elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.spd_idx = max(0, self.spd_idx - 1)
                elif k == pygame.K_r:
                    self.reset()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if mx < GRID_W * CELL and my < GRID_H * CELL:
                    gx = mx / CELL
                    gy = my / CELL
                    if self.selected is not None:
                        self.selected.selected = False
                    self.selected = self.world.get_mouse_at(gx, gy, radius=2.5)
                    if self.selected is not None:
                        self.selected.selected = True

        return True

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        running = True
        while running:
            now  = time.time()
            dt   = min(now - self.last_t, 0.10)   # cap to avoid spiral on lag
            self.last_t = now

            running = self.handle_events()

            # Advance simulation
            if not self.paused and len(self.world.mice) > 0:
                self.accum += dt * SPEEDS[self.spd_idx]
                steps = int(self.accum)
                self.accum -= steps
                for _ in range(steps):
                    self.world.step()

            # Render
            self.screen.fill(BG)
            self.draw_mice()
            self.draw_panel()
            self.draw_graph()

            # Extinction overlay
            if self.world.day > 10 and len(self.world.mice) == 0:
                msg = self.font_l.render(
                    f"EXTINCTION  —  Day {self.world.day}", True, (220, 50, 50))
                self.screen.blit(msg, (WIN_W // 2 - msg.get_width() // 2,
                                       GRID_H * CELL // 2 - 15))

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()
        sys.exit()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = App()
    app.run()


if __name__ == "__main__":
    main()
