# PHOENIX v21.231 — Demo 1 Concrete Tool Adapter Registry, Capability Health & Governed Invocation

## Purpose
Close the final Demo 1 integration-debt item by binding governed PHOENIX capabilities to real in-process services instead of adapter stubs.

## Concrete capabilities
- TradingView Sync: status and alert retrieval
- Memory: governed search through the canonical persistent memory service
- Approvals: canonical approval-inbox read access
- Voice: canonical voice subsystem status
- MT5 financial execution: registered but remains approval-gated and disabled for Demo 1
- Browser/CDP TradingView control: represented explicitly as unavailable until a real local bridge is bound

## Governance
Every capability reports availability, health, risk class and approval requirement. Risk Brain hard block is authoritative. Unknown capabilities fail closed. Financial execution cannot be enabled by this module.

## Inspiration / future path
A future local TradingView desktop operator can be bound behind the `browser-cdp / tradingview.control` capability. That adapter should expose chart read, symbol/timeframe switching, replay, drawings, screenshots and Pine Script workflows through the same health and approval contract rather than bypassing it.

## Demo 1 readiness
After v21.231 the known integration-debt list is empty and runtime readiness can report `ready`. This means the bounded Demo 1 vertical slice is integrated; it does not mean every future PHOENIX capability is production-complete.

## Next
v21.232 — Demo 1 End-to-End Integration Validation, Scenario Harness & Operator Acceptance Governance.
