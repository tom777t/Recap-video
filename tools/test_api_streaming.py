# -*- coding: utf-8 -*-
"""test_api_streaming.py - every synchronous API call is streamed.

  NON-STREAM-REFUSED  the real SDK refuses messages.create with a large
                      max_tokens ("Streaming is required...") - the error the
                      Furious 7 draft hit. Proves the test reproduces it.
  HELPER-STREAMS      tag_batch.create_message with the same params returns
                      the final message (text, stop_reason, usage) through a
                      stream, offline (mock HTTP transport, no key, no network)
  DROP-RETRIED        a stream cut MID-REPLY ("peer closed connection without
                      sending complete message body" - furious72015 plan,
                      17 Nov) is made again and returns the full reply; a
                      400 is raised at once, never retried
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


def test_drop_retried():
    import anthropic
    import tag_batch as TB
    httpx = _httpx()
    body = _sse()
    n = {"req": 0}

    class Cut(httpx.SyncByteStream):
        def __iter__(self):
            yield body[: len(body) // 3]
            raise httpx.RemoteProtocolError(
                "peer closed connection without sending complete message "
                "body (incomplete chunked read)")

    def handler(req):
        n["req"] += 1
        if n["req"] == 1:
            return httpx.Response(200, headers={
                "content-type": "text/event-stream"}, stream=Cut())
        return httpx.Response(200, headers={
            "content-type": "text/event-stream"}, content=body)
    c = anthropic.Anthropic(api_key="test", max_retries=0,
                            http_client=httpx.Client(
                                transport=httpx.MockTransport(handler)))
    sleep, TB.time.sleep = TB.time.sleep, (lambda s: None)
    try:
        m = TB.create_message(c, **PARAMS)
        first = n["req"]
        n["req"] = 0
        bad = anthropic.Anthropic(api_key="test", max_retries=0,
                                  http_client=httpx.Client(
                                      transport=httpx.MockTransport(
                                          lambda r: (n.__setitem__(
                                              "req", n["req"] + 1),
                                              httpx.Response(400, json={
                                                  "type": "error", "error": {
                                                      "type": "invalid_request_error",
                                                      "message": "bad"}}))[1])))
        raised = False
        try:
            TB.create_message(bad, **PARAMS)
        except anthropic.BadRequestError:
            raised = True
    finally:
        TB.time.sleep = sleep
    ok = (m.content[0].text == '{"ok": 1}' and first == 2 and raised
          and n["req"] == 1)
    return ok, (f"cut mid-reply -> retried, full reply after {first} "
                f"request(s); a 400 raised after {n['req']} request"
                if ok else f"text {m.content[0].text!r}, first {first}, "
                f"400 raised {raised} after {n['req']}")


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
         "DROP-RETRIED": test_drop_retried,
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
