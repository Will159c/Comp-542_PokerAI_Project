import random

# 6-card deck: two each of J, Q, K
cards = ["J", "J", "Q", "Q", "K", "K"]
rank = {"J": 1, "Q": 2, "K": 3}

# Fixed-limit bet sizes: 2 chips in round 0 (preflop), 4 chips in round 1 (postflop)
BET_SIZES = [2, 4]
MAX_RAISES = 2


class LeducPoker():
    def __init__(self, dealer=0):
        # `dealer` is the player who acts FIRST in this hand (0 = human, 1 = AI).
        # Default 0 keeps existing CFR training behavior unchanged.
        self.dealer = dealer

        self.deck = cards.copy()
        random.shuffle(self.deck)
        self.player_cards = [self.deck[0], self.deck[1]]
        self.community = None  # Revealed when round 1 (postflop) starts

        # Betting history per round. Round 0 = preflop, Round 1 = postflop
        # Actions: 'p' = check/call (pass), 'b' = bet, 'r' = raise, 'f' = fold
        self.history = ["", ""]
        self.current_round = 0

        # Chips each player has committed to the pot (ante of 1 each)
        self.pot = [1, 1]

        # Set to True if a player folded (lets get_payoff know who won)
        self.folded = False

    def is_terminal(self):
        # Game ends if someone folded
        if self.folded:
            return True
        # Or if round 1 (postflop) betting has finished — showdown
        if self.current_round == 1 and self._round_betting_complete(1):
            return True
        return False

    def get_current_player(self):
        # Dealer acts first in both rounds; players alternate after that.
        return (self.dealer + len(self.history[self.current_round])) % 2

    def get_actions(self):
        h = self.history[self.current_round]
        raises = self._count_raises(h)

        # No bet outstanding: can check or bet
        if h == "" or h[-1] == "p":
            return ["p", "b"]

        # There IS a bet outstanding (last action was 'b' or 'r')
        if raises < MAX_RAISES:
            return ["f", "c", "r"]  # fold, call, raise
        else:
            return ["f", "c"]  # max raises reached, can only fold or call

    def get_payoff(self, player):
        # Returns payoff from `player`'s perspective.
        if self.folded:
            folder = self._last_actor(self.current_round)
            winner = 1 - folder
        else:
            winner = self._showdown_winner()

        loser = 1 - winner
        payoff_for_winner = self.pot[loser]

        if player == winner:
            return payoff_for_winner
        else:
            return -payoff_for_winner

    def add_action(self, action):
        self.history[self.current_round] += action

        bet_size = BET_SIZES[self.current_round]
        actor = self._last_actor(self.current_round)

        if action == "f":
            self.folded = True
            return

        if action == "b":
            self.pot[actor] += bet_size

        elif action == "r":
            opp = 1 - actor
            self.pot[actor] = self.pot[opp] + bet_size

        elif action == "c":
            opp = 1 - actor
            self.pot[actor] = self.pot[opp]

        # 'p' (check) adds no chips

        # After the action, check if this round's betting is complete
        # and we need to transition to round 1 (deal the flop)
        if (not self.folded
                and self.current_round == 0
                and self._round_betting_complete(0)):
            self.community = self.deck[2]
            self.current_round = 1

    def _count_raises(self, round_history):
        return sum(1 for a in round_history if a in ("b", "r"))

    def _last_actor(self, round_idx):
        # Who made the most recent action in this round?
        # First actor in the round was `dealer`, so the most recent actor is
        # (dealer + N - 1) mod 2 after N actions.
        n = len(self.history[round_idx])
        if n == 0:
            return None
        return (self.dealer + n - 1) % 2

    def _round_betting_complete(self, round_idx):
        h = self.history[round_idx]
        if h == "":
            return False
        if h == "pp":
            return True
        if h[-1] == "c":
            return True
        if h[-1] == "f":
            return True
        return False

    def _showdown_winner(self):
        p0, p1 = self.player_cards[0], self.player_cards[1]
        if p0 == self.community and p1 != self.community:
            return 0
        if p1 == self.community and p0 != self.community:
            return 1
        if rank[p0] > rank[p1]:
            return 0
        else:
            return 1


def get_infoset_key(game, player):
    # Round 0 format:  "K:pb"              (private card : round0 history)
    # Round 1 format:  "K|Q:pb|p"          (private|community : round0|round1)
    private = game.player_cards[player]
    if game.community is None:
        return f"{private}:{game.history[0]}"
    else:
        return f"{private}|{game.community}:{game.history[0]}|{game.history[1]}"
