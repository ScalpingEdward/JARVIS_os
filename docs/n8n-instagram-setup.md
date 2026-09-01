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
1. **n8n's only job is fetching bytes -- AURON does the actual looking.** For each new photo (or a representative thumbnail frame for a video) in your Drive folder, n8n downloads it and calls `POST /v1/instagram/media-pool/analyze-and-ingest` with `{media_ref, media_type, image_base64 + image_media_type (or image_url), duration_seconds (video only)}`. AURON makes a real Claude vision call to actually look at the photo and derive a `theme` label (e.g. `"gold-trading-desk"`, `"mystic-symbol"`, `"quote-card"` — consistent labels are what let AURON group photos into a coherent carousel), `tags`, and a real `aesthetic_score` (0-1, judged from composition/lighting/coherence with the account's look, not guessed). Each item's outcome comes back individually, so one bad photo never blocks the rest of a 100-200-item batch. Video is analyzed via its thumbnail frame only -- Claude's vision reads a still image, not motion or audio, so treat a video's score/theme as a proxy from that one frame.
2. Re-running this over the same folder is safe: `analyze-and-ingest` still calls the same deduplication-by-`media_ref` logic as plain `ingest` underneath.
3. Trigger curation: `POST /v1/instagram/curate` — AURON groups the *unused* pool into hero posts (a standout single image), right-sized carousels (3-6 same-theme images), and standalone Reels (every video), reserving each item so nothing gets proposed twice. Nothing is posted yet; each result is a `CuratedDraft`.
4. **AURON writes the caption itself too.** Call `POST /v1/instagram/curate/drafts/{draft_id}/finalize` with an empty body (or omit `caption_draft`), and AURON makes a real Anthropic API call to write the caption + hashtags in the account's voice, then runs it through the normal moderation/format/edit-plan pipeline. You can still pass `caption_draft` explicitly to skip generation for a one-off post -- both paths produce a real `ContentCandidate` (status `proposed`, unless moderation rejects it — in which case the photos are *not* consumed, so a retry doesn't burn fresh media).

   Set the API key once in `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   AURON_CAPTION_MODEL=claude-sonnet-5   # optional, this is the default
   AURON_VISION_MODEL=claude-sonnet-5    # optional, this is the default
   ```

With this path, n8n's Instagram role shrinks to three mechanical steps: fetch bytes from Drive, forward them to AURON, and (after your approval) call the Meta Graph API to actually post. Every judgment call -- what a photo is, whether it fits the account, how to group it, what to write about it -- happens in AURON.
5. From here it's the manual path: you approve, then publish triggers n8n.

Each photo/video is only ever used once: `mark_finalized` (step 4) permanently flags the pool items as used, and a discarded draft (`POST /v1/instagram/curate/drafts/{draft_id}/discard`, e.g. if the grouping itself was wrong) releases its photos back to the pool instead.

No Meta credential ever needs to live in AURON's code or environment --
posting itself stays entirely inside your existing n8n workflow, and so
does fetching the raw files from Drive (AURON never holds a Drive
credential either). Vision analysis and caption generation both now run
inside AURON, using its own `ANTHROPIC_API_KEY` -- since that's Anthropic's
own API rather than a third-party credential, and it's the same key you'd
already trust Claude with elsewhere in this project. The plain
`POST /v1/instagram/media-pool/ingest` endpoint (pre-analyzed items, no
vision call) still exists too, for cases where you already have
theme/tags/aesthetic_score from somewhere else.
