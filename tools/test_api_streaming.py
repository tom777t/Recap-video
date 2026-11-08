# -*- coding: utf-8 -*-
"""test_api_streaming.py - every synchronous API call is streamed.

  NON-STREAM-REFUSED  the real SDK refuses messages.create with a large
                      max_tokens ("Streaming is required...") - the error the
                      Furious 7 draft hit. Proves the test reproduces it.
  HELPER-STREAMS      tag_batch.create_message with the same params returns
                      the final message (text, stop_reason, usage) through a
                      stream, offline (mock HTTP transport, no key, no network)
  NO-DIRECT-CREATE    no pipeline/tools module calls client.messages.create(...)
                      directly any more; batches are unaffected

Run:  python tools/test_api_streaming.py      (exit 0 = all pass; skips if
      the anthropic SDK or httpx is not installed)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PARAMS = dict(model="claude-opus-5-5", max_tokens=32000,
              messages=[{"role": "user", "content": "x"}])


def _sse() -> bytes:
    ev = [
        ("message_start", {"type": "message_start", "message": {
            "id": "msg_t", "type": "message", "role": "assistant",
            "model": PARAMS["model"], "content": [], "stop_reason": None,
            "stop_sequence": None, "usage": {"input_tokens": 5, "output_tokens": 0}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0,
                                 "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                 "delta": {"type": "text_delta", "text": "{\"ok\": 1}"}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta",
                           "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                           "usage": {"output_tokens": 7}}),
        ("message_stop", {"type": "message_stop"}),
    ]
    return "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in ev).encode()


def _httpx():
    """The SDK's own HTTP package: httpx2 on newer SDKs, httpx on older ones."""
    try:
        import httpx2 as h
    except ImportError:
        import httpx as h
    return h


def _client():
    import anthropic
    httpx = _httpx()
    tr = httpx.MockTransport(lambda req: httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content=_sse()))
    return anthropic.Anthropic(api_key="test", http_client=httpx.Client(transport=tr))


def test_refused():
    try:
        _client().messages.create(**PARAMS)
    except ValueError as e:
        return "Streaming is required" in str(e), f"SDK refuses: {str(e)[:50]}..."
    return True, "this SDK version no longer refuses (fine - the helper still streams)"


def test_helper():
    import tag_batch as TB
    m = TB.create_message(_client(), **PARAMS)
    u = TB.usage_of(m)
    ok = (m.content[0].text == '{"ok": 1}' and m.stop_reason == "end_turn"
          and u.get("out") == 7)
    return ok, f"streamed reply '{m.content[0].text}', stop {m.stop_reason}, usage {u}"


def test_no_direct():
    bad = []
    for f in list((ROOT / "tools").glob("*.py")) + list((ROOT / "pipeline").glob("*.py")) \
            + [ROOT / "recap.py"]:
        if f.name.startswith("test_") or not f.exists():
            continue
        for i, ln in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if re.search(r"\.messages\.create\(", ln) and "def create_message" not in ln:
                if "return msgs.create(" in ln:
                    continue
                bad.append(f"{f.name}:{i}")
    return not bad, "none" if not bad else "direct calls at " + ", ".join(bad)


TESTS = {"NON-STREAM-REFUSED": test_refused, "HELPER-STREAMS": test_helper,
         "NO-DIRECT-CREATE": test_no_direct}

if __name__ == "__main__":
    try:
        import anthropic  # noqa: F401
        _httpx()
    except ImportError:
        print("test_api_streaming: SKIP (anthropic/httpx not installed)")
        sys.exit(0)
    bad = 0
    for name, fn in TESTS.items():
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"raised {type(e).__name__}: {e}"
        print(f"{'PASS' if ok else 'FAIL'}  {name:<20} {msg}")
        bad += 0 if ok else 1
    print("-" * 60)
    print(f"test_api_streaming: {bad} FAILURE(S)" if bad else "test_api_streaming: all pass")
    sys.exit(1 if bad else 0)
