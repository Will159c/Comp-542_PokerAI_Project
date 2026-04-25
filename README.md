# Comp-542_PokerAI_Project

## What is in `poker_ai`

- **`poker_ai/kuhn_poker.py`** — `KuhnPoker` game state: cards `J`/`Q`/`K`, history string, legal actions `p`/`b`/`c`, terminal checks, and `get_payoff`.
- **`poker_ai/cfr.py`** — CFR training and the learned policy: global `info_sets`, `get_infoset_key`, `get_average_strategy`, and `cfr(...)`.
- **`poker_ai/train.py`** — Terminal training loop: runs `cfr` for many sampled games and prints average strategies when run as a script.

Training from the terminal (prints all infosets):

```bash
python -m poker_ai.train
```

## Web UI (localhost)

**FastAPI** lives in **`classic_poker/server.py`**. It serves a small **landing hub**, the **classic Texas Hold'em vs AI** game (HTML/CSS/JS + JSON API), and a **playable Leduc Hold'em page** backed by `poker_ai` Kuhn/CFR logic.

### Setup

```bash
cd /path/to/Comp-542_PokerAI_Project
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run

From the project root, either:

```bash
uvicorn classic_poker.server:app --reload --host 127.0.0.1 --port 8000
```

or (thin wrapper):

```bash
uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

### URLs

| URL | Content |
|-----|---------|
| **http://127.0.0.1:8000/** | Landing hub with links to variants |
| **http://127.0.0.1:8000/classic-poker/** | Texas Hold'em vs AI (oval table, chips, all-in, etc.) |
| **http://127.0.0.1:8000/leduc-holdem/** | Poker Leduc Hold'em — playable localhost UI |

**Sounds** and **images** stay at the project root (`sounds/`, `images/`) and are mounted at `/sounds/…` and `/images/…`.

### Classic Hold'em API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/classic-poker/api/new-game` | New session + first state |
| `POST` | `/classic-poker/api/new-hand` | Body `{"session_id": "…"}` |
| `POST` | `/classic-poker/api/action` | Body `{"session_id": "…", "action": "p"\|"b"\|"c", "bet_amount": …}` |
| `GET` | `/classic-poker/api/state?session_id=…` | Current state |

### Leduc Hold'em API (uses `poker_ai` logic)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/classic-poker/api/leduc/new-game` | New Leduc/Kuhn session + first state |
| `POST` | `/classic-poker/api/leduc/new-hand` | Body `{"session_id": "…"}` |
| `POST` | `/classic-poker/api/leduc/action` | Body `{"session_id": "…", "action": "p"\|"b"\|"c"}` |
| `GET` | `/classic-poker/api/leduc/state?session_id=…` | Current Leduc state |

### Package layout (`classic_poker/`)

- **`cards.py`** — deck, chip display helpers.
- **`holdem_lite.py`** — two-player Hold'em rules and AI heuristics.
- **`server.py`** — FastAPI app, routes above, static mounts.
- **`web/static/`** — Hold'em UI (`index.html`, `app.js`, `style.css`).
- **`web/landing/`** — Hub `index.html`.
- **`web/leduc/`** — Leduc UI (`index.html`, `app.js`, `style.css`) using `poker_ai` model outputs.

There is no separate frontend server; everything is served from **uvicorn** on port **8000** by default.
