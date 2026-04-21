import copy
from leduc_poker import get_infoset_key

# Stores learned regrets and strategy sums for every infoset seen
info_sets = {}


def get_strategy(regrets):
    positive_regrets = [max(r, 0) for r in regrets]
    total = sum(positive_regrets)
    if total > 0:
        return [r / total for r in positive_regrets]
    else:
        return [1 / len(regrets) for _ in regrets]


def get_average_strategy(strategy_set):
    total = sum(strategy_set)
    if total > 0:
        return [s / total for s in strategy_set]
    else:
        return [1 / len(strategy_set) for _ in strategy_set]


def cfr(game, player, reach_probs):
    if game.is_terminal():
        return game.get_payoff(player)

    players_turn = game.get_current_player()
    infoset_key = get_infoset_key(game, players_turn)
    current_actions = game.get_actions()
    num_actions = len(current_actions)

    # Initialize infoset with the correct number of actions for this node
    if infoset_key not in info_sets:
        info_sets[infoset_key] = {
            "regrets": [0.0] * num_actions,
            "strategy_sum": [0.0] * num_actions,
        }

    current_strategy = get_strategy(info_sets[infoset_key]["regrets"])

    # Recursively compute value of each action
    action_values = []
    for i, action in enumerate(current_actions):
        new_game = copy.deepcopy(game)
        new_game.add_action(action)
        new_reach = reach_probs.copy()
        new_reach[players_turn] *= current_strategy[i]
        action_values.append(cfr(new_game, player, new_reach))

    node_value = sum(current_strategy[i] * action_values[i] for i in range(num_actions))

    # Only update regrets/strategy when it's this CFR run's training player
    if players_turn == player:
        opponent = 1 - player
        for i in range(num_actions):
            info_sets[infoset_key]["regrets"][i] += (
                reach_probs[opponent] * (action_values[i] - node_value)
            )
            info_sets[infoset_key]["strategy_sum"][i] += (
                reach_probs[player] * current_strategy[i]
            )

    return node_value