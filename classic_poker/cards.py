from __future__ import annotations

import random
import time
import uuid
from typing import Any, MutableSequence

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

# Table display denominations (greedy largest-first).
CHIP_ORDER = [200, 100, 50, 25, 10]
CHIP_COLORS: dict[int, str] = {
    10: "grey",
    25: "red",
    50: "blue",
    100: "green",
    200: "black",
}

global_card_id = 0


def build_deck() -> list[dict[str, str]]:
    deck: list[dict[str, str]] = []
    for s in SUITS:
        for r in RANKS:
            deck.append({"rank": r, "suit": s, "id": f"{r}{s}"})
    return deck


def shuffle(arr: MutableSequence[dict[str, str]]) -> list[dict[str, str]]:
    a = list(arr)
    for i in range(len(a) - 1, 0, -1):
        j = random.randint(0, i)
        a[i], a[j] = a[j], a[i]
    return a


def with_card_keys(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    global global_card_id
    out: list[dict[str, Any]] = []
    for c in cards:
        d = dict(c)
        d["key"] = f"card-{global_card_id}"
        global_card_id += 1
        out.append(d)
    return out


class ShoeRef:
    current: list[dict[str, str]]


def take_from_shoe(shoe_ref: ShoeRef, n: int = 1) -> list[dict[str, Any]]:
    if len(shoe_ref.current) < n:
        shoe_ref.current = shuffle(build_deck())
    raw = shoe_ref.current[:n]
    shoe_ref.current = shoe_ref.current[n:]
    return with_card_keys(raw)


def chips_for_amount(total: int) -> list[dict[str, Any]]:
    """Greedy largest-first chip stack for display."""
    t = max(0, int(total))
    stack: list[dict[str, Any]] = []
    for d in CHIP_ORDER:
        while t >= d:
            stack.append(
                {
                    "value": d,
                    "color": CHIP_COLORS[d],
                    "id": f"c-{time.time_ns()}-{uuid.uuid4().hex[:9]}",
                }
            )
            t -= d
    return stack


def sum_stack(stack: list[dict[str, Any]]) -> int:
    return sum(c["value"] for c in stack)


# exmaple 
if __name__ == "__main__":
    shoe = ShoeRef()
    shoe.current = shuffle(build_deck())

    # Simulate real dealing
    player1 = take_from_shoe(shoe, 2)
    player2 = take_from_shoe(shoe, 2)

    burn1 = take_from_shoe(shoe, 1)
    flop = take_from_shoe(shoe, 3)

    burn2 = take_from_shoe(shoe, 1)
    turn = take_from_shoe(shoe, 1)

    burn3 = take_from_shoe(shoe, 1)
    river = take_from_shoe(shoe, 1)

    print("Flop:", " ".join(f"{c['rank']}{c['suit']}" for c in flop))
    print("Turn:", f"{turn[0]['rank']}{turn[0]['suit']}")
    print("River:", f"{river[0]['rank']}{river[0]['suit']}")
    print("Table:", " ".join(f"{c['rank']}{c['suit']}" for c in flop + turn + river))