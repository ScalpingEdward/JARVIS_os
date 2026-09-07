"""Opening Range Breakout (ORB) strategy.

Entry: price breaks out of the session's opening range (opening_range_high /
       opening_range_low on MarketSnapshot -- see models.py), with HTF bias
       not opposing the breakout direction.
Exit: single TP at the classic ORB measured move (breakout point projected
      by the range's own height).
SL: just inside the broken level itself, with a small buffer -- not the
    opposite side of the range (that would make 1:2 RR essentially
    unreachable, see strategy.py).
Min RR: 1:2

The fourth strategy on the shared registry, and the first to need new
MarketSnapshot fields (opening_range_high/opening_range_low, both optional
and defaulting to None -- every existing strategy and every existing test
snapshot is unaffected). Ignores FVGs, Order Blocks and structure_levels
entirely; the opening range is its own, self-contained edge.
"""
