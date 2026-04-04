from pokerkit import (
     Automation,
     NoLimitTexasHoldem,
     Folding,
     CheckingOrCalling,
     CompletionBettingOrRaisingTo
)

state = NoLimitTexasHoldem.create_state(
    
    # Automate everything except player actions.
    # Manual:
    # - Standing pat
    # - Discarding
    # - Folding
    # - Checking
    # - Calling
    # - Posting bring-in
    # - Completing
    # - Betting
    # - Raising
    # - Selecting the number of runouts (cash-game only)
    (
         Automation.ANTE_POSTING,
        Automation.BET_COLLECTION,
        Automation.BLIND_OR_STRADDLE_POSTING,
        Automation.CARD_BURNING,
        Automation.HOLE_DEALING,
        Automation.BOARD_DEALING,
        Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
        Automation.HAND_KILLING,
        Automation.CHIPS_PUSHING,
        Automation.CHIPS_PULLING,
    ),
    True,  # False for big blind ante, True otherwise
    500,  # ante
    (1000, 2000),  # blinds or straddles
    2000,  # min bet
    (1125600, 2000000, 553500),  # starting stacks
    3,  # number of players
)

while state.status:
    player = state.actor_index
    print(f"Board: {state.board_cards} and Pot: {state.total_pot_amount}")
    print(f"Player {player}'s Turn with Hand: {state.hole_cards[player]}")
    
    if player is None:
        break

    if state.can_check_or_call():
        state.check_or_call() 
    elif state.can_fold():
        state.fold()
    else:
        # This handles cases like being all-in
        break

print("Hand finished!")
print(f"Payoffs: {state.payoffs}")