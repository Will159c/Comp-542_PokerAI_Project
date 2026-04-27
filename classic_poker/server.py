"""
Poker web app: landing page + classic Texas Hold'em vs AI + Leduc Hold'em.

Run from project root:
  uvicorn classic_poker.server:app --reload --host 127.0.0.1 --port 8000

Open:
  http://127.0.0.1:8000/                 — game hub (landing)
  http://127.0.0.1:8000/classic-poker/   — Texas Hold'em vs AI
  http://127.0.0.1:8000/leduc-holdem/    — Leduc Hold'em vs AI
"""
from __future__ import annotations

import random
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from poker_ai import cfr as leduc_cfr
from poker_ai import train as leduc_train
from poker_ai.leduc_poker import LeducPoker, get_infoset_key

from . import cards as cardutil
from .holdem_lite import (
    STARTING_STACK,
    HoldemLiteGame,
    action_label,
    ai_choose_action,
)

CLASSIC_POKER_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = CLASSIC_POKER_ROOT.parent

sessions: dict[str, dict[str, Any]] = {}
leduc_sessions: dict[str, dict[str, Any]] = {}
_leduc_model_ready = False

CARD_VALUE = {"J": 1, "Q": 2, "K": 3}


def _ensure_leduc_model_ready() -> None:
    global _leduc_model_ready
    if _leduc_model_ready:
        return
    leduc_train.train(15000)
    _leduc_model_ready = True


def _average_strategy_for_infoset(infoset_key: str, legal_actions: list[str]) -> list[float]:
    node = leduc_cfr.info_sets.get(infoset_key)
    if node is None:
        n = len(legal_actions)
        return [1.0 / n for _ in legal_actions]
    avg = leduc_cfr.get_average_strategy(node["strategy_sum"])
    if len(avg) != len(legal_actions):
        n = len(legal_actions)
        return [1.0 / n for _ in legal_actions]
    return avg


def _leduc_action_label(action: str) -> str:
    return {
        "p": "check",
        "b": "bet",
        "c": "call",
        "r": "raise",
        "f": "fold",
    }.get(action, action)


def _leduc_audio_for_label(label: str) -> str:
    return {
        "bet": "raise",
        "raise": "raise",
        "call": "call",
        "fold": "fold",
        "check": "check",
    }.get(label, "check")


def _serialize_leduc_state(
    game: LeducPoker,
    *,
    message: str | None = None,
    audio_event: str | None = None,
    ai_action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Serialize the current Leduc state for the frontend.

    NOTE: model_info is NOT set here by default — it's attached separately by
    the action handler when appropriate (i.e., right after a human action,
    showing what the AI was about to do in response).
    """
    terminal = game.is_terminal()
    legal = [] if terminal else game.get_actions()
    current_player = -1 if terminal else game.get_current_player()

    human_card = game.player_cards[0]
    ai_card = game.player_cards[1] if terminal else None
    community = game.community

    winner: str | None = None
    payoff_human: int | None = None
    if terminal:
        payoff_human = game.get_payoff(0)
        if payoff_human > 0:
            winner = "human"
        elif payoff_human < 0:
            winner = "ai"
        else:
            winner = "tie"

    round_label = {
        0: "Preflop (round 1)",
        1: "Postflop (round 2)",
    }.get(game.current_round, f"Round {game.current_round}")

    return {
        "game": "leduc_holdem",
        "street_label": round_label,
        "current_round": game.current_round,
        "round0_history": game.history[0],
        "round1_history": game.history[1],
        "current_player": current_player,
        "human_turn": (not terminal and current_player == 0),
        "legal_actions": legal,
        "human_card": human_card,
        "human_card_value": CARD_VALUE[human_card],
        "community_card": community,
        "community_card_value": CARD_VALUE[community] if community else None,
        "opponent_card": ai_card,
        "opponent_card_value": CARD_VALUE[ai_card] if ai_card else None,
        "terminal": terminal,
        "winner": winner,
        "payoff_human": payoff_human,
        "pot_units": game.pot[0] + game.pot[1],
        "pot_human": game.pot[0],
        "pot_ai": game.pot[1],
        "dealer": game.dealer,
        "model_info": None,
        "message": message,
        "audio_event": audio_event,
        "ai_action": ai_action,
    }


def _capture_ai_response_strategy(game: LeducPoker) -> dict[str, Any] | None:
    """
    If it's the AI's turn and the hand isn't over, capture what the AI is
    about to do (its real strategy at this infoset, including its card).
    Returns None otherwise.
    """
    if game.is_terminal():
        return None
    if game.get_current_player() != 1:
        return None
    _ensure_leduc_model_ready()  # make sure training has run
    legal = game.get_actions()
    infoset = get_infoset_key(game, 1)
    probs = _average_strategy_for_infoset(infoset, legal)
    return {
        "infoset": infoset,
        "strategy_actions": legal,
        "strategy_probs": probs,
    }


def _run_leduc_ai_until_human_turn(game: LeducPoker) -> tuple[str | None, dict[str, Any] | None]:
    _ensure_leduc_model_ready()
    audio: str | None = None
    last_ai_action: dict[str, Any] | None = None

    while not game.is_terminal() and game.get_current_player() == 1:
        legal = game.get_actions()
        infoset = get_infoset_key(game, 1)
        probs = _average_strategy_for_infoset(infoset, legal)
        ai_action = random.choices(legal, weights=probs, k=1)[0]
        game.add_action(ai_action)
        label = _leduc_action_label(ai_action)
        last_ai_action = {
            "action": ai_action,
            "label": label,
            "probs": dict(zip(legal, probs)),
        }
        audio = _leduc_audio_for_label(label)
    return audio, last_ai_action


def _street_ui_name(street: str) -> str:
    return {
        "preflop": "Preflop",
        "flop": "Flop",
        "turn": "Turn",
        "river": "River",
        "showdown": "Showdown",
        "complete": "Hand complete",
    }.get(street, street)


def _run_ai_until_human_turn(game: HoldemLiteGame) -> tuple[str | None, list[dict[str, Any]]]:
    human_player = 0
    audio: str | None = None
    ai_trace: list[dict[str, Any]] = []
    while not game.is_hand_complete() and game.get_current_player() != human_player:
        acts_before = game.get_actions()
        a, bet_amt = ai_choose_action(game)
        game.add_action(a, bet_amt)
        label_amt = bet_amt if a == "b" else (game.state.pending_call_amount if a == "c" else None)
        ai_trace.append(
            {
                "action": a,
                "bet_amount": bet_amt,
                "label": action_label(a, acts_before, label_amt),
                "street_after": game.state.street,
                "street_history_after": game.state.street_history,
            }
        )
        audio = "bet" if a == "b" else "check"
    return audio, ai_trace


def _serialize_state(
    game: HoldemLiteGame,
    *,
    audio_event: str | None = None,
    ai_trace: list[dict[str, Any]] | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    st = game.state
    human_player = 0
    p = game.get_current_player()
    terminal = game.is_hand_complete()
    human_turn = not terminal and p == human_player
    actions = [] if terminal else game.get_actions()

    n_vis = game.visible_board_count()
    board_visible = [c for c in st.board[:n_vis]]

    out: dict[str, Any] = {
        "game": "texas_holdem_poker",
        "street": st.street,
        "street_label": _street_ui_name(st.street),
        "street_history": st.street_history,
        "board": board_visible,
        "board_total": 5,
        "current_player": p,
        "human_player": human_player,
        "human_turn": human_turn,
        "legal_actions": actions,
        "human_hole": st.hole[human_player],
        "opponent_hole_revealed": terminal,
        "opponent_hole": st.hole[1] if terminal else None,
        "terminal": terminal,
        "pot_chips": st.pot,
        "pot_chip_stack": cardutil.chips_for_amount(st.pot),
        "human_in_pot": st.human_wagered_hand,
        "ai_in_pot": st.ai_wagered_hand,
        "human_chips": st.stacks[human_player],
        "ai_chips": st.stacks[1 - human_player],
        "starting_stack": STARTING_STACK,
        "bet_size": st.pending_call_amount,
        "call_amount": st.pending_call_amount,
        "legal_bet_sizes": (
            game.get_legal_bet_sizes(human_player) if (human_turn and "b" in actions) else []
        ),
        "ante_each": st.ante_each,
        "message": message,
        "audio_event": audio_event,
        "ai_trace": ai_trace or [],
        "model_info": None,
    }

    if terminal:
        net = game.human_net_chips()
        out["payoff_human"] = net
        out["winner"] = st.winner
        out["finish_reason"] = st.finish_reason
    else:
        out["payoff_human"] = None
        out["winner"] = None
        out["finish_reason"] = None

    return out


class NewGameBody(BaseModel):
    pass


class NewHandBody(BaseModel):
    session_id: str


class ActionBody(BaseModel):
    session_id: str
    action: Literal["p", "b", "c"]
    bet_amount: int | None = None


class LeducNewHandBody(BaseModel):
    session_id: str


class LeducActionBody(BaseModel):
    session_id: str
    action: Literal["p", "b", "c", "r", "f"]


api_router = APIRouter()


@api_router.post("/new-game")
def new_game(_body: NewGameBody = NewGameBody()) -> dict[str, Any]:
    game = HoldemLiteGame()
    sid = uuid.uuid4().hex
    sessions[sid] = {"game": game}

    audio, ai_trace = _run_ai_until_human_turn(game)
    if audio is None:
        audio = "shuffle"

    return {
        "session_id": sid,
        "state": _serialize_state(
            game,
            audio_event=audio,
            ai_trace=ai_trace,
            message=(
                f"Texas Hold'em — you vs the AI on one board; it bets against your hand with its own hole cards. "
                f"{STARTING_STACK} chips each, antes in the pot. Preflop: your action."
            ),
        ),
    }


@api_router.post("/new-hand")
def new_hand(body: NewHandBody) -> dict[str, Any]:
    s = sessions.get(body.session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    game: HoldemLiteGame = s["game"]
    if not game.is_hand_complete():
        raise HTTPException(status_code=400, detail="Finish the current hand before starting another.")
    try:
        game.deal_next_hand()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    audio, ai_trace = _run_ai_until_human_turn(game)
    if audio is None:
        audio = "shuffle"

    return {
        "session_id": body.session_id,
        "state": _serialize_state(
            game,
            audio_event=audio,
            ai_trace=ai_trace,
            message="Next hand — antes in the pot. Preflop: your action.",
        ),
    }


@api_router.post("/action")
def player_action(body: ActionBody) -> dict[str, Any]:
    s = sessions.get(body.session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    game: HoldemLiteGame = s["game"]
    human_player = 0

    if game.is_hand_complete():
        raise HTTPException(status_code=400, detail="Hand is over; start a new hand.")
    if game.get_current_player() != human_player:
        raise HTTPException(status_code=400, detail="Not your turn.")

    actions = game.get_actions()
    if body.action not in actions:
        raise HTTPException(status_code=400, detail=f"Illegal action {body.action!r}; allowed: {actions}")

    if body.action == "b":
        if body.bet_amount is None:
            raise HTTPException(status_code=400, detail="bet_amount is required when betting")
        allowed = game.get_legal_bet_sizes(human_player)
        if body.bet_amount not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot bet {body.bet_amount} chips; legal: {allowed}",
            )
    elif body.bet_amount is not None:
        raise HTTPException(status_code=400, detail="bet_amount is only allowed when action is 'b'")

    acts_before = actions
    pending_for_msg = game.state.pending_call_amount if body.action == "c" else None
    audio: str | None = None
    if body.action == "b":
        audio = "raise"
    elif body.action == "c":
        audio = "call"
    elif body.action == "p" and "c" in actions:
        audio = "fold"
    else:
        audio = "check"

    bet_pass = body.bet_amount if body.action == "b" else None
    try:
        game.add_action(body.action, bet_pass)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    ai_trace: list[dict[str, Any]] = []

    g = game
    msg = f"You {action_label(body.action, acts_before, body.bet_amount if body.action == 'b' else pending_for_msg)}."
    street_before_ai = g.state.street

    while not g.is_hand_complete() and g.get_current_player() != human_player:
        acts = g.get_actions()
        a, bet_amt = ai_choose_action(g)
        try:
            g.add_action(a, bet_amt)
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        label_amt = bet_amt if a == "b" else (g.state.pending_call_amount if a == "c" else None)
        ai_trace.append(
            {
                "action": a,
                "bet_amount": bet_amt,
                "label": action_label(a, acts, label_amt),
                "street_after": g.state.street,
                "street_history_after": g.state.street_history,
            }
        )
        if a == "b":
            audio = "raise"
        elif a == "c":
            audio = "call"
        elif a == "p" and "c" in acts:
            audio = "fold"
        else:
            audio = "check"

    if ai_trace:
        msg += f" Opponent: {ai_trace[-1]['label']}."

    if street_before_ai != g.state.street and not g.is_hand_complete():
        msg += f" {_street_ui_name(g.state.street)} — board updated."

    if g.is_hand_complete():
        w = g.state.winner
        net = g.human_net_chips()
        why = g.state.finish_reason
        if w == "human":
            if why == "fold":
                msg += (
                    f" Opponent folded — you take the pot (+{net} chips)."
                    if net is not None and net > 0
                    else " Opponent folded — you take the pot."
                )
            else:
                msg += (
                    f" Showdown — your hand wins (+{net} chips)."
                    if net is not None and net > 0
                    else " Showdown — your hand wins the pot."
                )
        elif w == "ai":
            if why == "fold":
                msg += " You folded — opponent takes the pot."
            elif net is not None and net < 0:
                msg += f" Showdown — opponent wins (you lose {-net} chips)."
            else:
                msg += " Showdown — opponent wins the pot."
        else:
            msg += " Push — split pot at showdown."
        if net is not None and net > 0:
            audio = "win"
        elif net is not None and net < 0:
            audio = "lose"
        else:
            audio = "check"

    return {"state": _serialize_state(g, audio_event=audio, ai_trace=ai_trace, message=msg)}


@api_router.get("/state")
def get_state(session_id: str) -> dict[str, Any]:
    s = sessions.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    game: HoldemLiteGame = s["game"]
    return {"state": _serialize_state(game)}


@api_router.post("/leduc/new-game")
def leduc_new_game() -> dict[str, Any]:
    # First hand: human acts first (dealer = 0). The session tracks who deals
    # the NEXT hand so we can alternate.
    game = LeducPoker(dealer=0)
    sid = uuid.uuid4().hex
    leduc_sessions[sid] = {"game": game, "next_dealer": 1}

    if game.get_current_player() == 1:
        # Shouldn't happen with dealer=0, but kept for completeness.
        audio, ai_action = _run_leduc_ai_until_human_turn(game)
        if audio is None:
            audio = "shuffle"
        state = _serialize_leduc_state(
            game,
            audio_event=audio,
            ai_action=ai_action,
            message="Leduc Hold'em — opponent acts first this hand.",
        )
        return {"session_id": sid, "state": state}

    # Human acts first — no AI action yet, no model_info to show.
    state = _serialize_leduc_state(
        game,
        audio_event="shuffle",
        message="Leduc Hold'em — preflop. Your move.",
    )
    return {"session_id": sid, "state": state}


@api_router.post("/leduc/new-hand")
def leduc_new_hand(body: LeducNewHandBody) -> dict[str, Any]:
    s = leduc_sessions.get(body.session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Unknown session_id")

    # Pull the queued dealer for this hand and queue the alternate for next time.
    dealer = s.get("next_dealer", 0)
    s["next_dealer"] = 1 - dealer

    game = LeducPoker(dealer=dealer)
    s["game"] = game

    if game.get_current_player() == 1:
        # AI acts first this hand. Run AI loop, then return waiting for human.
        audio, ai_action = _run_leduc_ai_until_human_turn(game)
        if audio is None:
            audio = "shuffle"
        msg = "New hand — opponent acts first."
        if ai_action:
            msg += f" Opponent {ai_action['label']}."
        state = _serialize_leduc_state(
            game,
            audio_event=audio,
            ai_action=ai_action,
            message=msg,
        )
        return {"session_id": body.session_id, "state": state}

    # Human acts first — show empty model info.
    state = _serialize_leduc_state(
        game,
        audio_event="shuffle",
        message="New hand dealt — your action first.",
    )
    return {"session_id": body.session_id, "state": state}


@api_router.post("/leduc/action")
def leduc_action(body: LeducActionBody) -> dict[str, Any]:
    s = leduc_sessions.get(body.session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    game: LeducPoker = s["game"]
    if game.is_terminal():
        raise HTTPException(status_code=400, detail="Hand is over. Start a new hand.")
    if game.get_current_player() != 0:
        raise HTTPException(status_code=400, detail="Not your turn.")
    legal = game.get_actions()
    if body.action not in legal:
        raise HTTPException(
            status_code=400,
            detail=f"Illegal action {body.action!r}; allowed: {legal}",
        )

    round_before = game.current_round
    game.add_action(body.action)

    human_label = _leduc_action_label(body.action)
    audio = _leduc_audio_for_label(human_label)

    # CAPTURE the AI's response strategy *before* it acts. This is what we'll
    # show the user — what the AI was going to do in response to their action,
    # including its card.
    pre_ai_model_info = _capture_ai_response_strategy(game)

    ai_audio, ai_action = _run_leduc_ai_until_human_turn(game)
    if ai_audio is not None:
        audio = ai_audio

    msg = f"You {human_label}."
    if ai_action:
        msg += f" Opponent {ai_action['label']}."

    if round_before == 0 and game.current_round == 1 and not game.is_terminal():
        msg += f" Flop: {game.community}."

    if game.is_terminal():
        payoff = game.get_payoff(0)
        if payoff > 0:
            msg += f" You win ({payoff:+d} chips)."
            audio = "win"
        elif payoff < 0:
            msg += f" Opponent wins ({payoff:+d} chips)."
            audio = "lose"
        else:
            msg += " Tie."
            audio = "check"

    state = _serialize_leduc_state(
        game, message=msg, audio_event=audio, ai_action=ai_action
    )
    # Attach the captured pre-AI strategy: this shows what the AI was about to
    # do in response to the human's move (including its card, per user request).
    if pre_ai_model_info is not None:
        state["model_info"] = pre_ai_model_info

    return {"state": state}


@api_router.get("/leduc/state")
def leduc_state(session_id: str) -> dict[str, Any]:
    s = leduc_sessions.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    game: LeducPoker = s["game"]
    return {"state": _serialize_leduc_state(game)}


app = FastAPI(title="Poker — Comp 542")

app.mount("/sounds", StaticFiles(directory=PROJECT_ROOT / "sounds"), name="sounds")
app.mount("/images", StaticFiles(directory=PROJECT_ROOT / "images"), name="images")
app.mount("/video", StaticFiles(directory=PROJECT_ROOT / "video"), name="video")
app.mount(
    "/classic-poker/static",
    StaticFiles(directory=CLASSIC_POKER_ROOT / "web" / "static"),
    name="classic_static",
)
app.mount(
    "/classic-poker/leduc-static",
    StaticFiles(directory=CLASSIC_POKER_ROOT / "web" / "leduc"),
    name="leduc_static",
)

app.include_router(api_router, prefix="/classic-poker/api")


@app.get("/")
def landing() -> FileResponse:
    return FileResponse(CLASSIC_POKER_ROOT / "web" / "landing" / "index.html")


@app.get("/leduc-holdem/")
def leduc_holdem_page() -> FileResponse:
    return FileResponse(CLASSIC_POKER_ROOT / "web" / "leduc" / "index.html")


@app.get("/classic-poker/")
def classic_poker_page() -> FileResponse:
    return FileResponse(CLASSIC_POKER_ROOT / "web" / "static" / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}