import json

from app.assistant import brain


def _sse(events):
    return [f"data: {json.dumps(e)}" for e in events]


def test_the_stream_rebuilds_blocks_like_the_plain_api():
    events = [
        {"type": "message_start"},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "hmm"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "sig"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Einen Moment, "}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Sir."}},
        {"type": "content_block_stop", "index": 1},
        {"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use", "id": "t1", "name": "trading_status", "input": {}}},
        {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": "{\"days\": "}},
        {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": "1}"}},
        {"type": "content_block_stop", "index": 2},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use"}},
    ]
    out = list(brain._blocks_from_stream(iter(_sse(events))))
    assert [v for k, v in out if k == "text"] == ["Einen Moment, ", "Sir."]
    content, stop = out[-1][1]
    assert stop == "tool_use"
    assert content[0] == {"type": "thinking", "thinking": "hmm", "signature": "sig"}
    assert content[1]["text"] == "Einen Moment, Sir."
    assert content[2]["input"] == {"days": 1} and content[2]["name"] == "trading_status"
