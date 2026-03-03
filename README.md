# Universe 25 — Mouse Utopia Simulation

A Pygame-based agent-based simulation of John B. Calhoun's famous **Universe 25** experiment, where a mouse colony with unlimited resources collapses due to social breakdown from overcrowding.

## Overview

In the original 1960s–70s experiment, mice were given:
- Unlimited food and water
- No predators or disease
- Ample nesting space
- But **finite living area**

Despite paradise-like conditions, the colony underwent behavioral collapse and eventual extinction.

## Simulation Features

- **Agent-based model** — each mouse is an individual with age, sex, stress, and behavioral state
- **Four behavioral states**: Normal, Aggressive, Withdrawn, and "The Beautiful Ones"
- **Stress-driven dynamics** — local density increases cumulative stress, triggering behavioral changes
- **Behavioral sink** — mice cluster in busy areas even when empty space exists
- **Full lifecycle** — birth, gestation, maternal neglect, aging, and death
- **Real-time visualization** — color-coded grid, population graph, and phase indicator
- **Mouse inspection** — click any mouse to view its full status

## The Four Phases

| Phase | Description |
|-------|-------------|
| **I — Growth** | Rapid population expansion, normal behavior |
| **II — Stagnation** | Growth slows, social hierarchies rigidify |
| **III — Behavioral Sink** | Aggression, withdrawal, neglect, "Beautiful Ones" emerge |
| **IV — Collapse** | Birth rate crashes, population ages and dies out |

## Controls

| Key | Action |
|-----|--------|
| `SPACE` | Pause / Resume |
| `+` / `-` | Increase / Decrease simulation speed |
| `R` | Reset simulation |
| `ESC` | Quit |
| Left-click | Select a mouse to inspect |

## Requirements

```
pygame>=2.1.0
numpy>=1.21.0
```

## Installation & Running

```bash
conda activate ml-env
cd C:\Projects\AI_Agents\MouseUtopia
pip install -r requirements.txt
python main.py
```

## Project Structure

```
MouseUtopia/
├── main.py           # Pygame app, rendering, and event handling
├── simulation.py     # Agent-based simulation engine (Mouse, World)
├── requirements.txt  # Python dependencies
└── README.md
```

## References

- Calhoun, J. B. (1962). *Population density and social pathology*. Scientific American.
- Calhoun, J. B. (1973). *Death squared: The explosive growth and demise of a mouse population*. Proceedings of the Royal Society of Medicine.
