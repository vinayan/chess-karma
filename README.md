# Chess Karma – Chess Puzzle Trainer

A desktop application for solving chess puzzles, built with **PyQt6** and **python-chess**.

![GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue)

---

## Features

| Feature | Details |
|---------|---------|
| **Puzzle sets** | Manage named collections; landing page on startup (select a set before training) |
| **Load PGN files** | Open any PGN containing one or more games / puzzles |
| **Interactive board** | Click to select a piece, click again to move; drag-and-drop also supported |
| **Move validation** | Moves are checked against the PGN solution line |
| **Auto-play opponent** | Opponent responses are played automatically after a short delay |
| **Hint system** | Shows a green arrow for the next correct move |
| **Show solution** | Applies all remaining solution moves and displays arrows |
| **Reset puzzle** | Return to the starting position at any time |
| **Puzzle navigation** | Prev / Next buttons + keyboard arrow keys |
| **Progress tracking** | Solved / Failed counters with progress bars |
| **Sound effects** | Move, capture, castle and check sounds |
| **Stockfish (optional)** | Optional engine integration for evaluation |
| **⚡ Puzzle Rush** | Timed puzzle sprints with lives – see below |

---

## Puzzle Rush

Puzzle Rush is a separate mode (menu **⚡ Rush → Start Puzzle Rush…** or `Ctrl+R`).

| Mode | Duration | End condition |
|------|----------|---------------|
| **3 Minutes** | 3-minute countdown | Time runs out or 3 mistakes |
| **5 Minutes** | 5-minute countdown | Time runs out or 3 mistakes |
| **Survival** | No time limit | 3 mistakes |

- Puzzles are **shuffled** each run for a fresh experience.
- Each **incorrect move** costs one life (❤ out of 3).
- The session ends immediately when all 3 lives are lost or time expires.
- **Top-3 scores** per mode are persisted in `~/.chess_karma_scores.json`.
- After a session the result dialog shows your score and the updated leaderboard.
- Click **Play Again** to start a new rush with the same mode, or **Back to Training** to return to normal practice.

---

## Requirements

- Python 3.10+
- [PyQt6](https://pypi.org/project/PyQt6/) (GPL licence)
- [python-chess](https://pypi.org/project/chess/)
- [Stockfish](https://stockfishchess.org/download/) *(optional – engine hints)*

---

## Installation

```bash
# 1. Clone or download the project
cd chess-karma

# 2. Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python main.py
```

### Optional: Stockfish

Download the [Stockfish binary](https://stockfishchess.org/download/) and make sure
it is on your `PATH` (or place `stockfish.exe` in one of these locations):

- `C:\Program Files\Stockfish\stockfish.exe`
- `C:\stockfish\stockfish.exe`

The application will detect it automatically on startup.

---

## Project Structure

```
chess-karma/
├── main.py                         # Entry point
├── requirements.txt
├── README.md
└── chess_karma/
    ├── __init__.py
    ├── core/
    │   ├── puzzle_manager.py       # PGN loading, move validation, progress
    │   ├── engine.py               # Stockfish wrapper
    │   ├── rush_manager.py         # Puzzle Rush session state & timer
    │   └── leaderboard.py          # Persistent top-3 scores (JSON)
    └── ui/
        ├── board_widget.py         # SVG chess board (click & drag-to-move)
        ├── puzzle_panel.py         # Train mode side panel
        ├── rush_panel.py           # Rush mode side panel (timer, lives, score)
        ├── rush_start_dialog.py    # Rush mode selection dialog
        ├── rush_result_dialog.py   # Rush end-of-session result dialog
        └── main_window.py          # Main window & Train / Rush orchestration
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+Shift+O` | Open Puzzle Sets (landing page) |
| `→` / `←` | Next / Previous puzzle (Train mode) |
| `H` | Show hint (Train mode) |
| `S` | Show solution (Train mode) |
| `R` | Reset current puzzle (Train mode) |
| `Ctrl+R` | Start Puzzle Rush |
| `Escape` | Abort active Puzzle Rush |
| `F` | Flip board |
| `M` | Toggle mute |

---

## PGN Format

Chess Karma treats each **game** in the PGN as a **puzzle**.
The mainline move sequence is the solution. Standard PGN headers
(`White`, `Black`, `Event`, `FEN`) are displayed in the info panel.

Example puzzle PGN:

```pgn
[Event "Mate in 2"]
[White "Puzzle"]
[Black "Solver"]
[FEN "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1"]

1. Bxf7+ Ke7 2. Nd5#
```

---

## Licence

Chess Karma is free software: you can redistribute it and/or modify it under the
terms of the **GNU General Public License v3** as published by the Free Software
Foundation. See [LICENSE](LICENSE) for the full text.

PyQt6 is used under the GPL licence.
python-chess is licensed under the GPL v3.