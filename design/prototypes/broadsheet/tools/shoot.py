#!/usr/bin/env python3
"""Screenshot a page at an exact layout width with headless Chrome.
   python3 tools/shoot.py <out-name> <page> <width> <theme> [y h]     -> shots/<out-name>.png
   Without y/h the whole page is captured."""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
        "--allow-file-access-from-files", "--virtual-time-budget=5000"]

def main():
    name, page, width, theme = sys.argv[1:5]
    crop = [int(v) for v in sys.argv[5:7]] if len(sys.argv) > 6 else None
    url = f"file://{ROOT}/tools/harness.html?src={page}&w={width}&theme={theme}"
    dom = subprocess.run(BASE + [f"--window-size={max(int(width), 500)},900", "--dump-dom", url], capture_output=True, text=True).stdout
    m = re.search(r"H=(\d+) SW=(\d+) CW=(\d+)", dom)
    if not m:
        sys.exit("harness did not report a height")
    height, sw, cw = (int(v) for v in m.groups())
    y, h = crop if crop else (0, height)
    out = ROOT / "shots" / f"{name}.png"
    subprocess.run(BASE + [f"--window-size={width},{h}", f"--screenshot={out}", url + f"&y={y}"], capture_output=True)
    flag = "" if sw <= cw else f"  !! horizontal overflow: scrollWidth {sw} > {cw}"
    print(f"{out.name}: page {cw}x{height}, shot {width}x{h} at y={y}{flag}")

main()
