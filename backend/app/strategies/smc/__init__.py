"""Smart Money Concepts (SMC) premium/discount strategy.

Entry: Order Block retest inside the discount (long) or premium (short) half
       of the range bracketed by the nearest opposing structure levels.
Exit: single clean target at the opposing structure level (the range's other
      side) -- no partial TPs, since the whole premise is "this is where
      smart money re-enters before running the range", not a scaled exit.
SL: below/above the order block, same buffer convention as the other
    strategies.
Min RR: 1:2

Deliberately ignores FVGs and session entirely -- the third strategy on the
shared registry, proving it out with yet another field combination
(structure_levels + order_blocks only) after scalping_3tp (FVG+OB, no
structure) and ict_silver_bullet (session+FVG+structure).
"""
