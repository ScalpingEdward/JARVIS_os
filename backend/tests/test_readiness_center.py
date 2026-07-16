from app.readiness_center.models import CheckCategory, CheckState, DiagnosticCheckCreate, ReadinessRunCreate
from app.readiness_center.service import readiness_center_service


def setup_function() -> None:
    readiness_center_service.reset()


def test_ready_preflight_allows_advisory_launch() -> None:
    result = readiness_center_service.run(
        ReadinessRunCreate(
            checks=[
                DiagnosticCheckCreate(name="Core API", category=CheckCategory.core, state=CheckState.ready),
                DiagnosticCheckCreate(name="Database", category=CheckCategory.database, state=CheckState.ready),
                DiagnosticCheckCreate(name="Security gates", category=CheckCategory.security, state=CheckState.ready),
            ]
        )
    )
    assert result.state == CheckState.ready
    assert result.launch_allowed is True
    assert result.automatic_execution_enabled is False
    assert result.automatic_order_execution_enabled is False
    assert "MASTER Brano" in result.next_actions[0]


def test_blocked_required_check_denies_launch() -> None:
    result = readiness_center_service.run(
        ReadinessRunCreate(
            checks=[
                DiagnosticCheckCreate(name="Core API", category=CheckCategory.core, state=CheckState.ready),
                DiagnosticCheckCreate(
                    name="MT5 read-only bridge",
                    category=CheckCategory.trading,
                    state=CheckState.blocked,
                    detail="Bridge token missing",
                    remediation="Configure the MT5 bridge secret reference.",
                ),
            ]
        )
    )
    assert result.state == CheckState.blocked
    assert result.launch_allowed is False
    assert any("Bridge token missing" in blocker for blocker in result.blockers)
    assert "Configure the MT5 bridge secret reference." in result.next_actions


def test_optional_blocker_does_not_block_launch() -> None:
    result = readiness_center_service.run(
        ReadinessRunCreate(
            checks=[
                DiagnosticCheckCreate(name="Core API", category=CheckCategory.core, state=CheckState.ready),
                DiagnosticCheckCreate(name="Database", category=CheckCategory.database, state=CheckState.ready),
                DiagnosticCheckCreate(name="Mobile push", category=CheckCategory.notifications, state=CheckState.blocked, required=False),
            ]
        )
    )
    assert result.launch_allowed is True


def test_degraded_system_returns_warning_and_score() -> None:
    result = readiness_center_service.run(
        ReadinessRunCreate(
            checks=[
                DiagnosticCheckCreate(name="Core API", category=CheckCategory.core, state=CheckState.ready),
                DiagnosticCheckCreate(name="Research feed", category=CheckCategory.research, state=CheckState.degraded, detail="One source delayed"),
            ]
        )
    )
    assert result.state == CheckState.degraded
    assert result.score == 0.75
    assert result.launch_allowed is True
    assert result.warnings
