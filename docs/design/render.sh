#!/bin/bash
# Re-renders every mockup image from mockups/studio.html with headless Chrome (macOS path).
# Needs network the first time (Google Fonts). Output is 2880x1800 (1440x900 @2x).
set -e
cd "$(dirname "$0")"
CH="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
shot() { "$CH" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
  --window-size=1440,900 --virtual-time-budget=8000 --screenshot="$PWD/$2" \
  "file://$PWD/mockups/studio.html$1" >/dev/null 2>&1; echo "wrote $2"; }
shot ""                        01-player.png
shot "?annotate"               02-player-annotated.png
shot "?mode=stream"            03-stream.png
shot "?mode=stream&annotate"   04-stream-annotated.png
shot "?mode=gallery"           05-style-lab.png
