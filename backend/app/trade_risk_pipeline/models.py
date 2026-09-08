from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.modules.dynamic_risk_engine.models import DynamicRiskRecord
from app.modules.execution_supervisor.models import SupervisionRecord
from app.modules.position_management_brain.models import PositionRecord
from app.executive_mt5_live_order_executor.models import LiveOrderRecord
from app.setup_submission.models import SetupSubmissionStatus


class RiskAssessmentRequest(BaseModel):
    """Optional overrides for a risk assessment run.

    Everything else (symbol, side, entry, stop, confidence, and the
    account's live balance/equity) is pulled from the already-approved
    setup and the account registry -- nothing here re-specifies the trade.
    """

    value_per_price_unit: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Account-currency value of a 1.0 price move for one standard "
            "unit of the traded instrument (i.e. pip/point value). If "
            "omitted, AURON looks up the real contract spec from the "
            "mt5_bridge terminal matched to this account for the setup's "
            "symbol and fails closed if none is available. Pass this "
            "explicitly to override."
        ),
    )
    base_risk_percent: float | None = Field(
        default=None,
        gt=0,
        le=10,
        description="Override the account's default base risk-per-trade percent.",
    )


class SupervisionStartRequest(BaseModel):
    """Optional overrides for starting position supervision."""

    timeout_seconds: int = Field(
        default=86400,
        gt=0,
        le=2_592_000,
        description=(
            "Max time this position is expected to stay open before it's "
            "flagged for review. AURON does not yet know a strategy's "
            "intended hold time, so this defaults to 24h; override per call "
            "until strategies carry their own max-hold metadata."
        ),
    )
    stale_heartbeat_seconds: int = Field(default=300, gt=0, le=86400)
    minimum_quality_score: float = Field(default=70, ge=0, le=100)
    maximum_error_rate: float = Field(default=0.2, ge=0, le=1)


class LiveOrderPrepareRequest(BaseModel):
    """Everything AURON does not yet have a fully real data source for.

    Live quotes now have a real source: if quote_bid/quote_ask/quote_age_seconds
    are all omitted, AURON looks up the freshest tick pushed by the mt5_bridge
    terminal matched to this account (by login+server) for the position's
    symbol, and fails closed if no matching terminal or no recent tick
    exists. Pass all three explicitly to override (e.g. for testing).

    Contract specs (symbol point size, volume limits) still have no real
    source and must be supplied by the caller every time.

    This only ever calls the live order executor's *create* (preflight)
    step. Actually submitting to the broker requires a separate, explicit
    call to its /execute endpoint with human_approved=True -- this pipeline
    never sets that itself.
    """

    account_login: int = Field(gt=0, description="The MT5 account login this order will be submitted under.")
    native_adapter_ready: bool = Field(
        default=False,
        description=(
            "Whether a real, connected MT5 terminal adapter is actually "
            "reachable right now. Defaults to False -- AURON cannot detect "
            "this itself; only set True from the environment that actually "
            "has the MetaTrader5 package and a logged-in terminal."
        ),
    )
    quote_bid: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Current bid. If omitted, AURON looks up the latest tick pushed "
            "by the mt5_bridge terminal matched to this account (by login+"
            "server) for this position's symbol. If no matching terminal or "
            "no recent tick exists, the call fails closed -- it never "
            "invents a quote."
        ),
    )
    quote_ask: float | None = Field(default=None, gt=0, description="Same as quote_bid but for the ask.")
    quote_age_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Age of the quote above. Only meaningful together with quote_bid/quote_ask; ignored otherwise.",
    )
    order_type: str = Field(default="market", description="market, limit, or stop.")
    symbol_point: float | None = Field(
        default=None,
        gt=0,
        description=(
            "The instrument's point size. If omitted (along with min/max "
            "volume and volume_step below), AURON looks up the real "
            "contract spec from the mt5_bridge terminal matched to this "
            "account and fails closed if none is available."
        ),
    )
    min_volume: float | None = Field(default=None, gt=0)
    max_volume: float | None = Field(default=None, gt=0)
    volume_step: float | None = Field(default=None, gt=0)
    min_stop_distance_points: int = Field(default=0, ge=0)
    max_deviation_points: int = Field(default=30, ge=0)
    approved_account_logins: list[int] | None = Field(
        default=None,
        description="Allowlist of logins this order may run under. Defaults to [account_login] only -- i.e. no other account is implicitly trusted.",
    )


class LiveOrderPrepareOverrides(BaseModel):
    """Same fields as LiveOrderPrepareRequest, minus account_login and
    approved_account_logins -- both are derived from the approved setup's
    own account record when advance_to_preflight() builds the real request,
    so the caller never has to look up a login and pass it back in."""

    native_adapter_ready: bool = False
    quote_bid: float | None = Field(default=None, gt=0)
    quote_ask: float | None = Field(default=None, gt=0)
    quote_age_seconds: float | None = Field(default=None, ge=0)
    order_type: str = "market"
    symbol_point: float | None = Field(default=None, gt=0)
    min_volume: float | None = Field(default=None, gt=0)
    max_volume: float | None = Field(default=None, gt=0)
    volume_step: float | None = Field(default=None, gt=0)
    min_stop_distance_points: int = Field(default=0, ge=0)
    max_deviation_points: int = Field(default=30, ge=0)


class AdvanceToPreflightRequest(BaseModel):
    """Optional overrides threaded through to each of the four chained
    steps assess -> open_position -> start_supervision -> prepare_live_order.
    Every field defaults to exactly what calling the four steps by hand
    with no overrides would already do."""

    assessment: RiskAssessmentRequest = Field(default_factory=RiskAssessmentRequest)
    supervision: SupervisionStartRequest = Field(default_factory=SupervisionStartRequest)
    live_order: LiveOrderPrepareOverrides = Field(default_factory=LiveOrderPrepareOverrides)


class AdvanceToPreflightResult(BaseModel):
    """Everything produced by successfully chaining all four steps for one
    approved setup. live_order.human_approved is always False here -- this
    stops in exactly the same place prepare_live_order already stops when
    called by hand. It only removes the friction of tracking
    workspace_id/risk_record_id/position_id across four separate manual
    calls; it does not remove or shortcut the human_approved gate."""

    risk_record: DynamicRiskRecord
    position: PositionRecord
    supervision: SupervisionRecord
    live_order: LiveOrderRecord


class AdvanceToPreflightFailure(BaseModel):
    """What a partial failure looks like. The records that already
    succeeded are real, persisted, and still exist -- this is a report of
    where the chain stopped and why, not a rollback. A failure at
    'prepare_live_order', for instance, still leaves a real tracked
    position under supervision; only the live-order preflight itself
    needs to be retried once the reported problem is fixed."""

    failed_at: str
    error: str
    risk_record: DynamicRiskRecord | None = None
    position: PositionRecord | None = None
    supervision: SupervisionRecord | None = None


class TradeRiskPipelineStatus(BaseModel):
    """Capability health across the whole chain, not just this module's
    own layer -- setup_submission (the approval gate everything here
    depends on) plus the three record-keeping services assess(),
    open_position(), and start_supervision() delegate to. Each of the
    three already had its own status() method (module/version/record
    count/safety_boundary), just never exposed through a route of its
    own; this is that, aggregated in the one place an operator would
    actually want to look.

    executive_mt5_live_order_executor's own status is deliberately not
    included here -- unlike the other three, it is scoped per
    workspace_id (there is no single "the executor" to summarize
    globally), and already has its own route at
    GET /v1/executive-mt5-live-order-executor/status?workspace_id=...
    """

    setup_submission: SetupSubmissionStatus
    dynamic_risk_engine: dict
    position_management: dict
    execution_supervisor: dict
