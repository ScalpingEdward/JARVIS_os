# Connecting n8n to AURON (no tunnel, no SaaS, everything local)

AURON's `api` service and your existing n8n container talk to each other over
one shared Docker network, `jarvis_shared`. Nothing is exposed to the
internet and no third-party automation platform is involved.

## One-time setup

1. Create the shared network (only needs to happen once on your machine):

   ```
   docker network create jarvis_shared
   ```

2. Start AURON as usual:

   ```
   docker compose up -d
   ```

   The `api` service is now attached to both `jarvis_internal` (private, talks
   to postgres/redis) and `jarvis_shared` (for reaching n8n).

3. Attach your existing n8n container to the same network:

   ```
   docker network connect jarvis_shared <your-n8n-container-name>
   ```

   Or, if n8n is defined in its own `docker-compose.yml`, add this network as
   an external network there too, the same way it's declared here.

4. In n8n, create a webhook-triggered workflow ("Webhook" node, POST) that:
   - receives `{ "request_id": ..., "image_source_ref": ..., "caption": ... }`
   - does the actual Instagram publish (Meta Graph API call using your
     existing "JARVIS INST" app credentials)
   - responds with `{ "media_id": "<the id Instagram returned>" }`

   Note the webhook path n8n gives you, e.g. `/webhook/instagram-post`.

5. Set the webhook URL for AURON via environment variable in `.env`:

   ```
   N8N_INSTAGRAM_WEBHOOK_URL=http://<your-n8n-container-name>:5678/webhook/instagram-post
   ```

   Because both containers are on `jarvis_shared`, Docker's internal DNS
   resolves `<your-n8n-container-name>` without any port needing to be
   published to your host or the internet.

## How the flow works once this is wired

1. `POST /v1/instagram/candidates` — a candidate image + caption draft is
   proposed (status: `proposed`). Nothing is sent to n8n yet.
2. You review it (via the Command Centre once that's built, or directly via
   the API for now) and call `POST /v1/instagram/candidates/{id}/decision`
   with `approved: true` (optionally editing the caption).
3. Only then can `POST /v1/instagram/candidates/{id}/publish` succeed — this
   is the one call that reaches n8n and actually posts. Calling it before
   approval returns a 409, on purpose.

No API key or Meta credential ever needs to live in AURON's code or
environment; those stay entirely inside your existing n8n workflow.
