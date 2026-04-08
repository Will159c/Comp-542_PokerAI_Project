import random

cards = ["J", "Q", "K"];

class KuhnPoker():
    def __init__(self):
        self.deck = cards.copy();
        random.shuffle(self.deck)
        self.player_cards = [self.deck[0], self.deck[1]]
        self.history = ""

    def is_terminal(self):
        if self.history == "pp" or self.history == "bc" or self.history == "bp" or self.history == "pbp" or self.history == "pbc":
            return True 
        else:
            return False
    
    def get_current_player(self):
        if len(self.history) % 2:
            return 1
        else:
            return 0
    
    def get_actions(self):
        if self.history and self.history[-1] == "b":
            return ["p", "c"]
        else:
            return ["p", "b"]
    
    def get_payoff(self, player):
        result = self.player_cards[0] > self.player_cards[1]
        chip_results = {
            "pp": 1,
            "bc": 2,
            "pbc": 2
        }
        
        if self.history == "pbp":
            payoff = -1
        elif self.history == "bp":
            payoff = 1
        elif result:
            payoff = chip_results[self.history]
        else:
            payoff = -chip_results[self.history]
        
        if player == 0:
            return payoff
        else:
            return -payoff
    
    def add_action(self, action):
        self.history += action
