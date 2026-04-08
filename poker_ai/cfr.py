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
def cfr(game, player, reach_probs):
    # Base case: game is over, return the actual payoff for this player
    if game.is_terminal():
        return game.get_payoff(player)

    # Determine whose turn it is and what they can see (their card + betting history)
    players_turn = game.get_current_player()
    infoset_key = get_infoset_key(game, players_turn)

    # First time seeing this situation — initialize with zero regrets
    if infoset_key not in info_sets:
        info_sets[infoset_key] = {
            "regrets": [0.0, 0.0],
            "strategy_sum": [0.0, 0.0]
        }

    # Convert accumulated regrets into a strategy (higher regret = played more often)
    current_strategy = get_strategy(info_sets[infoset_key]["regrets"])
    current_actions = game.get_actions()

    # Recursively compute the expected value of each action
    # As we go deeper, update the current player's reach probability
    # to reflect how likely they were to choose this action
    action_values = []
    for i, action in enumerate(current_actions):
        new_game = copy.deepcopy(game)
        new_game.add_action(action)
        new_reach = reach_probs.copy()
        new_reach[players_turn] *= current_strategy[i]
        action_values.append(cfr(new_game, player, new_reach))

    # The value of this node is the weighted average across all actions
    node_value = sum(current_strategy[i] * action_values[i] for i in range(len(current_actions)))

    # Only update regrets and strategy at nodes where it's our turn
    if players_turn == player:
        opponent = 1 - player
        for i, action in enumerate(current_actions):
            # Regret is weighted by the opponent's reach probability:
            # "how often does the opponent put us in this situation?"
            # We exclude our own reach probability to avoid biasing against
            # actions we currently play rarely — we need to freely explore
            info_sets[infoset_key]["regrets"][i] += reach_probs[opponent] * (action_values[i] - node_value)

            # Strategy sum is weighted by our own reach probability:
            # "how often did we actually play this action?"
            # Averaging this over all iterations converges to Nash equilibrium
            info_sets[infoset_key]["strategy_sum"][i] += reach_probs[player] * current_strategy[i]

    return node_value