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
   - receives:
     ```json
     {
       "request_id": "...",
       "post_format": "single_image | carousel | reel",
       "media_items": [
         {"media_ref": "...", "media_type": "image | video", "aesthetic_score": 0.9, "duration_seconds": null}
       ],
       "edit_plan": [
         {
           "media_ref": "...",
           "target_aspect_ratio": "4:5",
           "color_grade_preset": "auron-warm-mystic-v1",
           "target_duration_seconds": null,
           "trim_needed": false,
           "trim_start_seconds": null,
           "trim_end_seconds": null,
           "notes": "Crop to 4:5 and apply the account's standard grade for feed consistency."
         }
       ],
       "caption": "..."
     }
     ```
   - executes `edit_plan` for real: crops/grades each item per `color_grade_preset` (define this preset once in your own editing tool -- AURON only sends a stable name, it does not touch pixels), and if `trim_needed` is `true` for a video, either trims it based on your own manual review (AURON deliberately never invents `trim_start_seconds`/`trim_end_seconds`) or flags it back to you before posting
   - posts as the right Instagram object based on `post_format` (single media, carousel container with all `media_items`, or Reel) via the Meta Graph API using your existing "JARVIS INST" app credentials
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

**Manual path** (still works, useful for one-off posts):
1. `POST /v1/instagram/candidates` — a candidate with one or more media items + caption is proposed (status: `proposed`). Nothing is sent to n8n yet.
2. You review it and call `POST /v1/instagram/candidates/{id}/decision` with `approved: true` (optionally editing the caption).
3. Only then can `POST /v1/instagram/candidates/{id}/publish` succeed — this is the one call that reaches n8n and actually posts. Calling it before approval returns a 409, on purpose.

**Automated path from a photo folder** (the ~100-200-photo workflow):
1. **Analyze once, in n8n (or a script with Drive access) — not in AURON.** For each new photo/video in your Drive folder, run a vision-analysis step (your existing Claude API call is fine for this) to produce: a short `theme` label (e.g. `"gold-trading-desk"`, `"mystic-symbol"`, `"quote-card"` — consistent labels are what let AURON group photos into a coherent carousel), optional `tags`, and an `aesthetic_score` (0-1, how well it fits the account's look).
2. Push the results to AURON: `POST /v1/instagram/media-pool/ingest` with a batch of `{media_ref, media_type, theme, tags, aesthetic_score, duration_seconds (video only)}`. Re-ingesting the same `media_ref` is a no-op (deduplicated), so it's safe to re-run this over the whole folder periodically.
3. Trigger curation: `POST /v1/instagram/curate` — AURON groups the *unused* pool into hero posts (a standout single image), right-sized carousels (3-6 same-theme images), and standalone Reels (every video), reserving each item so nothing gets proposed twice. Nothing is posted yet; each result is a `CuratedDraft`.
4. **A caption still needs to be attached — AURON does not write caption text itself.** This is deliberately still your existing n8n Claude-based captioning step, not duplicated inside AURON: fetch pending drafts (`GET /v1/instagram/curate/drafts`), have n8n generate a caption in your account's voice for each draft's theme/media, then call `POST /v1/instagram/curate/drafts/{draft_id}/finalize` with `{caption_draft}`. This runs the normal moderation/format/edit-plan pipeline and produces a real `ContentCandidate` (status `proposed`, unless moderation rejects it — in which case the photos are *not* consumed, so a corrected caption can be retried without burning fresh media).
5. From here it's the manual path: you approve, then publish triggers n8n.

Each photo/video is only ever used once: `mark_finalized` (step 4) permanently flags the pool items as used, and a discarded draft (`POST /v1/instagram/curate/drafts/{draft_id}/discard`, e.g. if the grouping itself was wrong) releases its photos back to the pool instead.

No API key or Meta credential ever needs to live in AURON's code or
environment; those stay entirely inside your existing n8n workflow. The
same is true for vision analysis and caption generation -- AURON works
with the structured results (theme, tags, scores, captions), never the
raw pixels or your Anthropic API key for that step.
