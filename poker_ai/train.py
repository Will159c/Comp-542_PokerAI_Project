from . import cfr as cr
from . import kuhn_poker as kp

def train(iterations, verbose=True):
    for r in range(iterations):
        cr.cfr(kp.KuhnPoker(), 0, [1.0, 1.0])
        cr.cfr(kp.KuhnPoker(), 1, [1.0, 1.0])

    if verbose:
        for key in cr.info_sets:
            avg = cr.get_average_strategy(cr.info_sets[key]["strategy_sum"])
            actions = ["p", "b"] if "b" not in key.split(":")[1] or key.split(":")[1] == "" else ["p", "c"]
            print(key, actions, avg)


if __name__ == "__main__":
    train(10000)