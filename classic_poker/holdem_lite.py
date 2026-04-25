"""
Texas Hold'em poker (two players: you vs AI) for the web demo.

- Two private hole cards each, shared board (flop, turn, river), standard 52-card deck.
- The AI plays the same betting game against your hand: check or bet each street, fold or call when facing a bet.
- Board cards appear only after that street's betting is finished.
"""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from typing import Any, Literal

from . import cards as cardutil

Street = Literal["preflop", "flop", "turn", "river", "showdown", "complete"]

STARTING_STACK = 1000

# Opening bet / raise sizes (chips). Calls must match the last bet on this street.
BET_SIZES: tuple[int, ...] = (10, 25, 50, 100, 200)

RANK_ORDER = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]


def _rank_val(rank: str) -> int:
    return RANK_ORDER.index(rank) + 2  # 2..14


def _parse_card(c: dict[str, Any]) -> tuple[int, str]:
    return _rank_val(c["rank"]), c["suit"]


def _straight_high_card(ranks_with_dupes: list[int]) -> int | None:
    """Top card of straight using ace-high or wheel (returns 5 for A-2-3-4-5)."""
    uniq = sorted(set(ranks_with_dupes))
    if len(uniq) < 5:
        return None
    hi = sorted(uniq, reverse=True)
    if {14, 5, 4, 3, 2}.issubset(set(uniq)):
        return 5
    for i in range(len(hi) - 4):
        w = hi[i : i + 5]
        if all(w[j] - w[j + 1] == 1 for j in range(4)):
            return w[0]
    return None


def _best_five_of_seven(cards7: list[dict[str, Any]]) -> tuple[int, tuple[int, ...]]:
    """
    Return (category, tiebreakers) with higher tuple = stronger.
    category: 8 SF .. 0 HC
    """
    best: tuple[int, tuple[int, ...]] | None = None
    for combo in itertools.combinations(cards7, 5):
        t = _evaluate_five(combo)
        if best is None or t > best:
            best = t
    assert best is not None
    return best


def _evaluate_five(cards5: tuple[dict[str, Any], ...]) -> tuple[int, tuple[int, ...]]:
    ranks = [_rank_val(c["rank"]) for c in cards5]
    suits = [c["suit"] for c in cards5]
    flush = len(set(suits)) == 1

    cnt: dict[int, int] = {}
    for r in ranks:
        cnt[r] = cnt.get(r, 0) + 1

    st = _straight_high_card(ranks)
    straight = st is not None

    if flush and straight and st is not None:
        return (8, (st,))

    counts = sorted(cnt.values(), reverse=True)
    if counts == [4, 1]:
        quad = next(r for r, k in cnt.items() if k == 4)
        kicker = next(r for r, k in cnt.items() if k == 1)
        return (7, (quad, kicker))
    if counts == [3, 2]:
        trips = next(r for r, k in cnt.items() if k == 3)
        pair = next(r for r, k in cnt.items() if k == 2)
        return (6, (trips, pair))
    if flush:
        return (5, tuple(sorted(ranks, reverse=True)))
    if straight:
        return (4, (st,))
    if counts == [3, 1, 1]:
        trips = next(r for r, k in cnt.items() if k == 3)
        kickers = sorted((r for r, k in cnt.items() if k == 1), reverse=True)
        return (3, (trips, kickers[0], kickers[1]))
    if counts == [2, 2, 1]:
        pairs = sorted((r for r, k in cnt.items() if k == 2), reverse=True)
        kicker = next(r for r, k in cnt.items() if k == 1)
        return (2, (pairs[0], pairs[1], kicker))
    if counts == [2, 1, 1, 1]:
        pair = next(r for r, k in cnt.items() if k == 2)
        kickers = sorted((r for r, k in cnt.items() if k == 1), reverse=True)
        return (1, (pair, kickers[0], kickers[1], kickers[2]))
    return (0, tuple(sorted(ranks, reverse=True)))


def preflop_two_card_strength(hole: list[dict[str, Any]]) -> float:
    """0..1 heuristic for AI preflop."""
    if len(hole) != 2:
        return 0.35
    r1, s1 = _parse_card(hole[0])
    r2, s2 = _parse_card(hole[1])
    hi, lo = max(r1, r2), min(r1, r2)
    pair = r1 == r2
    suited = s1 == s2
    gap = hi - lo
    score = 0.0
    if pair:
        score = 0.45 + (hi / 14.0) * 0.45
    else:
        score = (hi + lo) / 28.0 * 0.35
        if suited:
            score += 0.08
        if gap <= 3:
            score += 0.06
        if hi >= 12 and lo >= 10:
            score += 0.12
    return min(1.0, max(0.0, score))


def best_hand_category(hole: list[dict[str, Any]], board: list[dict[str, Any]]) -> tuple[int, tuple[int, ...]]:
    """Best 5-of-7 category (0 high card .. 8 straight flush) and kickers."""
    if len(board) < 3:
        return (-1, ())
    return _best_five_of_seven(hole + board)


def postflop_strength(hole: list[dict[str, Any]], board: list[dict[str, Any]]) -> float:
    """
    0..1 strength for AI heuristics.

    Uses absolute made-hand rank: two pair and better must not read as ~0.25 (that caused
    absurd folds). Lower categories still scale with kickers and board overlap.
    """
    if len(board) < 3:
        return preflop_two_card_strength(hole)
    cat, kick = best_hand_category(hole, board)
    if cat < 0:
        return preflop_two_card_strength(hole)
    # Floor by category so two pair+ never looks like air (old bug: cat/8.0 → 0.25 for two pair).
    floor_by_cat = (0.14, 0.36, 0.58, 0.68, 0.74, 0.78, 0.86, 0.93, 0.97)
    base = floor_by_cat[cat]
    tie = sum(k / 14.0 for k in kick[:5]) / 5.0 * 0.06
    overlap = len({c["rank"] for c in hole} & {c["rank"] for c in board})
    return min(1.0, base + tie + 0.04 * overlap)


def street_terminal(history: str) -> bool:
    return history in ("pp", "bc", "bp", "pbp", "pbc")


def street_current_player(history: str) -> int:
    return 1 if len(history) % 2 else 0


def street_legal_actions(history: str) -> list[str]:
    if history and history[-1] == "b":
        return ["p", "c"]
    return ["p", "b"]


@dataclass
class HoldemLiteState:
    human_player: int = 0
    ai_player: int = 1
    stacks: list[int] = field(default_factory=lambda: [STARTING_STACK, STARTING_STACK])
    hole: list[list[dict[str, Any]]] = field(default_factory=list)
    board: list[dict[str, Any]] = field(default_factory=list)
    street: Street = "preflop"
    street_history: str = ""
    pot: int = 0
    human_wagered_hand: int = 0
    ai_wagered_hand: int = 0
    folded: int | None = None
    winner: str | None = None
    last_human_net: int | None = None
    finish_reason: Literal["fold", "showdown"] | None = None
    ante_each: int = 25
    pending_call_amount: int = 0


class HoldemLiteGame:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.state = HoldemLiteState()
        self._deal()

    def _post_antes(self) -> None:
        st = self.state
        a = st.ante_each
        if st.stacks[0] < a or st.stacks[1] < a:
            raise ValueError("Not enough chips to post the ante.")
        st.stacks[0] -= a
        st.stacks[1] -= a
        st.pot = a * 2
        st.human_wagered_hand = a
        st.ai_wagered_hand = a

    def _deal(self) -> None:
        deck = cardutil.shuffle(cardutil.build_deck())
        self.state.hole = [deck[0:2], deck[2:4]]
        self.state.board = deck[4:9]
        self.state.street = "preflop"
        self.state.street_history = ""
        self.state.folded = None
        self.state.winner = None
        self.state.last_human_net = None
        self.state.finish_reason = None
        self.state.human_wagered_hand = 0
        self.state.ai_wagered_hand = 0
        self.state.pot = 0
        self.state.pending_call_amount = 0
        self._post_antes()

    def deal_next_hand(self) -> None:
        if not self.is_hand_complete():
            raise ValueError("Current hand is not finished.")
        st = self.state
        st.last_human_net = None
        st.finish_reason = None
        st.folded = None
        st.winner = None
        st.street_history = ""
        st.pot = 0
        st.human_wagered_hand = 0
        st.ai_wagered_hand = 0
        st.pending_call_amount = 0
        deck = cardutil.shuffle(cardutil.build_deck())
        st.hole = [deck[0:2], deck[2:4]]
        st.board = deck[4:9]
        st.street = "preflop"
        self._post_antes()

    def is_hand_complete(self) -> bool:
        return self.state.street == "complete"

    def visible_board_count(self) -> int:
        s = self.state.street
        if s == "preflop":
            return 0
        if s == "flop":
            return 3
        if s == "turn":
            return 4
        if s == "river":
            return 5
        if s in ("showdown", "complete"):
            return 5
        return 0

    def get_current_player(self) -> int:
        if self.is_hand_complete() or self.state.folded is not None:
            return -1
        if self.state.street == "showdown":
            return -1
        return street_current_player(self.state.street_history)

    def get_legal_bet_sizes(self, player: int) -> list[int]:
        """Opening bet sizes (chips) legal for `player`: standard sizes plus full-stack all-in."""
        st = self.state
        hist = st.street_history
        if hist and hist[-1] == "b":
            return []
        if street_current_player(hist) != player:
            return []
        stack = st.stacks[player]
        sizes = [s for s in BET_SIZES if stack >= s]
        if stack > 0 and stack not in sizes:
            sizes.append(stack)
        return sorted(sizes)

    def get_actions(self) -> list[str]:
        if self.is_hand_complete() or self.state.folded is not None or self.state.street == "showdown":
            return []
        base = street_legal_actions(self.state.street_history)
        p = street_current_player(self.state.street_history)
        hist = self.state.street_history
        facing_bet = bool(hist and hist[-1] == "b")
        amt = self.state.pending_call_amount
        if facing_bet:
            if amt <= 0:
                return base
            if self.state.stacks[p] < amt:
                return ["p"]
            return base
        out: list[str] = []
        if "p" in base:
            out.append("p")
        if "b" in base and len(self.get_legal_bet_sizes(p)) > 0:
            out.append("b")
        return out if out else ["p"]

    def _apply_chip_for_action(
        self, history_before: str, action: str, bet_amount: int | None = None
    ) -> None:
        if action == "p" and history_before and history_before[-1] == "b":
            return
        if action not in ("b", "c"):
            return
        p = street_current_player(history_before)
        st = self.state
        if action == "c":
            amt = st.pending_call_amount
            if amt <= 0:
                raise ValueError("nothing to call")
        elif action == "b":
            if history_before and history_before[-1] == "b":
                raise ValueError("already facing a bet")
            if bet_amount is None:
                raise ValueError("bet amount required")
            stack = st.stacks[p]
            if bet_amount != stack and bet_amount not in BET_SIZES:
                raise ValueError("invalid bet size")
            amt = bet_amount
            st.pending_call_amount = bet_amount
        if st.stacks[p] < amt:
            raise ValueError("Not enough chips for that action.")
        st.stacks[p] -= amt
        st.pot += amt
        if p == 0:
            st.human_wagered_hand += amt
        else:
            st.ai_wagered_hand += amt

    def add_action(self, action: str, bet_amount: int | None = None) -> None:
        if action not in ("p", "b", "c"):
            raise ValueError("illegal action symbol")
        acts = self.get_actions()
        if action not in acts:
            raise ValueError("action not legal")
        h0 = self.state.street_history
        if action == "b":
            p0 = street_current_player(h0)
            if bet_amount not in self.get_legal_bet_sizes(p0):
                raise ValueError("illegal bet amount")
        self._apply_chip_for_action(h0, action, bet_amount)
        self.state.street_history += action

        if not street_terminal(self.state.street_history):
            return

        # terminal for this street
        hist = self.state.street_history
        if hist in ("bp", "pbp"):
            # folder: last actor was bettor; folder is current after adding action
            # len(history) after fold: for bp -> bettor was 0, folder 1
            self.state.finish_reason = "fold"
            if hist == "bp":
                self.state.folded = 1
                self.state.winner = "human"
            else:
                self.state.folded = 0
                self.state.winner = "ai"
            self.state.street = "complete"
            self._settle_and_record_net()
            return

        # check-check, bet-call, check-bet-call: advance street
        self._advance_street()

    def _advance_street(self) -> None:
        cur = self.state.street
        self.state.pending_call_amount = 0
        self.state.street_history = ""
        if cur == "preflop":
            self.state.street = "flop"
        elif cur == "flop":
            self.state.street = "turn"
        elif cur == "turn":
            self.state.street = "river"
        elif cur == "river":
            self.state.street = "showdown"
            self._resolve_showdown()
        else:
            self.state.street = "complete"

    def _resolve_showdown(self) -> None:
        self.state.finish_reason = "showdown"
        b = self.state.board
        h0 = _best_five_of_seven(self.state.hole[0] + b)
        h1 = _best_five_of_seven(self.state.hole[1] + b)
        if h0 > h1:
            self.state.winner = "human"
        elif h1 > h0:
            self.state.winner = "ai"
        else:
            self.state.winner = "tie"
        self.state.street = "complete"
        self._settle_and_record_net()

    def _settle_and_record_net(self) -> None:
        st = self.state
        pot, hw = st.pot, st.human_wagered_hand
        if st.winner == "human":
            st.last_human_net = pot - hw
            st.stacks[0] += pot
        elif st.winner == "ai":
            st.last_human_net = -hw
            st.stacks[1] += pot
        else:
            half = pot // 2
            st.last_human_net = half - hw
            st.stacks[0] += half
            st.stacks[1] += pot - half
        st.pot = 0
        st.human_wagered_hand = 0
        st.ai_wagered_hand = 0

    def human_net_chips(self) -> int | None:
        """Net won/lost for the human for the completed hand (after pot is settled)."""
        if not self.is_hand_complete():
            return None
        return self.state.last_human_net


def _ai_pick_bet_size(game: HoldemLiteGame, strength: float) -> int:
    """Pick a legal bet size for the current actor; bias toward mid/larger when strong."""
    p = street_current_player(game.state.street_history)
    sizes = game.get_legal_bet_sizes(p)
    assert sizes, "AI bet with no legal sizes"
    if strength >= 0.62:
        pool = [s for s in sizes if s >= 50] or sizes
    elif strength >= 0.48:
        pool = [s for s in sizes if 25 <= s <= 200] or sizes
    elif strength >= 0.40:
        pool = [s for s in sizes if s <= 100] or sizes
    else:
        pool = sizes
    return game.rng.choice(pool)


def ai_choose_action(game: HoldemLiteGame) -> tuple[str, int | None]:
    """Heuristic: bet/raise more with strong coordination; fold more when weak facing bet."""
    st = game.state
    hist = st.street_history
    legal = game.get_actions()
    p_cur = street_current_player(hist)
    hole = st.hole[p_cur]
    if st.street == "preflop":
        strength = preflop_two_card_strength(hole)
    else:
        nv = game.visible_board_count()
        strength = postflop_strength(hole, st.board[:nv])

    facing_bet = hist and hist[-1] == "b"

    if facing_bet:
        if "c" not in legal:
            return ("p", None)
        nv = game.visible_board_count()
        board_vis = st.board[:nv]
        if len(board_vis) >= 3:
            cat, _ = best_hand_category(hole, board_vis)
            # Never dump strong made hands to a single fixed bet (old strength undervalued two pair+).
            if cat >= 2:
                return ("c", None)
            if cat >= 1 and st.street == "river":
                return ("c", None)
        if strength < 0.38:
            return ("p", None) if game.rng.random() < 0.72 else ("c", None)
        if strength < 0.55:
            return ("p", None) if game.rng.random() < 0.35 else ("c", None)
        return ("c", None)

    # not facing bet: can check or bet
    if "b" not in legal:
        return ("p", None)
    # Strong made / draw — raise (bet) often
    if strength >= 0.62 and game.rng.random() < 0.78:
        return ("b", _ai_pick_bet_size(game, strength))
    if strength >= 0.48 and game.rng.random() < 0.52:
        return ("b", _ai_pick_bet_size(game, strength))
    if strength >= 0.40 and game.rng.random() < 0.22:
        return ("b", _ai_pick_bet_size(game, strength))
    if game.rng.random() < 0.62:
        return ("p", None)
    return ("b", _ai_pick_bet_size(game, strength))


def action_label(action: str, legal: list[str], bet_amount: int | None = None) -> str:
    if action == "p" and "b" in legal:
        return "check"
    if action == "p" and "b" not in legal:
        return "fold"
    if action == "b":
        if bet_amount is not None:
            return f"bet +{bet_amount}"
        return "bet"
    if action == "c":
        if bet_amount is not None:
            return f"call ({bet_amount})"
        return "call"
    return action
