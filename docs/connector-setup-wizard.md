# PHOENIX Connector Setup Wizard

The setup wizard prepares connectors without storing raw credentials in the PHOENIX database.

## Workflow

1. Create a setup session for a connector kind.
2. Review and explicitly confirm requested permissions.
3. Configure one supported authentication method:
   - `environment_secret` for Telegram, GitHub and API tokens
   - `oauth2` for Gmail and Google Calendar
   - `local_path` for Obsidian and approved local folders
   - `bridge` for MT5, TradingView, MCP and local services
4. Run the connection validation.
5. Finalize only after validation succeeds.

## Secret policy

Only references such as `env:TELEGRAM_BOT_TOKEN` are accepted. Raw tokens, passwords and OAuth authorization codes are not persisted. OAuth tokens must be written to an external secret store or environment by the deployment layer.

## Safety boundaries

- Permission confirmation is mandatory.
- OAuth state values expire after ten minutes.
- Connector finalization requires a successful test.
- MT5 and TradingView order execution remain disabled.
- Automatic GitHub merge remains disabled.

## Command Center integration

The Command Center can use `GET /v1/connector-setup/status` and the setup-session endpoints to display progress, missing requirements and connection-test results.
