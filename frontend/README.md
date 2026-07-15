# PHOENIX Command Center

Responsive holographic-style operator interface for the JARVIS_os backend.

## Run locally

```bash
cd frontend
python -m http.server 3000
```

Open `http://localhost:3000`. The UI expects the backend at `http://localhost:8000`. A different backend URL can be configured in the browser console:

```js
localStorage.setItem('phoenix_api', 'https://your-secure-api.example')
location.reload()
```

## Connected modules

- Trading advisory and risk status
- Vision and live-feed status
- Voice identity and wake name
- Agent/orchestrator status
- Human approval center
- Roadmap and system log presentation

## Safety

The interface is operator-facing and advisory. It does not place trades, merge code, expose secrets, or bypass approval gates.