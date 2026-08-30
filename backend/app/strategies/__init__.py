"""AURON trading strategies — ICT/SMC-based entry logic with multi-TP exits.

Each strategy receives a MarketSnapshot (price, HTF bias, FVG, order blocks, structure)
and returns a TradingSetup (entry, 3 TPs, SL, side, confidence) if conditions are met.

Available strategies:
- scalping_3tp: FVG + Order Block mitigation, 3 TPs at 30%/50%/100% RR, min 1:2 RR
- ict: (coming soon) ICT model-2000 with displacement, FVG, and liquidity sweep
- smc: (coming soon) Smart Money Concepts with change-of-character and break-of-structure
- open_range: (coming soon) London/NY session open range breakout with HTF bias
"""
