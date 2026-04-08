import cfr as cr
import kuhn_poker as kp

def train(iterations):
    for r in range(iterations):
        cr.cfr(kp.KuhnPoker(), 0, 1.0)
        cr.cfr(kp.KuhnPoker(), 1, 1.0)

    for key in cr.info_sets:
        avg = cr.get_average_strategy(cr.info_sets[key]["strategy_sum"])
        actions = ["p", "b"] if "b" not in key.split(":")[1] or key.split(":")[1] == "" else ["p", "c"]
        print(key, actions, avg)

train(10000)