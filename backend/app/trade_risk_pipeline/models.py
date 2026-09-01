from __future__ import annotations

from pydantic import BaseModel, Field


class RiskAssessmentRequest(BaseModel):
    """Optional overrides for a risk assessment run.

    Everything else (symbol, side, entry, stop, confidence, and the
    account's live balance/equity) is pulled from the already-approved
    setup and the account registry -- nothing here re-specifies the trade.
    """

    value_per_price_unit: float = Field(
        default=1.0,
        gt=0,
        description=(
            "Account-currency value of a 1.0 price move for one standard "
            "unit of the traded instrument (i.e. pip/point value). AURON "
            "does not yet track per-instrument contract specs, so this "
            "must be supplied by the caller until that exists; the default "
            "of 1.0 is almost certainly wrong for anything but a sanity "
            "check and should not be relied on for real sizing."
        ),
    )
    base_risk_percent: float | None = Field(
        default=None,
        gt=0,
        le=10,
        description="Override the account's default base risk-per-trade percent.",
    )
