"""Agents that talk to a language model, and what they fall back to.

Nothing in here can compute a payable amount. Buyer agents turn a mission
into a basket; merchant agents turn a basket into an OfferIntent. Both
produce structured output that is validated before it is believed, and
both have a deterministic scripted strategy they drop to when the
provider is slow, unreachable, or returns something that is not a valid
intent. The negotiation always finishes.
"""
