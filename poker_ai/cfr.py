import copy

# Stores learned regrets and strategy sums for every situation the AI has seen
# Key: infoset string like "K:pb", Value: dict with regrets and strategy_sum lists
info_sets = {}

# Combines a player's card and the betting history into a unique key
# This represents everything a player knows at a given point in the game
def get_infoset_key(game, player):
    return game.player_cards[player] + ":" + game.history

# Converts accumulated regrets into a probability distribution over actions
# Actions with higher positive regret get played more often
# If all regrets are negative, play uniformly (equal probability for each action)
def get_strategy(regrets):
    positive_regrets = [max(r, 0) for r in regrets]
    total = sum(positive_regrets)
    if total > 0:
        return [r / total for r in positive_regrets]
    else:
        return [1 / len(regrets) for r in positive_regrets]

# Converts the accumulated strategy sum into the final average strategy
# The average strategy over all iterations converges to Nash equilibrium
def get_average_strategy(strategy_set):
    strategy_sum = sum(strategy_set)
    if strategy_sum > 0:
        return [s / strategy_sum for s in strategy_set]
    else:
        return [1 / len(strategy_set) for s in strategy_set]

# The core CFR algorithm — recursively walks through every possible game continuation
# game: current game state
# player: the player we are optimizing for
# reach_prob: how likely we were to reach this point (starts at 1.0)
def cfr(game, player, reach_prob):
    # Base case — game is over, return the actual payoff for this player
    if game.is_terminal():
        return game.get_payoff(player)
    
    # Figure out whose turn it is and what they can see
    players_turn = game.get_current_player()
    infoset_key = get_infoset_key(game, players_turn)
    
    # If this is the first time seeing this situation, initialize it with zero regrets
    if infoset_key not in info_sets:
        info_sets[infoset_key] = {
            "regrets": [0.0, 0.0],
            "strategy_sum": [0.0, 0.0]
        }
    
    # Get the current strategy for this situation based on accumulated regrets
    current_strategy = get_strategy(info_sets[infoset_key]["regrets"])
    current_actions = game.get_actions()
    
    # Simulate each possible action and record what it was worth
    action_values = []
    for i, action in enumerate(current_actions):
        new_game = copy.deepcopy(game)
        new_game.add_action(action)
        action_values.append(cfr(new_game, player, reach_prob * current_strategy[i]))
    
    # Weighted average of action values based on how often we play each action
    node_value = sum(current_strategy[i] * action_values[i] for i in range(len(current_actions)))
    
    # Update regrets and strategy sum for this infoset
    for i, action in enumerate(current_actions):
        if players_turn == player:
            info_sets[infoset_key]["regrets"][i] += reach_prob * (action_values[i] - node_value)
            info_sets[infoset_key]["strategy_sum"][i] += reach_prob * current_strategy[i]
    
    return node_value