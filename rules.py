# Poker hand rankings
# defines order of hand types 

from __future__ import annotations

from typing import Final

# Ordered from strongest to weakest hand 
poker_hand_rankings: Final[list[str]] = [
    "Royal Flush",
    "Straight Flush",
    "Four of a Kind",
    "Full House",
    "Flush",
    "Straight",
    "Three of a Kind",
    "Two Pair",
    "One Pair",
    "High Card",
]

# Numeric scores (higher is better), useful for comparisons.
HAND_STRENGTH: Final[dict[str, int]] = {
    name: len(poker_hand_rankings) - idx
    for idx, name in enumerate(poker_hand_rankings)
}


def hand_strength(hand_name: str) -> int:
    """
    Return numeric strength of a hand rank name.

    Example:
        hand_strength("Flush") > hand_strength("Straight")
    """
    normalized = hand_name.strip().title()
    if normalized not in HAND_STRENGTH:
        valid = ", ".join(poker_hand_rankings)
        raise ValueError(f"Unknown hand '{hand_name}'. Valid hands: {valid}")
    return HAND_STRENGTH[normalized]


def hand_beats(hand_a: str, hand_b: str) -> bool:
    # True if `hand_a` outranks `hand_b`.
    return hand_strength(hand_a) > hand_strength(hand_b)


def compare_hands(hand_a: str, hand_b: str) -> int:
    """
    Compare two hand rank names.

    Returns:
        1  if hand_a wins
        -1 if hand_b wins
        0  if same hand category (tie category; kickers not considered here)
    """
    a = hand_strength(hand_a)
    b = hand_strength(hand_b)
    if a > b:
        return 1
    if b > a:
        return -1
    return 0
