"""
Universe 25 — Mouse Utopia Experiment Simulation
Based on John B. Calhoun's behavioral experiments (1960s–70s)

Agent-based model: each mouse is an individual agent with age, sex,
behavioral state, stress, and reproductive status. Social dynamics
(crowding → stress → behavior breakdown) drive population collapse.
"""

import random
import math
from enum import IntEnum
from typing import List, Dict, Tuple, Optional
import numpy as np

# ── Grid dimensions ────────────────────────────────────────────────────────────
GRID_W = 100   # cells wide
GRID_H = 75    # cells tall

# ── Mouse lifecycle ────────────────────────────────────────────────────────────
MATURITY_AGE    = 60    # days to sexual maturity
MAX_AGE         = 730   # maximum lifespan (~2 years)
GESTATION_DAYS  = 21    # pregnancy duration
POSTPARTUM_DAYS = 28    # rest period between litters
WEANING_AGE     = 21    # age at which pup becomes independent
LITTER_MIN      = 3
LITTER_MAX      = 8
BASE_FERTILITY  = 0.10  # daily conception probability in ideal conditions

# ── Stress & behavior ──────────────────────────────────────────────────────────
NEIGHBOR_RADIUS = 6     # cells — radius for density calculation
MAX_STRESS_POP  = 20    # mice in neighborhood → stress = 1.0
EMA_WEIGHT      = 0.03  # exponential moving avg weight for cumulative stress

# Cumulative stress thresholds for state transitions
TH_AGGRESSION = 0.45
TH_WITHDRAWAL = 0.55
TH_BEAUTIFUL  = 0.78

# ── Mortality ──────────────────────────────────────────────────────────────────
BASE_DEATH       = 0.00020  # per day baseline
STRESS_DEATH     = 0.00150  # additional per day per unit stress
AGE_ACCEL_START  = 550      # day when aging accelerates toward death
INFANT_MORT      = 0.035    # extra daily mortality for pups < WEANING_AGE
NEGLECT_MORT     = 0.35     # fraction of litter lost at birth if mother neglects

# ── Movement ──────────────────────────────────────────────────────────────────
SINK_PROB      = 0.25   # base probability to move toward denser area
BEAUTIFUL_MOVE = 0.08   # daily movement probability for "beautiful ones"


# ── Enums ─────────────────────────────────────────────────────────────────────

class Sex(IntEnum):
    MALE   = 0
    FEMALE = 1


class State(IntEnum):
    NORMAL     = 0
    AGGRESSIVE = 1
    WITHDRAWN  = 2
    BEAUTIFUL  = 3   # "The Beautiful Ones" — physically healthy, socially withdrawn


STATE_COLORS: Dict[State, Tuple[int, int, int]] = {
    State.NORMAL:     (70,  200,  90),
    State.AGGRESSIVE: (220,  55,  55),
    State.WITHDRAWN:  (60,  100, 220),
    State.BEAUTIFUL:  (220, 195,  50),
}


# ── Mouse agent ───────────────────────────────────────────────────────────────

class Mouse:
    _counter: int = 0

    def __init__(self, x: float, y: float, sex: Sex,
                 age: int = 0, born_neglected: bool = False):
        Mouse._counter += 1
        self.id    = Mouse._counter
        self.x     = float(x)
        self.y     = float(y)
        self.sex   = sex
        self.age   = age
        self.alive = True

        # Behavior
        self.state      = State.NORMAL
        self.stress     = 0.0                              # instantaneous density-based
        self.cum_stress = 0.20 if born_neglected else 0.0  # exponential moving average

        # Reproduction (females only active)
        self.is_pregnant    = False
        self.preg_days      = 0
        self.postpart_days  = POSTPARTUM_DAYS  # start ready to mate
        self.litters        = 0
        self.children       = 0
        self.neglecting     = False

        # Metadata
        self.born_day  = 0
        self.death_day: Optional[int] = None
        self.selected  = False


# ── World ─────────────────────────────────────────────────────────────────────

class World:
    def __init__(self):
        Mouse._counter = 0
        self.day        = 0
        self.mice: List[Mouse] = []
        self.total_born = 0
        self.total_died = 0

        self._mouse_map: Dict[int, Mouse]              = {}
        self._cell_map:  Dict[Tuple[int,int], List[int]] = {}
        self._prefix:    Optional[np.ndarray]          = None
        self._raw:       Optional[np.ndarray]          = None

        # History for graph
        self.hist_pop:    List[int]  = []
        self.hist_states: List[Dict] = []

        self._spawn_initial()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _spawn_initial(self):
        """Spawn 4 breeding pairs arranged near the centre."""
        cx, cy = GRID_W * 0.5, GRID_H * 0.5
        for i in range(4):
            angle = i * math.pi / 2 + math.pi / 4
            x = cx + 7 * math.cos(angle)
            y = cy + 7 * math.sin(angle)
            age = random.randint(65, 110)
            for sex in (Sex.MALE, Sex.FEMALE):
                m = Mouse(x + random.uniform(-1, 1),
                          y + random.uniform(-1, 1),
                          sex, age=age)
                self._register(m)
        self.total_born = len(self.mice)

    def _register(self, m: Mouse):
        self.mice.append(m)
        self._mouse_map[m.id] = m

    # ── Spatial index ─────────────────────────────────────────────────────────

    def _build_spatial(self):
        """Build prefix-sum density grid and cell→mouse-id map."""
        raw = np.zeros((GRID_H, GRID_W), dtype=np.int32)
        cell_map: Dict[Tuple[int,int], List[int]] = {}
        for m in self.mice:
            if m.alive:
                gx = int(max(0, min(GRID_W - 1, m.x)))
                gy = int(max(0, min(GRID_H - 1, m.y)))
                raw[gy, gx] += 1
                key = (gx, gy)
                if key not in cell_map:
                    cell_map[key] = []
                cell_map[key].append(m.id)
        self._raw     = raw
        self._prefix  = raw.cumsum(axis=0).cumsum(axis=1)
        self._cell_map = cell_map

    def _density(self, x: float, y: float, r: int = NEIGHBOR_RADIUS) -> int:
        """Count mice within a square of radius r centred on (x, y). O(1)."""
        if self._prefix is None:
            return 0
        p  = self._prefix
        gx = int(x); gy = int(y)
        x1 = max(0, gx - r);        y1 = max(0, gy - r)
        x2 = min(GRID_W - 1, gx + r); y2 = min(GRID_H - 1, gy + r)
        total = int(p[y2, x2])
        if y1 > 0: total -= int(p[y1 - 1, x2])
        if x1 > 0: total -= int(p[y2, x1 - 1])
        if y1 > 0 and x1 > 0: total += int(p[y1 - 1, x1 - 1])
        return total

    def _sink_dir(self, x: float, y: float) -> Tuple[int, int]:
        """Return unit direction toward the densest neighbouring region."""
        gx, gy     = int(x), int(y)
        best_score = -1
        best_dir   = (0, 0)
        for dx, dy in ((0, 4), (0, -4), (4, 0), (-4, 0)):
            score = self._density(gx + dx, gy + dy, r=5)
            if score > best_score:
                best_score = score
                best_dir   = (dx // 4, dy // 4)
        return best_dir

    # ── Per-mouse actions ─────────────────────────────────────────────────────

    def _move(self, m: Mouse):
        if m.state == State.BEAUTIFUL:
            if random.random() > BEAUTIFUL_MOVE:
                return
            dx, dy = random.randint(-1, 1), random.randint(-1, 1)
        elif m.state == State.WITHDRAWN:
            # Wander randomly; slight tendency away from crowds
            dx, dy = random.randint(-2, 2), random.randint(-2, 2)
        else:
            # Normal / aggressive: behavioural sink tendency grows with stress
            prob = SINK_PROB + m.cum_stress * 0.35
            if random.random() < prob:
                bd = self._sink_dir(m.x, m.y)
                dx = bd[0] + random.randint(-1, 1)
                dy = bd[1] + random.randint(-1, 1)
            else:
                dx, dy = random.randint(-2, 2), random.randint(-2, 2)
        m.x = max(0.5, min(GRID_W - 1.5, m.x + dx))
        m.y = max(0.5, min(GRID_H - 1.5, m.y + dy))

    def _update_state(self, m: Mouse, density: int):
        m.stress     = min(1.0, density / MAX_STRESS_POP)
        m.cum_stress = (1 - EMA_WEIGHT) * m.cum_stress + EMA_WEIGHT * m.stress

        if m.state == State.BEAUTIFUL:
            return   # permanent — no recovery

        cs = m.cum_stress

        if cs >= TH_BEAUTIFUL:
            prob = 0.025 if m.sex == Sex.MALE else 0.012
            if random.random() < prob:
                m.state = State.BEAUTIFUL
                return

        if cs >= TH_WITHDRAWAL:
            r = random.random()
            if m.sex == Sex.MALE:
                if   r < 0.028: m.state = State.AGGRESSIVE
                elif r < 0.042: m.state = State.WITHDRAWN
            else:
                if r < 0.032:   m.state = State.WITHDRAWN
        elif cs >= TH_AGGRESSION and m.sex == Sex.MALE:
            if random.random() < 0.013:
                m.state = State.AGGRESSIVE
        else:
            # Gradual recovery when stress drops
            if m.state in (State.AGGRESSIVE, State.WITHDRAWN):
                if random.random() < 0.007:
                    m.state = State.NORMAL

    def _check_death(self, m: Mouse) -> bool:
        if m.age >= MAX_AGE:
            return True
        p = BASE_DEATH + m.stress * STRESS_DEATH
        if m.age > AGE_ACCEL_START:
            excess = (m.age - AGE_ACCEL_START) / (MAX_AGE - AGE_ACCEL_START)
            p += excess ** 2 * 0.006
        if m.age < WEANING_AGE:
            p += INFANT_MORT
        return random.random() < p

    def _has_mate(self, f: Mouse) -> bool:
        """Check whether a suitable male is within range."""
        gx, gy = int(f.x), int(f.y)
        r = 8
        for mx in range(max(0, gx - r), min(GRID_W, gx + r + 1)):
            for my in range(max(0, gy - r), min(GRID_H, gy + r + 1)):
                for mid in self._cell_map.get((mx, my), []):
                    m = self._mouse_map.get(mid)
                    if (m and m.alive and m.id != f.id
                            and m.sex == Sex.MALE
                            and m.age >= MATURITY_AGE
                            and m.state not in (State.BEAUTIFUL, State.WITHDRAWN)):
                        return True
        return False

    def _reproduce(self, f: Mouse, density: int) -> List[Mouse]:
        """Handle pregnancy countdown, birth, and new conception."""
        pups: List[Mouse] = []
        if f.sex != Sex.FEMALE or not f.alive:
            return pups
        if f.age < MATURITY_AGE:
            return pups
        if f.state in (State.BEAUTIFUL, State.WITHDRAWN):
            return pups

        # Active pregnancy
        if f.is_pregnant:
            f.preg_days += 1
            if f.preg_days >= GESTATION_DAYS:
                f.is_pregnant    = False
                f.preg_days      = 0
                f.postpart_days  = 0
                f.litters       += 1

                crowding = min(1.0, density / MAX_STRESS_POP)
                n = max(1, int(random.randint(LITTER_MIN, LITTER_MAX)
                               * (1 - crowding * 0.6)))

                neg_prob = f.cum_stress * 0.60
                if f.state == State.AGGRESSIVE:
                    neg_prob += 0.25
                f.neglecting = random.random() < neg_prob

                for _ in range(n):
                    if f.neglecting and random.random() < NEGLECT_MORT:
                        continue   # infant killed / abandoned
                    if random.random() < 0.04:
                        continue   # stillborn
                    sex = random.choice([Sex.MALE, Sex.FEMALE])
                    p = Mouse(f.x + random.uniform(-2, 2),
                              f.y + random.uniform(-2, 2),
                              sex, age=0,
                              born_neglected=f.neglecting)
                    p.born_day = self.day
                    pups.append(p)
                    self._mouse_map[p.id] = p
                    f.children  += 1
                    self.total_born += 1
            return pups

        # Postpartum rest
        if f.postpart_days < POSTPARTUM_DAYS:
            f.postpart_days += 1
            return pups

        # Try to conceive
        if not self._has_mate(f):
            return pups

        crowding  = min(1.0, density / MAX_STRESS_POP)
        fertility = BASE_FERTILITY * max(0.0, 1 - crowding) ** 2
        if random.random() < fertility:
            f.is_pregnant = True
            f.preg_days   = 0
        return pups

    # ── Main simulation step ──────────────────────────────────────────────────

    def step(self):
        self.day += 1
        self._build_spatial()

        new_mice: List[Mouse] = []
        for m in self.mice:
            if not m.alive:
                continue
            m.age += 1
            self._move(m)
            d = self._density(m.x, m.y)
            self._update_state(m, d)
            if self._check_death(m):
                m.alive     = False
                m.death_day = self.day
                self.total_died += 1
                continue
            if m.sex == Sex.FEMALE:
                new_mice.extend(self._reproduce(m, d))

        self.mice.extend(new_mice)
        self.mice = [m for m in self.mice if m.alive]

        counts = {s: 0 for s in State}
        for m in self.mice:
            counts[m.state] += 1
        self.hist_pop.append(len(self.mice))
        self.hist_states.append({s.name: counts[s] for s in State})

    # ── Query helpers ─────────────────────────────────────────────────────────

    def get_mouse_at(self, fx: float, fy: float,
                     radius: float = 2.5) -> Optional[Mouse]:
        """Return the mouse closest to grid position (fx, fy)."""
        best, best_d = None, float('inf')
        gx, gy = int(fx), int(fy)
        ir = int(radius) + 2
        for mx in range(max(0, gx - ir), min(GRID_W, gx + ir + 1)):
            for my in range(max(0, gy - ir), min(GRID_H, gy + ir + 1)):
                for mid in self._cell_map.get((mx, my), []):
                    m = self._mouse_map.get(mid)
                    if m and m.alive:
                        d = math.hypot(m.x - fx, m.y - fy)
                        if d < best_d and d <= radius:
                            best_d = d
                            best   = m
        return best

    def detect_phase(self) -> int:
        """Return current phase: 0=Growth, 1=Stagnation, 2=BehavioralSink, 3=Collapse."""
        pop = len(self.mice)
        if pop == 0:
            return 3
        if self.day < 80 or pop < 80:
            return 0
        hist = self.hist_pop
        if len(hist) >= 60:
            trend = (hist[-1] - hist[-60]) / max(1, hist[-60])
            if trend < -0.08:
                return 3
        if self.hist_states:
            s   = self.hist_states[-1]
            abn = s.get('AGGRESSIVE', 0) + s.get('WITHDRAWN', 0) + s.get('BEAUTIFUL', 0)
            if pop > 0 and abn / pop > 0.28:
                return 2
        if pop > 400:
            return 1
        return 0
