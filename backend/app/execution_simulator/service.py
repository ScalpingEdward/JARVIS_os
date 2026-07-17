from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ExecutionReport,
    FillRecord,
    OrderSide,
    OrderState,
    OrderType,
    SimulationOrderCreate,
    SimulationOrderRecord,
    SimulatorStatus,
)


class ExecutionSimulatorService:
    def __init__(self) -> None:
        self._orders: dict[UUID, SimulationOrderRecord] = {}

    def status(self) -> SimulatorStatus:
        return SimulatorStatus()

    def create(self, payload: SimulationOrderCreate) -> SimulationOrderRecord:
        executable = self._is_executable(payload)
        warnings: list[str] = []
        if payload.execution_profile.latency_ms > 1_000:
            warnings.append("High simulated broker latency")
        if payload.execution_profile.slippage_points > 30:
            warnings.append("High simulated slippage")

        if not executable:
            record = SimulationOrderRecord(
                symbol=payload.symbol.upper(),
                side=payload.side,
                order_type=payload.order_type,
                requested_volume=payload.volume,
                requested_price=payload.requested_price,
                state=OrderState.PENDING,
                latency_ms=payload.execution_profile.latency_ms,
                warnings=warnings + ["Trigger condition not reached"],
            )
            self._orders[record.id] = record
            return record

        fill_fraction = 1.0
        if payload.execution_profile.partial_fill_probability >= 0.5:
            fill_fraction = 0.5
            warnings.append("Simulated partial fill")

        filled_volume = round(payload.volume * fill_fraction, 4)
        direction = 1 if payload.side == OrderSide.BUY else -1
        fill_price = payload.market_price + (
            direction * payload.execution_profile.slippage_points * payload.point_size
        )
        commission = filled_volume * payload.execution_profile.commission_per_lot
        fill = FillRecord(
            volume=filled_volume,
            price=round(fill_price, 8),
            slippage_points=payload.execution_profile.slippage_points,
            commission=round(commission, 2),
            filled_at=datetime.now(timezone.utc),
        )
        state = OrderState.FILLED if fill_fraction == 1 else OrderState.PARTIALLY_FILLED
        record = SimulationOrderRecord(
            symbol=payload.symbol.upper(),
            side=payload.side,
            order_type=payload.order_type,
            requested_volume=payload.volume,
            filled_volume=filled_volume,
            requested_price=payload.requested_price,
            average_fill_price=fill.price,
            state=state,
            latency_ms=payload.execution_profile.latency_ms,
            fills=[fill],
            warnings=warnings,
        )
        self._orders[record.id] = record
        return record

    @staticmethod
    def _is_executable(payload: SimulationOrderCreate) -> bool:
        if payload.order_type == OrderType.MARKET:
            return True
        assert payload.trigger_price is not None
        if payload.order_type == OrderType.LIMIT:
            return (
                payload.market_price <= payload.trigger_price
                if payload.side == OrderSide.BUY
                else payload.market_price >= payload.trigger_price
            )
        return (
            payload.market_price >= payload.trigger_price
            if payload.side == OrderSide.BUY
            else payload.market_price <= payload.trigger_price
        )

    def list_all(self) -> list[SimulationOrderRecord]:
        return list(self._orders.values())

    def get(self, order_id: UUID) -> SimulationOrderRecord | None:
        return self._orders.get(order_id)

    def cancel(self, order_id: UUID) -> SimulationOrderRecord | None:
        record = self._orders.get(order_id)
        if record is None:
            return None
        if record.state == OrderState.PENDING:
            record.state = OrderState.CANCELLED
        return record

    def report(self) -> ExecutionReport:
        orders = self.list_all()
        fills = [fill for order in orders for fill in order.fills]
        return ExecutionReport(
            total_orders=len(orders),
            filled_orders=sum(o.state in {OrderState.FILLED, OrderState.PARTIALLY_FILLED} for o in orders),
            rejected_orders=sum(o.state == OrderState.REJECTED for o in orders),
            total_requested_volume=round(sum(o.requested_volume for o in orders), 4),
            total_filled_volume=round(sum(o.filled_volume for o in orders), 4),
            average_latency_ms=(sum(o.latency_ms for o in orders) / len(orders)) if orders else 0,
            average_slippage_points=(sum(f.slippage_points for f in fills) / len(fills)) if fills else 0,
            total_commission=round(sum(f.commission for f in fills), 2),
        )


execution_simulator_service = ExecutionSimulatorService()
