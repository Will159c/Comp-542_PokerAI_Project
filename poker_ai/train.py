import cfr as cr
import leduc_poker as lp


def action_labels(infoset_key):
    card_part, history_part = infoset_key.split(":")
    if "|" in history_part:
        current_history = history_part.split("|")[1]
    else:
        current_history = history_part

    if current_history == "" or current_history[-1] == "p":
        return ["p (check)", "b (bet)"]

    raises = sum(1 for a in current_history if a in ("b", "r"))
    if raises < lp.MAX_RAISES:
        return ["f (fold)", "c (call)", "r (raise)"]
    else:
        return ["f (fold)", "c (call)"]


def train(iterations):
    for r in range(iterations):
        cr.cfr(lp.LeducPoker(), 0, [1.0, 1.0])
        cr.cfr(lp.LeducPoker(), 1, [1.0, 1.0])
        if (r + 1) % 10000 == 0:
            print(f"  iteration {r+1}/{iterations}")

    print(f"\n=== Trained for {iterations} iterations ===")
    print(f"Total infosets: {len(cr.info_sets)}\n")

    sorted_keys = sorted(cr.info_sets.keys(),
                         key=lambda k: (k.count("|"), k))

    for key in sorted_keys:
        avg = cr.get_average_strategy(cr.info_sets[key]["strategy_sum"])
        labels = action_labels(key)
        probs_str = ", ".join(f"{label}={p:.3f}" for label, p in zip(labels, avg))
        print(f"{key:20s} -> {probs_str}")


if __name__ == "__main__":
    train(50000)