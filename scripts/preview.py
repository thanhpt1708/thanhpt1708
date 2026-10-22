#!/usr/bin/env python3
"""Local preview of the GitHub profile README.

Renders README.md through GitHub's own Markdown API (via the `gh` CLI), wraps it
in GitHub's markdown CSS, and serves it with live reload whenever the file changes.

Usage:
    python3 scripts/preview.py [--port 8000] [--file README.md]
"""

import argparse
import http.server
import json
import mimetypes
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent

PAGE = """<!doctype html>
<html lang="en" data-theme="{theme}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Profile preview</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown.min.css">
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin: 0; background: #ffffff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
  @media (prefers-color-scheme: dark) {{ body {{ background: #0d1117; }} }}
  .bar {{ display: flex; gap: 8px; justify-content: flex-end; padding: 8px 16px; font-size: 13px; }}
  .bar a {{ color: #2c9cdb; }}
  .layout {{ max-width: 1012px; margin: 0 auto; padding: 16px; display: flex; gap: 24px; }}
  .side {{ width: 260px; flex-shrink: 0; }}
  .side img {{ width: 100%; border-radius: 50%; border: 1px solid #30363d; }}
  .side h1 {{ font-size: 24px; margin: 12px 0 0; color: #8b949e; }}
  .main {{ flex: 1; min-width: 0; border: 1px solid #30363d; border-radius: 6px; padding: 24px; }}
  .main .label {{ font-size: 12px; color: #8b949e; margin-bottom: 12px; }}
  @media (max-width: 768px) {{ .layout {{ flex-direction: column; }} .side {{ width: 120px; }} }}
</style>
</head>
<body>
<div class="bar">Theme follows your OS · <span id="status">watching {file}</span></div>
<div class="layout">
  <aside class="side">
    <img src="https://github.com/{user}.png" alt="avatar">
    <h1>{user}</h1>
  </aside>
  <section class="main">
    <div class="label">{user} / README.md</div>
    <article class="markdown-body">{body}</article>
  </section>
</div>
<script>
  let version = {version};
  setInterval(async () => {{
    try {{
      const r = await fetch('/__version');
      const v = (await r.json()).version;
      if (v !== version) location.reload();
    }} catch (e) {{ document.getElementById('status').textContent = 'server stopped'; }}
  }}, 1000);
</script>
</body>
</html>"""


class State:
    html = ""
    version = 0


def render(md_path: Path, user: str, repo: str) -> str:
    """Render Markdown with GitHub's API so output matches github.com."""
    result = subprocess.run(
        ["gh", "api", "markdown", "-f", f"text={md_path.read_text()}",
         "-f", "mode=gfm", "-f", f"context={user}/{repo}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return f"<pre>gh api markdown failed:\n{result.stderr}</pre>"
    return result.stdout


def watch(md_path: Path, user: str, repo: str) -> None:
    last_mtime = None
    while True:
        mtime = md_path.stat().st_mtime
        if mtime != last_mtime:
            last_mtime = mtime
            body = render(md_path, user, repo)
            State.version += 1
            State.html = PAGE.format(body=body, user=user, file=md_path.name,
                                     version=State.version, theme="auto")
            print(f"[{time.strftime('%H:%M:%S')}] rendered {md_path.name} (v{State.version})")
        time.sleep(0.5)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Relative paths in the README (e.g. generated cards) are served from the repo
        local = (ROOT / unquote(urlparse(self.path).path).lstrip("/")).resolve()
        if self.path == "/__version":
            payload = json.dumps({"version": State.version}).encode()
            ctype = "application/json"
        elif self.path != "/" and local.is_file() and local.is_relative_to(ROOT):
            payload = local.read_bytes()
            ctype = mimetypes.guess_type(local.name)[0] or "application/octet-stream"
        else:
            payload = State.html.encode()
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--file", default="README.md")
    parser.add_argument("--user", default="thanhpt1708")
    args = parser.parse_args()

    md_path = (ROOT / args.file).resolve()
    threading.Thread(target=watch, args=(md_path, args.user, args.user), daemon=True).start()
    while not State.html:
        time.sleep(0.1)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Preview: http://localhost:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
