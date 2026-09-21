"""Wrap app.html (artifact fragment) into index.html, a standalone page.

The published artifact supplies the document skeleton itself, so app.html deliberately
has no <!doctype>/<html>/<head>/<body>. This adds them, plus the bit of reset the
artifact platform provides, for opening from disk or hosting anywhere.
"""

import pathlib

FRAGMENT = pathlib.Path(__file__).with_name("app.html")
STANDALONE = pathlib.Path(__file__).with_name("index.html")

head, body = FRAGMENT.read_text().split("</style>", 1)

STANDALONE.write_text(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin: 0; }}
</style>
{head}</style>
</head>
<body>
{body}
</body>
</html>
""")

print(f"wrote {STANDALONE.name} ({STANDALONE.stat().st_size:,} bytes)")
