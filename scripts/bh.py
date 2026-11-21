#!/usr/bin/env python3
"""blender-hyperframes helper. Stdlib only, Python 3.10+, Windows, macOS and Linux.

    python bh.py doctor                      what is installed, what is missing, how to install it
    python bh.py build build_scene.py -- --out scene/scene.blend
    python bh.py stats scene/scene.blend     objects, polys, camera, frame range as JSON
    python bh.py render scene/scene.blend --out renders/shot01 --preview [--stills 1,60,120]
    python bh.py sheet renders/shot01        contact sheet (sheet.jpg) to look at
    python bh.py encode renders/shot01 --out video/assets/shot01.mp4 [--alpha webm|mov]
    python bh.py voices dialog.txt --out skit/ [--voice dev=am_michael --voice buddy=bm_george] [--gap 0.25] [--lead 0.4] [--speed 1.0]
    python bh.py compose skit/timing.json --clip shot.mp4 --out video/ [--style subtitle|punch|story] [--title "..."]
    python bh.py polyhaven list --type hdris --category studio
    python bh.py polyhaven get studio_small_09 --res 2k --out assets/
    python bh.py blender -- <any blender arguments>

No Python on Windows: `uv run --no-project bh.py ...` runs it with uv's own Python.
Set BLENDER to the blender executable if `doctor` can't find it.
"""

import argparse
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE.parent / "templates"
JOB = HERE / "blender_job.py"
IS_WIN = os.name == "nt"
UA = "blender-hyperframes-skill/0.1 (+claude code)"
PH_API = "https://api.polyhaven.com"


def die(msg):
    raise SystemExit(f"bh: {msg}")


# ---------- finding tools ----------

def version_key(path):
    nums = re.findall(r"\d+", str(path))
    return [int(n) for n in nums[-3:]] if nums else [0]


def find_blender():
    env = os.environ.get("BLENDER")
    if env:
        return env if Path(env).exists() or shutil.which(env) else die(f"BLENDER={env} does not exist")
    hit = shutil.which("blender")
    if hit:
        return hit
    candidates = []
    if IS_WIN:
        for root in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
            candidates += glob.glob(os.path.join(root, "Blender Foundation", "Blender*", "blender.exe"))
            candidates += glob.glob(os.path.join(root, "Steam", "steamapps", "common", "Blender", "blender.exe"))
    elif sys.platform == "darwin":
        candidates += glob.glob("/Applications/Blender*.app/Contents/MacOS/Blender")
        candidates += glob.glob(os.path.expanduser("~/Applications/Blender*.app/Contents/MacOS/Blender"))
    else:
        candidates += [p for p in ("/snap/bin/blender", "/usr/local/bin/blender", "/opt/blender/blender") if Path(p).exists()]
        candidates += glob.glob(os.path.expanduser("~/blender*/blender"))
    return max(candidates, key=version_key) if candidates else None


def run(cmd, timeout=None, check=True, capture=True):
    env = dict(os.environ, BH_SCRIPTS=str(HERE))  # build scripts import bh_scene from here
    try:
        r = subprocess.run(cmd, capture_output=capture, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=env)
    except FileNotFoundError:
        die(f"not found: {cmd[0]}")
    if check and r.returncode != 0:
        tail = "\n".join(((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-25:])
        die(f"{Path(cmd[0]).name} failed (exit {r.returncode}):\n{tail}")
    return r


def tool_version(cmd, pattern=r"(\d+\.\d+(?:\.\d+)?)"):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    m = re.search(pattern, (r.stdout or "") + (r.stderr or ""))
    return m.group(1) if m else None


def blender_cmd(*args):
    exe = find_blender()
    if not exe:
        die("Blender not found. Install it (see `bh.py doctor`) or set BLENDER to blender.exe")
    return [exe, *args]


def bh_json(stdout):
    for line in reversed(stdout.splitlines()):
        if line.startswith("BH_JSON "):
            return json.loads(line[8:])
    die("no result from blender_job.py:\n" + "\n".join(stdout.splitlines()[-25:]))


# ---------- commands ----------

INSTALL = {
    "blender": {"win": "winget install -e --id BlenderFoundation.Blender", "mac": "brew install --cask blender",
                "linux": "sudo snap install blender --classic"},
    "uv": {"win": "winget install -e --id astral-sh.uv", "mac": "brew install uv",
           "linux": "curl -LsSf https://astral.sh/uv/install.sh | sh"},
    "ffmpeg": {"win": "winget install -e --id Gyan.FFmpeg", "mac": "brew install ffmpeg", "linux": "sudo apt install ffmpeg"},
    "node": {"win": "winget install -e --id OpenJS.NodeJS.LTS", "mac": "brew install node", "linux": "use nodesource or nvm, Node 22+"},
    "mcp-for-blender": {"all": "claude mcp add blender uvx mcp-for-blender  (then: uvx mcp-for-blender install-addon, "
                               "enable the add-on in Blender, start its server)"},
    "hyperframes": {"all": "claude plugin marketplace add heygen-com/hyperframes && "
                           "claude plugin install hyperframes@hyperframes  (or: npx skills add heygen-com/hyperframes)"},
}


def fix_for(tool):
    hints = INSTALL[tool]
    key = "win" if IS_WIN else "mac" if sys.platform == "darwin" else "linux"
    return hints.get("all") or hints[key]


def doctor(a):
    rows = []

    def add(tool, ok, found, note=""):
        rows.append({"tool": tool, "ok": bool(ok), "found": found or "", "note": note,
                     "fix": "" if ok else fix_for(tool if tool in INSTALL else tool.split()[0])})

    exe = find_blender()
    bver = tool_version([exe, "-b", "--factory-startup", "--version"], r"Blender (\d+\.\d+(?:\.\d+)?)") if exe else None
    old = bver and [int(x) for x in bver.split(".")[:2]] < [4, 2]
    add("blender", exe and bver and not old, f"{bver} {exe}" if exe else None, "needs 4.2 or later" if old else "")
    uvx = shutil.which("uvx")
    add("uv", uvx, tool_version(["uv", "--version"]), "runs MCP for Blender")
    ff = shutil.which("ffmpeg")
    add("ffmpeg", ff and shutil.which("ffprobe"), tool_version(["ffmpeg", "-version"], r"ffmpeg version (\S+)"), "encodes renders; HyperFrames needs it")
    nver = tool_version(["node", "--version"])
    add("node", nver and int(nver.split(".")[0]) >= 22, nver, "HyperFrames needs Node 22+")
    claude = shutil.which("claude")
    if claude:
        try:
            ok = subprocess.run([claude, "mcp", "get", "blender"], capture_output=True, text=True, timeout=60).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            ok = False
        add("mcp-for-blender", ok, "claude mcp: blender" if ok else None,
            "optional: live scene control; headless scripts work without it")
    home = Path.home()
    hf = [p for p in (home / ".claude/skills/hyperframes", home / ".agents/skills/hyperframes") if p.exists()]
    hf += [Path(p) for p in glob.glob(str(home / ".claude/plugins/cache/hyperframes*/*/*"))]
    add("hyperframes", hf, str(hf[0]) if hf else None, "the HyperFrames skills for the edit")
    if a.json:
        print(json.dumps({"platform": platform.platform(), "tools": rows}, indent=1))
        return
    print(f"platform: {platform.platform()}")
    for r in rows:
        mark = "ok  " if r["ok"] else "MISS"
        print(f"{mark} {r['tool']:<16} {r['found']}" + (f"  ({r['note']})" if r["note"] else ""))
        if not r["ok"]:
            print(f"     install: {r['fix']}")


def blender_passthrough(a):
    args = a.args[1:] if a.args[:1] == ["--"] else a.args
    r = subprocess.run(blender_cmd(*args))
    sys.exit(r.returncode)


def build(a):
    script = Path(a.script).resolve()
    extra = a.args[1:] if a.args[:1] == ["--"] else a.args
    r = run(blender_cmd("-b", "--factory-startup", "--python-exit-code", "1", "-P", str(script), "--", *extra),
            timeout=a.timeout)
    print("\n".join(r.stdout.strip().splitlines()[-15:]))


def stats(a):
    r = run(blender_cmd("-b", str(Path(a.blend).resolve()), "--python-exit-code", "1", "-P", str(JOB), "--", "stats"),
            timeout=300)
    print(json.dumps(bh_json(r.stdout), indent=1))


def render(a):
    job = ["render", "--out", str(Path(a.out).resolve()), "--engine", a.engine]
    for flag, val in (("--res", a.res), ("--percent", a.percent), ("--samples", a.samples), ("--fps", a.fps),
                      ("--frames", a.frames), ("--stills", a.stills), ("--hide", a.hide)):
        if val:
            job += [flag, str(val)]
    job += ["--preview"] if a.preview else []
    job += ["--transparent"] if a.transparent else []
    r = run(blender_cmd("-b", str(Path(a.blend).resolve()), "--python-exit-code", "1", "-P", str(JOB), "--", *job),
            timeout=a.timeout)
    print(json.dumps(bh_json(r.stdout), indent=1))


def frames_in(folder):
    files = sorted(Path(folder).glob("frame_*.png"))
    if not files:
        die(f"no frame_*.png in {folder}")
    first = int(re.search(r"(\d+)", files[0].stem).group(1))
    return files, first


def sheet(a):
    files, first = frames_in(a.dir)
    cells = a.cols * a.rows
    step = max(1, len(files) // cells)
    out = Path(a.out or Path(a.dir) / "sheet.jpg")
    vf = (f"select='not(mod(n\\,{step}))',scale={a.width}:-2,"
          f"drawtext=text='%{{eif\\:n*{step}+{first}\\:d}}':x=8:y=8:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.5,"
          f"tile={a.cols}x{a.rows}:padding=4:color=gray")
    cmd = ["ffmpeg", "-v", "error", "-y", "-start_number", str(first), "-i", str(Path(a.dir) / "frame_%04d.png"),
           "-vf", vf, "-frames:v", "1", "-q:v", "3", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:  # some ffmpeg builds lack drawtext (no libfreetype)
        cmd[cmd.index("-vf") + 1] = re.sub(r"drawtext=[^,]*(?:\\,[^,]*)*,", "", vf)
        run(cmd)
    print(json.dumps({"sheet": str(out), "frames": len(files), "every": step, "first": first}))


def encode(a):
    files, first = frames_in(a.dir)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    gop = str(a.fps)  # a keyframe every second keeps HyperFrames seeks frame-accurate
    src = ["ffmpeg", "-v", "error", "-y", "-framerate", str(a.fps), "-start_number", str(first),
           "-i", str(Path(a.dir) / "frame_%04d.png")]
    even = ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]
    if a.alpha == "webm":
        out = out.with_suffix(".webm")
        codec = ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", str(a.crf or 30),
                 "-row-mt", "1", "-auto-alt-ref", "0", "-g", gop]
    elif a.alpha == "mov":
        out = out.with_suffix(".mov")
        codec = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0"]
    else:
        out = out.with_suffix(".mp4")
        codec = ["-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf or 18), "-g", gop, "-keyint_min", gop,
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    run(src + even + codec + [str(out)])
    probe = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                 "stream=width,height,codec_name,pix_fmt,r_frame_rate,nb_frames:format=duration", "-of", "json", str(out)])
    info = json.loads(probe.stdout)
    s = info["streams"][0]
    print(json.dumps({"out": str(out), "codec": s.get("codec_name"), "size": [s.get("width"), s.get("height")],
                      "pix_fmt": s.get("pix_fmt"), "fps": s.get("r_frame_rate"),
                      "duration": float(info["format"].get("duration", 0)), "frames": len(files)}))


# ---------- skit: voices and overlay ----------

DEFAULT_VOICES = {"dev": "am_michael", "buddy": "bm_george"}
FALLBACK_VOICE = "am_adam"
TAIL = 0.8  # silence after the last line


def hyperframes_cli():
    """Command prefix that runs the HyperFrames CLI: env var, newest plugin copy, then npx."""
    env = os.environ.get("HYPERFRAMES_CLI")
    node = shutil.which("node")
    if env:
        if not Path(env).exists():
            die(f"HYPERFRAMES_CLI={env} does not exist")
        return [node or die("node not found (HyperFrames needs Node 22+)"), env]
    pattern = str(Path.home() / ".claude/plugins/cache/hyperframes/hyperframes/*/skills/hyperframes/scripts/plugin-cli.mjs")
    hits = glob.glob(pattern)
    if hits and node:
        return [node, max(hits, key=version_key)]
    npx = shutil.which("npx.cmd" if IS_WIN else "npx")
    if not npx:
        die("HyperFrames CLI not found: set HYPERFRAMES_CLI to plugin-cli.mjs, or install Node 22+ for npx")
    return [npx, "--yes", "hyperframes"]


def parse_dialog(path):
    lines, cards = [], []  # cards: dicts with 'after' = index of the first spoken line they apply to
    for n, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        t = raw.strip()
        if not t or t.startswith("//"):
            continue
        if t.startswith("#card"):
            body = t[5:].strip()
            if body.lower() == "off":
                cards.append({"after": len(lines), "off": True})
                continue
            parts = [x.strip() for x in body.split("|")]
            if len(parts) < 2 or not parts[0] or not parts[1]:
                die(f"{path}:{n}: expected '#card LABEL | VALUE | SUFFIX' or '#card off'")
            c = {"after": len(lines), "label": parts[0], "value": parts[1], "suffix": parts[2] if len(parts) > 2 else ""}
            m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*%\s*$", c["value"])
            if m:
                c["progress"] = round(max(0.0, min(1.0, float(m.group(1)) / 100)), 4)
            cards.append(c)
            continue
        m = re.match(r"^([A-Za-z0-9_\- ]+?)\s*:\s*(.+)$", t)
        if not m:
            die(f"{path}:{n}: expected 'speaker: text', got: {t[:60]}")
        lines.append({"speaker": m.group(1).strip().lower(), "text": m.group(2).strip()})
    if not lines:
        die(f"{path}: no spoken lines")
    return lines, cards


def probe_duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)])
    return float(r.stdout.strip())


def voices(a):
    lines, raw_cards = parse_dialog(a.dialog)
    vmap = dict(DEFAULT_VOICES)
    for item in a.voice or []:
        if "=" not in item:
            die(f"--voice expects speaker=voice, got {item}")
        k, v = item.split("=", 1)
        vmap[k.strip().lower()] = v.strip()
    out = Path(a.out)
    (out / "lines").mkdir(parents=True, exist_ok=True)
    cli = hyperframes_cli()
    speakers = {}
    for i, ln in enumerate(lines):
        voice = vmap.get(ln["speaker"], FALLBACK_VOICE)
        speakers.setdefault(ln["speaker"], {"voice": voice})
        wav = out / "lines" / f"{i:03d}.wav"
        cmd = cli + ["tts", ln["text"], "-o", str(wav), "-v", voice, "--json"]
        if a.speed != 1.0:
            cmd += ["-s", str(a.speed)]
        run(cmd, timeout=600)
        if not wav.exists() or wav.stat().st_size == 0:
            die(f"tts produced no audio for line {i}: {ln['text']}")
        dur = probe_duration(wav)
        start = a.lead if i == 0 else lines[i - 1]["end"] + a.gap
        ln.update(i=i, start=round(start, 3), end=round(start + dur, 3), file=f"lines/{i:03d}.wav")
    duration = round(lines[-1]["end"] + TAIL, 3)

    # cards run from the start of the next spoken line to the next #card (or off, or the end)
    cards = []
    for j, c in enumerate(raw_cards):
        if c.get("off") or c["after"] >= len(lines):
            continue
        nxt = raw_cards[j + 1] if j + 1 < len(raw_cards) else None
        if nxt is None:
            end = duration
        else:
            end = lines[nxt["after"]]["start"] if nxt["after"] < len(lines) else duration
        start = lines[c["after"]]["start"]
        if end <= start:
            continue
        card = {"start": start, "end": round(end, 3), "label": c["label"], "value": c["value"], "suffix": c["suffix"]}
        if "progress" in c:
            card["progress"] = c["progress"]
        cards.append(card)

    # mix: each line delayed to its start; lines never overlap, so a plain sum is exact
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for ln in lines:
        cmd += ["-i", str(out / ln["file"])]
    parts, labels = [], []
    for k, ln in enumerate(lines):
        ms = int(round(ln["start"] * 1000))
        parts.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}|{ms}[a{k}]")
        labels.append(f"[a{k}]")
    parts.append("".join(labels) + f"amix=inputs={len(lines)}:normalize=0:duration=longest,apad=whole_dur={duration}[m]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "[m]", "-t", str(duration), "-ar", "48000", "-ac", "1",
            "-c:a", "pcm_s16le", str(out / "voice.wav")]
    run(cmd)

    timing = {"fps": 30, "duration": duration, "audio": "voice.wav", "speakers": speakers,
              "lines": [{k: ln[k] for k in ("i", "speaker", "text", "start", "end", "file")} for ln in lines],
              "cards": cards}
    (out / "timing.json").write_text(json.dumps(timing, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"lines": len(lines), "cards": len(cards), "duration": duration, "out": str(out / "timing.json")}))


def compose(a):
    tpath = Path(a.timing).resolve()
    timing = json.loads(tpath.read_text(encoding="utf-8"))
    clip = Path(a.clip).resolve()
    if not clip.exists():
        die(f"clip not found: {clip}")
    audio = (tpath.parent / timing.get("audio", "voice.wav")).resolve()
    if not audio.exists():
        die(f"voice audio not found: {audio}")
    out = Path(a.out).resolve()
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    clip_dst, audio_dst = assets / f"clip{clip.suffix}", assets / f"voice{audio.suffix}"
    for src, dst in ((clip, clip_dst), (audio, audio_dst)):
        if src != dst:
            shutil.copyfile(src, dst)
    duration = float(timing["duration"])
    data = {"style": a.style, "title": a.title or "", "duration": duration,
            "lines": timing["lines"], "cards": timing.get("cards", [])}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = (TEMPLATES / "skit_overlay.html").read_text(encoding="utf-8")
    for key, val in (("{{DURATION}}", f"{duration:g}"), ("{{CLIP}}", f"assets/{clip_dst.name}"),
                     ("{{AUDIO}}", f"assets/{audio_dst.name}"), ("{{DATA}}", blob)):
        html = html.replace(key, val)
    (out / "index.html").write_text(html, encoding="utf-8")
    print(json.dumps({"index": str(out / "index.html"), "style": a.style, "duration": duration,
                      "lines": len(data["lines"]), "cards": len(data["cards"])}))


# ---------- Poly Haven (CC0 assets, no key) ----------

def ph_get(path):
    req = urllib.request.Request(PH_API + path, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def polyhaven(a):
    if a.action == "list":
        q = f"/assets?t={a.type}" + (f"&c={a.category}" if a.category else "")
        assets = ph_get(q)
        rows = []
        for aid, info in assets.items():
            blob = " ".join([aid, info.get("name", ""), *info.get("tags", []), *info.get("categories", [])]).lower()
            if a.query and not all(w in blob for w in a.query.lower().split()):
                continue
            rows.append({"id": aid, "name": info.get("name"), "categories": info.get("categories", [])[:5],
                         "downloads": info.get("download_count", 0)})
        rows.sort(key=lambda r: -r["downloads"])
        print(json.dumps(rows[: a.limit], indent=1))
        return
    files = ph_get(f"/files/{a.id}")
    out = Path(a.out) / a.id
    kind = {0: "hdri", 1: "texture", 2: "model"}[ph_get(f"/info/{a.id}")["type"]]
    fmt = a.format or {"hdri": "hdr", "model": "gltf", "texture": "blend"}[kind]
    if kind == "hdri":
        entry = files["hdri"].get(a.res, {}).get(fmt)
    else:
        entry = files.get(fmt, {}).get(a.res, {}).get(fmt)
    if not entry:
        die(f"{a.id}: no {fmt} at {a.res}; try --res 1k/2k/4k or --format (hdri: hdr/exr; models: gltf/blend/fbx)")
    main = out / Path(entry["url"]).name
    download(entry["url"], main)
    for rel, inc in (entry.get("include") or {}).items():
        download(inc["url"], out / rel)
    print(json.dumps({"id": a.id, "kind": kind, "file": str(main), "license": "CC0 (polyhaven.com/license)",
                      "includes": len(entry.get("include") or {})}))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=doctor)

    p = sub.add_parser("blender", help="run Blender with any arguments")
    p.add_argument("args", nargs=argparse.REMAINDER)
    p.set_defaults(fn=blender_passthrough)

    p = sub.add_parser("build", help="run a scene build script headless (factory settings)")
    p.add_argument("script")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("args", nargs=argparse.REMAINDER, help="-- arguments passed to the script")
    p.set_defaults(fn=build)

    p = sub.add_parser("stats")
    p.add_argument("blend")
    p.set_defaults(fn=stats)

    p = sub.add_parser("render")
    p.add_argument("blend")
    p.add_argument("--out", required=True, help="folder for frame_####.png")
    p.add_argument("--preview", action="store_true", help="50%% size, 16 samples unless set")
    p.add_argument("--engine", choices=["eevee", "cycles", "workbench"], default="eevee")
    p.add_argument("--res", help="WIDTHxHEIGHT")
    p.add_argument("--percent", type=int)
    p.add_argument("--samples", type=int)
    p.add_argument("--fps", type=int)
    p.add_argument("--frames", help="START-END")
    p.add_argument("--stills", help="e.g. 1,60,120")
    p.add_argument("--transparent", action="store_true")
    p.add_argument("--hide", help="object names left out of this render, e.g. Floor for a cutout")
    p.add_argument("--timeout", type=int, default=7200)
    p.set_defaults(fn=render)

    p = sub.add_parser("sheet", help="contact sheet of rendered frames")
    p.add_argument("dir")
    p.add_argument("--out")
    p.add_argument("--cols", type=int, default=4)
    p.add_argument("--rows", type=int, default=3)
    p.add_argument("--width", type=int, default=480)
    p.set_defaults(fn=sheet)

    p = sub.add_parser("encode", help="PNG frames to a clip HyperFrames can seek")
    p.add_argument("dir")
    p.add_argument("--out", required=True)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--alpha", choices=["webm", "mov"], help="keep transparency")
    p.add_argument("--crf", type=int)
    p.set_defaults(fn=encode)

    p = sub.add_parser("voices", help="dialog text file to per-line voices, one mixed voice.wav and timing.json")
    p.add_argument("dialog")
    p.add_argument("--out", required=True, help="folder for lines/, voice.wav, timing.json")
    p.add_argument("--voice", action="append", help="speaker=voice, repeatable (defaults dev=am_michael, buddy=bm_george)")
    p.add_argument("--gap", type=float, default=0.25, help="seconds between lines")
    p.add_argument("--lead", type=float, default=0.4, help="seconds before the first line")
    p.add_argument("--speed", type=float, default=1.0)
    p.set_defaults(fn=voices)

    p = sub.add_parser("compose", help="timing.json + clip to a HyperFrames project (index.html) with captions and cards")
    p.add_argument("timing")
    p.add_argument("--clip", required=True)
    p.add_argument("--out", required=True, help="HyperFrames project folder")
    p.add_argument("--style", choices=["subtitle", "punch", "story"], default="subtitle")
    p.add_argument("--title")
    p.set_defaults(fn=compose)

    p = sub.add_parser("polyhaven", help="CC0 HDRIs, textures and models")
    p.add_argument("action", choices=["list", "get"])
    p.add_argument("id", nargs="?")
    p.add_argument("--type", choices=["hdris", "textures", "models"], default="hdris")
    p.add_argument("--category")
    p.add_argument("--query")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--res", default="2k")
    p.add_argument("--format")
    p.add_argument("--out", default="assets")
    p.set_defaults(fn=polyhaven)

    a = ap.parse_args()
    if a.cmd == "polyhaven" and a.action == "get" and not a.id:
        die("polyhaven get needs an asset id (see polyhaven list)")
    a.fn(a)


if __name__ == "__main__":
    main()
