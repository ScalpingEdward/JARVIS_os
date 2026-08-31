"""Trading accounts & strategy assignment registry.

The first persistent source of truth for *which* accounts AURON manages
(prop-firm, live, demo), the prop-firm rule set each one must respect, and
*which* strategies are assigned to each account. Everything else in the
trading verticals (risk, portfolio, execution) takes account data as input --
this package is where that data is actually registered, persisted and audited.
"""
