"""A tiny OpenAI-compatible chat server on loopback, so real `zanni` subprocesses can play local seats in tests with
no model and no network. The model name says what it does:

- `write:<path>`: the first reply writes `<path>` on the stage (a one-line Python file), the next one says done;
- `slow`: never answers in time (it sleeps), for a seat killed mid-cue;
- anything else: answers "Done." at once.
"""

import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        model, messages = body["model"], body["messages"]
        self.server.calls.append(model)
        if model == "slow":
            time.sleep(60)
        message = {"role": "assistant", "content": "Done."}
        finish = "stop"
        if model.startswith("write:") and not any(m["role"] == "tool" for m in messages):
            path = model.removeprefix("write:")
            args = json.dumps({"path": path, "content": "def slugify(text):\n    return text\n"})
            message = {"role": "assistant", "content": None,
                       "tool_calls": [{"id": "call_1", "type": "function",
                                       "function": {"name": "stage_write", "arguments": args}}]}
            finish = "tool_calls"
        reply = {"id": "chatcmpl-fake", "object": "chat.completion", "created": 0, "model": model,
                 "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                 "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}}
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@contextmanager
def fake_openai():
    """Yields (base_url, calls): the server's /v1 URL, and the model names it was asked for, in order."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    server.calls = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1", server.calls
    finally:
        server.shutdown()
        server.server_close()
