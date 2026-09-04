"""SELLABLE Market — three merchants competing for one order.

The buyer states a mission in plain language. Three merchant agents, each
with its own commercial strategy and its own signed limits, compete for
the basket across bounded rounds. A deterministic scorer picks the winner
and the existing gateway, binding and execution machine settle it.

The load-bearing idea is in `intents.py`: a merchant's vocabulary has no
way to express a price. It offers percentages and terms; the server
computes the amount. So the negotiation can be as adversarial as it likes
without any model, on either side, ever naming a figure that money
follows.
"""
