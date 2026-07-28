# PHOENIX v21.149 — Quarantine Fleet Impact & Dependency Containment Governance

v21.149 evaluates the downstream impact of a quarantined governance consumer and creates a bounded, human-approved containment/fallback plan.

## Flow

`Drift Reviewed → Consumer Quarantined → Dependency Impact Evaluation → Critical Gap Detection → Containment Review → Human Approval → Fallback Ready`

## Impact model

The module records affected consumers and capabilities, identifies critical dependencies, verifies fallback readiness, and derives deterministic blast-radius, severity and residual-risk scores.

A critical dependency without a ready fallback fails closed and cannot be approved.

## Safety boundary

This module performs no external network call, no fallback activation, no route mutation, no policy mutation, no credential/permission expansion and no trading or fund movement. `fallback-ready` means the containment plan is approved for downstream governed use; it does not perform the fallback itself.

## Human control

Human approval is required both for the containment plan and separately before it can enter `fallback-ready` state. Risk Brain remains authoritative.

## Next

v21.150 should add Containment Effectiveness Observation & Quarantine Resolution Readiness Governance, observing whether the approved containment preserves required downstream capabilities and producing human-reviewed readiness for quarantine resolution.
