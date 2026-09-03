#!/usr/bin/env python3
"""
Robotics Lab server v2 — projects, STEP export, sim LLM driver.

API:
  GET  /api/projects        -> list projects
  POST /api/projects        -> {name} create project
  POST /api/projects/open   -> {name} switch active project
  GET  /api/project         -> active project meta + parts
  POST /api/parts           -> {parts:[...]} save parts list
  GET  /api/models          -> STLs in active project
  GET  /api/mtimes          -> live-reload polling
  GET  /models/<f>          -> STL file
  POST /api/snapshot        -> save view+note into project snapshots/
  POST /api/export          -> {model} convert matching .scad -> STEP via FreeCAD
  POST /api/sim/drive       -> {image,distance,goal} -> vision LLM -> {left,right,say}
"""
import json, base64, time, os, subprocess, urllib.request
import http.client, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT     = Path(__file__).parent
UI       = ROOT / "ui"
PROJECTS = ROOT / "projects"
STATE    = ROOT / "state.json"
TOOLS    = ROOT / "tools"
PORT     = 8321

# ---------- project helpers ----------
def state():
    try: return json.loads(STATE.read_text())
    except Exception: return {"active": None}

def set_active(name):
    STATE.write_text(json.dumps({"active": name}))

def active():
    s = state().get("active")
    if s and (PROJECTS / s).is_dir(): return s
    ps = sorted(p.name for p in PROJECTS.iterdir() if p.is_dir())
    return ps[0] if ps else None

def pdir(sub=""):
    a = active()
    if not a: return None
    d = PROJECTS / a / sub if sub else PROJECTS / a
    d.mkdir(parents=True, exist_ok=True)
    return d

# ---------- OpenAI key: env var, or the Settings tab (stored in local config.json,
# gitignored — each user brings their own key) ----------
CONFIG_F = ROOT / "config.json"

def _config():
    try: return json.loads(CONFIG_F.read_text())
    except Exception: return {}

def openai_key():
    return os.environ.get("OPENAI_API_KEY") or _config().get("openai_api_key") or None

# ---------- FreeCAD STEP conversion ----------
def find_freecadcmd():
    for c in ["/Applications/FreeCAD.app/Contents/MacOS/freecadcmd",
              "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd",
              "/opt/homebrew/bin/freecadcmd", "/opt/homebrew/bin/FreeCADCmd"]:
        if Path(c).exists(): return c
    return None

def export_step(stem):
    stl = pdir("models") / f"{stem}.stl"
    if not stl.exists():
        return {"ok": False, "error": f"model '{stem}.stl' not found"}
    fc = find_freecadcmd()
    if not fc:
        return {"ok": False, "error": "FreeCAD not installed yet (install in progress?)"}
    out = pdir("exports") / f"{stem}.step"
    try:
        env = {**os.environ, "STL_IN": str(stl), "STEP_OUT": str(out)}
        r = subprocess.run([fc, str(TOOLS / "scad2step.py")],
                           env=env, capture_output=True, text=True, timeout=300)
        if out.exists() and out.stat().st_size > 0:
            return {"ok": True, "file": f"projects/{active()}/exports/{out.name}",
                    "size": out.stat().st_size}
        return {"ok": False, "error": (r.stderr or r.stdout)[-400:]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ---------- vision LLM driver ----------
DRIVE_PROMPT = """You are driving a small 2-wheel differential-drive rover with a pan servo camera in a simulation.
GOAL: {goal}

ONBOARD SENSOR TELEMETRY (live readings, distances in mm):
{telemetry}

YOUR MEMORY (notes you wrote to yourself on the previous call):
{memory}

YOUR RECENT ACTIONS (oldest first):
{history}

The image is the rover camera's point of view (currently panned {cam_pan} degrees).
ENVIRONMENT: {env_desc}. Use the floor pattern (~150-200mm per plank/tile) to estimate distances.
LANDMARKS: telemetry "known_landmarks" lists objects you already labeled, with live distance/bearing from your current pose (bearing 0 = straight ahead, positive = left). If you see a NEW distinct object not on that list, label it via "landmarks" in your reply (max 3, only new objects, bearing relative to camera center).
Decide motor powers, optionally re-aim the camera, and update your memory.
Reply ONLY with JSON: {{"left": <-1..1>, "right": <-1..1>, "cam_pan": <-60..60 deg, optional>, "observe": "<what you see right now, <=15 words>", "assess": "<what it means for the current step/goal, <=15 words>", "memory": "<running plan + notes to your future self, max 60 words>", "say": "<the action decision, brief>", "landmarks": [{{"label": "<short name>", "bearing_deg": <-45..45>, "distance_mm": <estimate>}}] (optional)}}
left/right are wheel powers. Equal+positive=forward, opposite=spin turn.
Any ultrasonic under 100mm = about to hit something on that side (0 = touching); turn away.
SPEED is yours to choose via power magnitude: creep at 0.1-0.3 near obstacles or when unsure, 0.5-0.8 in open space.
A reflex governor physically slows forward motion when anything is under 400mm ahead ("speed_governor_active": true means it is engaged right now); reverse is never limited.
COLLISIONS: "colliding": true means you are IN CONTACT with an obstacle RIGHT NOW — immediately reverse (negative powers) or pivot away. "stuck_s" = seconds you have been jammed. Every collision is a failure; keep "collisions_this_session" at zero.
Use memory + recent actions to avoid repeating failed maneuvers and to explore new areas instead of revisiting."""

# gpt-4o-mini pricing per 1M tokens
PRICE_IN, PRICE_OUT = 0.15, 0.60

# ---------- mission planner: mission -> exhaustive step list (top of hierarchy) ----------
PLAN_PROMPT = """This is a hobby robotics SIMULATOR — a virtual toy rover in a browser-rendered arena; no real hardware.
You are the MISSION PLANNER, the top of a three-layer stack: you break the mission into steps ONCE; a thinker executes your steps one at a time via driving subgoals; a driver moves the wheels. You are only called at mission start or when the thinker reports your plan cannot work.

MISSION: {goal}

WHAT THE ROVER KNOWS SO FAR:
Telemetry: {telemetry}
Its memory: {memory}
Landmarks already identified: {landmarks}

ENVIRONMENT: {env_desc}. Beyond that, the CONTENTS ARE UNKNOWN — some number of objects of unknown colors/shapes/positions; the rover discovers, names, and maps them itself. The rover has a FIXED forward camera (no pan — looking elsewhere means turning the rover; never write camera-pan steps), 3 forward ultrasonics, and a memory map that grows as it drives.
Break the mission into an EXHAUSTIVE ordered list of 3-8 concrete executable steps. The executor offers exactly these motions: scan, goto(landmark), follow_waypoints (plotted arcs/routes), move, turn — write steps that map cleanly onto them (e.g. 'plot and drive an arc around the target object to its far face'). Each step must be something a rover can do by driving/turning/looking, with an observable success condition. Cover: locating any named target (rotating/scanning until seen), approaching it, positioning (seeing a far face requires driving AROUND the object), verifying, and answering.
Each step ALSO gets a machine-checkable "check" that code evaluates automatically (steps advance without judgment when possible):
- {{"type": "landmark_known", "label": "<name substring>"}} — succeeds when a landmark with that label has been identified
- {{"type": "near_landmark", "label": "<name substring>", "within_mm": <n>}} — succeeds when the rover is within n mm of that landmark
- {{"type": "telemetry", "field": "<sensor field>", "op": "gt|lt", "value": <n>}} — succeeds on a sensor threshold
- {{"type": "perception"}} — only for steps requiring visual judgment (reading a number, confirming a face is visible); these advance via your executor's step_done
Use landmark_known/near_landmark/telemetry wherever possible; perception only when unavoidable.
Reply ONLY JSON: {{"plan": [{{"step": "<imperative, <=18 words>", "success": "<observable condition, <=14 words>", "check": {{...}}}}], "say": "<brief rationale>"}}"""

def sim_plan(payload):
    key = openai_key()
    if not key: return {"error": "No OpenAI API key — add yours in the Settings section (left panel)"}
    sensors = payload.get("sensors", {})
    prompt = PLAN_PROMPT.format(
        env_desc=payload.get("env_desc") or "a walled area",
        goal=payload.get("goal") or "Explore.",
        telemetry=json.dumps(sensors)[:800],
        memory=(payload.get("memory") or "").strip() or "(none yet)",
        landmarks=json.dumps(sensors.get("known_landmarks", []))[:400])
    img = payload.get("image")
    user_content = ([{"type": "text", "text": "Current camera view attached. Reply with the JSON."},
                     {"type": "image_url", "image_url": {"url": img, "detail": "low"}}]
                    if img else "No camera frame. Reply with the JSON.")
    body = _mk_body(payload.get("model") or "gpt-4.1",
                    [{"role": "system", "content": prompt},
                     {"role": "user", "content": user_content}], 500)
    t0 = time.time()
    try:
        reply = _openai_post(body, key)
        latency_ms = round((time.time() - t0) * 1000)
        msg = reply["choices"][0]["message"]
        raw = msg.get("content")
        if raw is None:
            return {"error": "model refused: " + str(msg.get("refusal"))[:200], "latency_ms": latency_ms}
        tin, tout, cost = _cost(reply.get("usage", {}))
        add_usage(tin, tout, cost)
        cmd = json.loads(raw)
        plan = []
        for s in (cmd.get("plan") or [])[:8]:
            if isinstance(s, dict) and s.get("step"):
                chk = s.get("check") if isinstance(s.get("check"), dict) else {}
                if chk.get("type") not in ("landmark_known", "near_landmark", "telemetry", "perception"):
                    chk = {"type": "perception"}
                plan.append({"step": str(s["step"])[:140], "success": str(s.get("success", ""))[:100],
                             "check": chk})
        out = {"plan": plan, "say": str(cmd.get("say", ""))[:200],
               "latency_ms": latency_ms, "usage": {"in": tin, "out": tout},
               "cost_usd": cost, "context": prompt, "raw": raw, "model": body["model"]}
        session_log({"type": "plan", "t": round(time.time(), 1), "tab": payload.get("tab"), "goal": payload.get("goal"),
                     "plan": plan, "usage": out["usage"], "cost_usd": cost,
                     "latency_ms": latency_ms, "model": body["model"]})
        return out
    except Exception as e:
        err = {"error": str(e)[:300], "latency_ms": round((time.time() - t0) * 1000)}
        session_log({"type": "error", "loop": "plan", "t": round(time.time(), 1), **err})
        return err

# ---------- split-brain: slow thinker sets subgoals, fast driver executes ----------
THINK_PROMPT = """This is a hobby robotics SIMULATOR — a virtual toy rover in a browser-rendered arena; no real hardware, people, or property are involved.
You are the strategic PLANNER for the simulated 2-wheel rover. A separate fast driver model executes your subgoals; you think, it drives.
BIG GOAL: {goal}

MISSION PLAN (written by the planner — execute it IN ORDER, one step at a time):
{plan}
YOU ARE ON STEP {step_no}: {step_text}
STEP SUCCESS CONDITION: {step_success}
EVERY CALL, FIRST evaluate: is the current step's success condition ALREADY MET per telemetry/image? If yes, set "step_done": true AND issue a subgoal for the NEXT step in the same reply. Do not linger on a completed step.
Then focus your subgoal on the (possibly newly advanced) current step. "need_replan": true only if the plan genuinely cannot work as written.
OPPORTUNISM OVERRIDES THE PLAN: if you can ALREADY read/see the thing the mission is looking for (e.g. the target number is visible in this frame), reply with "answer" IMMEDIATELY, whatever step you are on. Never postpone a visible answer.

⚠ SITUATION (code-assessed from physics, trust it over your own reading): {situation}
EVENTS SINCE YOUR LAST PLAN (things that happened while you were thinking):
{events}
If the situation shows contact, stuck, closing obstacle, or spinning, your FIRST priority is a subgoal that increases clearance: turn toward an open or unscanned radar sector and advance. The big goal waits until the rover is safe.
SAFETY MODE: {safety_mode}
MISSION SIZING — the budgets are the law: "advance_budget_mm" is how far you can actually advance RIGHT NOW before contact (live forward cone minus hull width). "reverse_budget_mm" is the same for reverse, but computed from MEMORY only (unscanned space behind = untrustworthy). Your advanced_mm target MUST be at most advance_budget_mm minus ~150 margin — commanding 1000 when the budget says 700 is how collisions happen. If advance_budget_mm < 300, do not advance at all: turn instead.

YOUR TIMING (know your own tempo): {timing}
Your reply lands in the FUTURE — plan for where the rover WILL BE by then, not where this snapshot shows it. Size subgoals to stay valid for at least 2 of your planning cycles.

DETAILED MISSION PROGRESS (code-measured, trust these numbers):
{plan_progress}

PREVIOUS SUBGOAL: {subgoal}
ITS PROGRESS SO FAR: {progress}
DRIVER REPORTED: {driver_status}
RECENT SUBGOALS AND OUTCOMES (oldest first, with age in seconds):
{history}

ORIENTATION — how to read your compass and bearings:
- heading_deg is your compass in the arena (0-359; it INCREASES when you turn left). It tells you which way you face in the world map.
- landmark bearing_deg is RELATIVE TO YOUR NOSE, exactly as it appears in your camera image: bearing 0 = straight ahead/image center, POSITIVE = to your RIGHT, NEGATIVE = to your LEFT. Report new landmark bearings the same way.
- Therefore a landmark's bearing_deg is EXACTLY how many degrees to turn to face it: bearing +30 → turn RIGHT 30 (turned_deg gt 28); bearing -60 → turn LEFT 60.
- turned_deg counts degrees actually rotated since the current subgoal began.

ONBOARD TELEMETRY (all distances measured from your FRONT BUMPER — 0mm = touching):
{telemetry}

YOUR MEMORY (notes you wrote last time):
{memory}

The first image is the rover camera POV. THE CAMERA IS FIXED, facing straight ahead — there is no pan. To look in a different direction, TURN THE ROVER.
MIND'S EYE — the second image is YOUR MAP: only what you have discovered (grey dots = sonar-scanned geometry, orange dots = landmarks you labeled with their (x,y) in mm, blue = your trail, green arrow = YOU with your facing and printed pose). Coordinate grid in mm: +x right/east, +y up/north; heading 0 = +x, increasing counterclockwise (left). Unmarked space is UNKNOWN, not open. Telemetry pose_mm and each landmark's map_x/map_y give the same coordinates as numbers.
DURABILITY: your "memory" field is 60 words and constantly rewritten — everything else you learn is forgotten. Your map annotations (points_of_interest) are the ONLY durable record of what you have discovered about PLACES. What is not written on the map does not persist.
GRID VIEW — the same map as a text grid for precise planning ('.'=unknown, '#'=scanned obstacle/wall, letter=labeled block (first letter of its color), '@'=you). Each cell is 200mm (24x24); columns run x=-2400(left)→+2400(right), rows run y=+2400(top)→-2400(bottom). Convert cell(col,row) to mm: x=-2400+(col+0.5)*200, y=+2400-(row+0.5)*200. Lowercase letters = your own POI marks.
{map_grid}
PLOTTING A PATH — your strongest tool for maneuvers language cannot steer (going AROUND objects, reaching far sides, threading gaps): reply with "waypoints": [{{"x": <mm>, "y": <mm>}}, ...] — use 4-6 points for any go-around (2 points cannot trace a curve; the route must sweep AROUND, not cut across). Keep every point at least 450mm from block centers and away from grey dots. Code will drive them precisely, point by point, and report progress; you will see "following plotted path: waypoint k/n". Plot around known geometry — leave ~350mm clearance from dots and landmarks. Example: to view the far side of a block at (700,500) from the south, plot points sweeping around it: (350,350) → (350,700) → (700,860) then face it. Only re-plot if the path is wrong; while a path runs, missions/subgoals are unnecessary.
MANDATORY: if the current step involves circling, going around, reaching a far side, or any multi-turn route — turning in place CANNOT accomplish it. You MUST reply with "waypoints" for such steps. A turn subgoal for a go-around step is a wrong answer.
ENVIRONMENT SCALE: floor tiles are 200mm — count tiles for distance. Walls are striped with an ORANGE BAND on top; stripes/orange filling the frame = you are facing a wall CLOSE UP. Facing a wall = DEAD END: the correct subgoal is to turn ~120-180 deg and drive AWAY — never keep approaching.
SEARCH LABELING PRIORITY: if the object your current step is SEARCHING FOR is visible anywhere in the frame, your FIRST duty is to include it in "landmarks" in THIS reply — the step cannot advance until it is labeled; describing it in scene text is not enough.
LANDMARKS: "known_landmarks" lists objects you already labeled (live distance/bearing, bearing 0 = ahead, positive = left). Label NEW distinct objects via "landmarks" (max 3, only new).
NO REAR SENSOR: "rear_memory_mm" is NOT a sensor — it is remembered from your map. "map_radar" is your SEMANTIC spatial memory per 45-deg sector: each sector is {{"mm": <distance to nearest remembered obstacle>, "what": <its label if you ever identified it, else null>}}. 6000 = unscanned (not necessarily open). Example: "rear_right": {{"mm": 1400, "what": "red block"}} means the red block you labeled is 1.4m behind-right. Use it to navigate by memory. LABEL EVERYTHING: every distinct thing you can identify in a frame (up to 3 new per reply) — labels get fused onto the sonar map and enrich your radar forever. LABELS ARE YOURS TO INVENT: there is no predefined list of objects — name things by whatever YOU observe (color, shape, size, "tall grey pillar", "small striped box"). Be consistent: reuse your own names for the same object. If a NEARBY sector shows an obstacle under ~800mm with "what": null and it is in your camera view, identifying and labeling it is a priority.
NAVIGATION GROUNDING — no invented bearings: you may only steer "toward X" if X appears in known_landmarks (use its live distance/bearing) or is clearly visible in the CURRENT image. If the mission target is in neither, you DO NOT know where it is — your task is to find it: slow perception-gated scan, then label it the moment it appears. Never fabricate a target direction from memory of text.
FACE BEFORE YOU CHASE: before issuing "drive toward X", check X's bearing in known_landmarks. If |bearing| > 25, first pivot toward it (fixed turned_deg sized to the bearing); the driver can hold a course and trim small bearings itself, but cannot fix a large initial error. Name the target in the subgoal text ("drive toward the green block") — the driver steers by that name's live bearing.
YOU ARE CALLED CONTINUOUSLY (~every 2-3s). You command the rover by CALLING ONE FUNCTION per reply; a hardcoded motion layer executes it precisely, measures its progress, and auto-stops if blocked (you get an event). Reissuing the SAME action lets it continue; a different action replaces it instantly; omitting "action" means "carry on".

ACTION LIBRARY — reply with "action": {{"name": "<fn>", "args": {{...}}}}:
- move {{"mm": -800..1200}} — drive straight (negative = reverse). Never exceed advance_budget_mm.
- turn {{"deg": -180..180}} — pivot in place. Positive = RIGHT (same sign convention as bearings).
- scan {{"direction": "left"|"right"}} — slow visual-search rotation at auto-computed speed; keeps rotating until you command otherwise. Use while hunting; LABEL the target the moment it appears. SCAN DISCIPLINE: visual_coverage.unseen_arcs_here shows which headings remain unlooked-at FROM THIS SPOT — pick ONE direction and HOLD IT until empty or the target is found; never flip mid-search. When angular coverage completes without success, the target is in a "?" region: relocate, do not re-scan.
- rotate_until_clear {{"direction": "left"|"right", "clearance_mm": 600..2000}} — turn until the forward cone shows at least that much room.
- goto {{"label": "<landmark>", "standoff_mm": 350..800}} — auto-steer to a labeled landmark and stop at standoff. ONLY for entries in known_landmarks (label it first).
- follow_waypoints {{"points": [{{"x":<mm>, "y":<mm>, "face"?: "<landmark to aim at on arrival>", "face_deg"?: <0-359 heading to aim>, "look_s"?: <0-6 seconds to STOP AND OBSERVE>}}, ...]}} — drive a plotted trajectory. A trajectory is not just locomotion: add LOOK-POINTS (face + look_s) where observing matters — a dwell gives you fresh, stationary camera frames at that spot (e.g. orbit arcs: face the target at each arc point with look_s 2). 4-6 points for complex routes. The ONLY clearance rule: no segment within 170mm of mapped geometry — corridors wider than ~400mm are passable through their CENTER. Paths are PRE-FLIGHT CHECKED against your own map: if a segment crosses mapped geometry you get "path_rejected" naming the segment and location — replot around it. Unscanned space cannot be pre-checked.
- turn_to {{"heading_deg": 0..359}} — rotate to an ABSOLUTE compass heading by the shortest way (precision ~0.5°).
- face {{"label": "<landmark>"}} — rotate until a labeled landmark is dead ahead (live-tracking; precision ~0.5°).
- mark {{"label": "<short name>", "x": <mm>, "y": <mm>}} — annotate your mind map with a point of interest. Instant; POIs appear on your map/grid and in telemetry with live distance/bearing. BEST USE — SEARCH BOOKKEEPING: after inspecting a face or viewpoint, mark it crossed-off (e.g. "purpleW-seen" at your viewing spot, "nothing-here"). Before searching anywhere, check your POIs: never re-inspect a marked face. This is YOUR ledger — invent whatever naming convention helps you.
- continue {{}} — explicitly keep the CURRENT action or path running, untouched. While a path is reporting progress, reply continue unless you have a stated reason to change — every replacement abandons the remaining points.
- stop {{}} — hold position (while purely looking or thinking).
PRECISION: all args are floats — turn/turn_to/face resolve to ~0.5°, move to ~1mm; motion auto-tapers on approach so small commands land accurately. Size moves with buffer (stop 100-150mm short and re-check) but do not fear fine adjustments.
CONTACT ESCAPE: if an action stops with "contact", you are TOUCHING something. The ONLY reliable first move is reverse: move {{"mm": -200}} (straight back along where you came from is guaranteed-known space). THEN turn/face and re-plot. Never re-issue forward motion or a path from a contact stop.

CURRENT ACTION: {subgoal}
ITS MEASURED PROGRESS: {progress}
LAST ACTION RESULT: {driver_status}
There is DELIBERATELY no orbit primitive — going around something is a THINKING task:
ORBIT RECIPE: read the target's map coordinates (grid + map_x/map_y), then plot an arc with follow_waypoints — 4-6 points spaced ~45-60° apart on a circle of radius 450-550mm around the target, starting from your side and sweeping to the far side. Check each point against the grid: never place one on or beside '#' cells or other letters; route the arc AWAY from walls and neighbors even if it means a wider detour. If the path stops early you will get a signal with WHERE it stopped and WHY — re-plot the remaining arc from that position, wider.
Typical patterns: hunting → scan until seen+labeled, then goto; hidden far face → goto, then plot an arc (ORBIT RECIPE); tight spot → rotate_until_clear then move; long route → follow_waypoints.

Reply ONLY JSON: {{"scene": "<exhaustive frame inventory, 40-80 words>", "observe": "<headline of what you see, <=15 words>", "assess": "<what it means for the current step, <=15 words>", "action": {{"name": "<fn from the library>", "args": {{...}}}}, "memory": "<working memory: current intent + key context, <=100 words — OMIT this field entirely to keep your previous memory unchanged (free); rewrite only when it should change>", "say": "<the decision, brief>", "check": "<YOUR success criterion for this action, <=15 words — it will be read back to you when the action completes>", "landmarks": [{{"label":"..","bearing_deg":<-45..45>,"distance_mm":<est>}}] (optional), "notes": [{{"label":"<your words>","x":<mm>,"y":<mm>}}] (optional — map annotations, FREE: they ride along with any action, cost nothing)}}"""

DRIVE_FAST_PROMPT = """Hobby robotics SIMULATOR (virtual toy rover, no real hardware). You are the fast low-level DRIVER of the simulated 2-wheel rover. TEXT ONLY — no camera. A planner gave you one subgoal; execute it using telemetry.
SUBGOAL: {subgoal}
DONE WHEN: {done_when}
MISSION CONTEXT: {mission}
LATEST SCENE (the vision layer's most recent frame read — your eyes, a few seconds old): {scene}

TELEMETRY (mm): {telemetry}

HARD LIMITS: if advancing and ultrasonic_front_mm < 300, STOP and report blocked=true. Never command forward when front < 250. {safety_mode}
NO REAR SENSOR: "rear_memory_mm" is remembered, not sensed. If rear_memory_mm < 400, reverse at 0.3 max. Prefer pivoting to face the travel direction and going forward over long reverses. "map_radar" = remembered obstacle distance per sector (3000 = unscanned, treat as unknown, not open).
WHEEL CONVENTION: forward = both positive. Turn/pivot LEFT = left NEGATIVE, right POSITIVE. Turn/pivot RIGHT = left POSITIVE, right NEGATIVE. heading_deg increases when turning left; use it to measure how far you have turned.
CONTINUOUS CONTROL: your left/right are TARGETS — motors RAMP toward them (a full swing takes about one of your command cycles). Think in adjustments, not jumps: nudge power up in open space, ease it down as distances shrink. Small corrections every call beat big rigid commands.
STEER BY BEARING: telemetry "known_landmarks" gives each labeled object's live bearing_deg (positive = it is to your RIGHT, negative = LEFT). If your subgoal names one of them, keep its bearing near 0 while advancing: bearing positive → raise left power / lower right (curve right); bearing negative → the opposite. Proportional: |bearing| 10 → gentle bias (±0.1); |bearing| 45 → strong (±0.3); |bearing| > 90 → pivot in place toward it before advancing. Its distance_mm falling confirms you are closing in.
Reply ONLY JSON: {{"left": <-1..1>, "right": <-1..1>, "done": <bool>, "blocked": <bool>, "say": "<max 8 words>"}}
done=true when DONE WHEN is met per telemetry. blocked=true if the subgoal cannot proceed safely."""

def sanitize_landmarks(cmd, sensors):
    lms = []
    known = {k.get("label") for k in sensors.get("known_landmarks", [])}
    for lm in (cmd.get("landmarks") or [])[:3]:
        try:
            label = str(lm.get("label", "")).strip()[:40]
            dist = float(lm.get("distance_mm", 0))
            if not label or label in known or dist < 100:
                continue
            known.add(label)
            lms.append({"label": label,
                        "bearing_deg": max(-90, min(90, float(lm.get("bearing_deg", 0)))),
                        "distance_mm": min(5000.0, dist)})
        except (TypeError, ValueError):
            pass
    return lms

def _cost(usage):
    tin, tout = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    return tin, tout, round(tin * PRICE_IN / 1e6 + tout * PRICE_OUT / 1e6, 6)

def sim_think(payload):
    key = openai_key()
    if not key: return {"error": "No OpenAI API key — add yours in the Settings section (left panel)"}
    sensors = payload.get("sensors", {})
    hist = payload.get("history") or []
    history = "\n".join(
        f'  ({h.get("s_ago","?")}s ago) "{h.get("subgoal","")}" -> {h.get("outcome","?")}'
        for h in hist) or "  (none yet)"
    tm = payload.get("timing") or {}
    timing = (f"you are called about every {tm.get('think_period_s','?')}s, "
              f"your last plan took {tm.get('think_latency_s','?')}s to arrive; "
              f"the driver acts about every {tm.get('drive_period_s','?')}s")
    evs = payload.get("events") or []
    events = "\n".join(f'  ({e.get("s_ago","?")}s ago) {e.get("type","?")}: {e.get("detail","")}'
                       for e in evs) or "  (none)"
    progress = str(payload.get("action_progress") or "(none)")
    plan_steps = payload.get("plan") or []
    step_idx = int(payload.get("step_idx") or 0)
    if plan_steps:
        plan_txt = "\n".join(
            f'  {"->" if i == step_idx else "  "} {i+1}. {s.get("step","")} (success: {s.get("success","")})'
            f'{" [DONE]" if i < step_idx else ""}'
            for i, s in enumerate(plan_steps))
        cur = plan_steps[min(step_idx, len(plan_steps)-1)]
        step_no, step_text, step_success = step_idx+1, cur.get("step",""), cur.get("success","")
    else:
        plan_txt, step_no, step_text, step_success = "  (no plan — act directly on the goal)", "-", "(n/a)", "(n/a)"
    safety_mode = ("code guards active (governor, standoff stop, recoil) as a backstop — "
                   "but plan as if they were not there."
                   if payload.get("guards")
                   else "NO CODE OVERRIDES ACTIVE. Nothing will stop the rover before contact "
                        "except your own mission sizing. Every collision is your planning failure.")
    rm = payload.get("recent_motion") or {}
    recent_motion = (f"rotated {rm.get('rotated_deg_15s', '?')} deg total, "
                     f"net displacement {rm.get('advanced_mm_15s', '?')} mm")
    tp = tm.get("think_period_s") or 5
    try: tp = float(tp)
    except (TypeError, ValueError): tp = 5
    # scan power sized so a perception-gated rotation covers ~<FOV per think cycle
    scan_power = round(min(0.15, max(0.04, 60/(tp*640))), 2)
    prompt = THINK_PROMPT.format(
        goal=payload.get("goal") or "Explore.",
        subgoal=payload.get("current_action") or payload.get("subgoal") or "(none yet)",
        driver_status=payload.get("driver_status", "(n/a)"),
        history=history,
        telemetry=json.dumps(sensors, indent=1),
        memory=(payload.get("memory") or "").strip() or "(empty)",
        recent_motion=recent_motion,
        timing=timing,
        env_desc=payload.get("env_desc") or "a walled area",
        situation=payload.get("situation") or "(not assessed)",
        events=events,
        progress=progress,
        safety_mode=safety_mode,
        scan_power=scan_power, think_period=tp,
        plan_progress=payload.get("plan_progress") or "  (no plan yet)",
        prev_scene=(payload.get("prev_scene") or "(first look — no previous scene)")[:700],
        map_grid=payload.get("map_grid") or "(no grid yet)",
        plan=plan_txt, step_no=step_no, step_text=step_text, step_success=step_success)
    tc = payload.get("think_count")
    if isinstance(tc, int) and tc > 0 and tc % 5 == 0:
        prompt += ("\n\nSTANDING QUESTION (asked periodically): is there anything you now know about "
                   "places in this arena that future-you would wish was written on the map? "
                   "If yes, add it to \"notes\" — it is free and rides along with your action.")
    if payload.get("strategy"):
        prompt += ("\n\nSEARCH STRATEGY (assigned for this experiment — follow it consistently):\n"
                   + str(payload["strategy"])[:500])
    prompt += ('\n\nIf your GOAL asks you to find/identify something, add an extra reply field ONLY '
               'when you can clearly read/see it in the camera image: "answer": {"number": <int>, '
               '"color": "<block color>"}. Never guess an answer. EYES BEAT THEORY: a clearly '
               'LEGIBLE digit on the target object IS the answer — answer immediately, even if '
               'you believe you are looking at the "wrong" face. The hidden-face hint tells you '
               'where to SEARCH; it is not a test for rejecting what you can plainly read. There '
               'is only one number on the target.')
    # instructions in the system role, observation in the user role — gpt-4o refused
    # ~2/3 of wall-of-imperatives user prompts; split structure tests 0/3 refusals
    img = payload.get("image")
    map_img = payload.get("map_image")
    parts = []
    if img:
        parts += [{"type": "text", "text": "Current camera view:"},
                  {"type": "image_url", "image_url": {"url": img, "detail": "low"}}]
    else:
        parts += [{"type": "text", "text": "No camera frame this call (camera feed disabled)."}]
    if map_img:
        parts += [{"type": "text", "text": "Your mind map (discovered knowledge only, grid in mm):"},
                  {"type": "image_url", "image_url": {"url": map_img, "detail": "low"}}]
    parts += [{"type": "text", "text": "Reply with the JSON."}]
    user_content = parts
    body = _mk_body(payload.get("model") or "gpt-4o-mini",
                    [{"role": "system", "content": prompt},
                     {"role": "user", "content": user_content}], 480)
    t0 = time.time()
    try:
        reply = _openai_post(body, key)
        latency_ms = round((time.time() - t0) * 1000)
        msg = reply["choices"][0]["message"]
        raw = msg.get("content")
        if raw is None:
            return {"error": "model refused: " + str(msg.get("refusal", "(no content)"))[:200],
                    "latency_ms": latency_ms}
        tin, tout, cost = _cost(reply.get("usage", {}))
        cmd = json.loads(raw)
        act = cmd.get("action") if isinstance(cmd.get("action"), dict) else {}
        name = act.get("name"); args = act.get("args") if isinstance(act.get("args"), dict) else {}
        clean = None
        def _f(v, lo, hi, dflt):
            try: return max(lo, min(hi, float(v)))
            except (TypeError, ValueError): return dflt
        if name == "move":
            clean = {"name": "move", "args": {"mm": _f(args.get("mm"), -800, 1200, 300)}}
        elif name == "turn":
            clean = {"name": "turn", "args": {"deg": _f(args.get("deg"), -180, 180, 45)}}
        elif name == "scan":
            clean = {"name": "scan", "args": {"direction": "left" if args.get("direction") == "left" else "right"}}
        elif name == "rotate_until_clear":
            clean = {"name": "rotate_until_clear", "args": {
                "direction": "left" if args.get("direction") == "left" else "right",
                "clearance_mm": _f(args.get("clearance_mm"), 600, 2000, 800)}}
        elif name == "goto":
            clean = {"name": "goto", "args": {"label": str(args.get("label", ""))[:30],
                     "standoff_mm": _f(args.get("standoff_mm"), 350, 800, 450)}}
        elif name == "follow_waypoints" or (name is None and cmd.get("waypoints")):
            pts = args.get("points") or cmd.get("waypoints") or []
            cpts = []
            for w in pts[:8]:
                try:
                    cp = {"x": _f(w["x"], -2300, 2300, 0), "y": _f(w["y"], -2300, 2300, 0)}
                    if w.get("face"): cp["face"] = str(w["face"])[:30]
                    if w.get("face_deg") is not None: cp["face_deg"] = _f(w["face_deg"], 0, 359.9, 0)
                    if w.get("look_s"): cp["look_s"] = _f(w["look_s"], 0, 6, 0)
                    cpts.append(cp)
                except (TypeError, KeyError): pass
            if cpts: clean = {"name": "follow_waypoints", "args": {"points": cpts}}
        elif name == "turn_to":
            clean = {"name": "turn_to", "args": {"heading_deg": _f(args.get("heading_deg"), 0, 359.9, 0)}}
        elif name == "face":
            clean = {"name": "face", "args": {"label": str(args.get("label", ""))[:30]}}
        elif name == "mark":
            clean = {"name": "mark", "args": {"label": str(args.get("label", "poi"))[:20],
                     "x": _f(args.get("x"), -2300, 2300, 0), "y": _f(args.get("y"), -2300, 2300, 0)}}
        elif name == "continue":
            clean = {"name": "continue", "args": {}}
        elif name == "stop":
            clean = {"name": "stop", "args": {}}
        out = {"action": clean,
               "subgoal": (clean["name"] + " " + json.dumps(clean["args"])) if clean else str(cmd.get("subgoal", ""))[:120],
               "scene": str(cmd.get("scene", ""))[:700],
               "observe": str(cmd.get("observe", ""))[:160],
               "assess": str(cmd.get("assess", ""))[:160],
               "memory": str(cmd.get("memory", ""))[:800],
               "say": str(cmd.get("say", ""))[:200],
               "latency_ms": latency_ms, "usage": {"in": tin, "out": tout},
               "cost_usd": cost, "context": prompt, "raw": raw, "model": body["model"]}
        lms = sanitize_landmarks(cmd, sensors)
        if lms: out["landmarks"] = lms
        nts = []
        for n in (cmd.get("notes") or [])[:3]:
            try:
                nts.append({"label": str(n.get("label", ""))[:24] or "note",
                            "x": _f(n.get("x"), -1150, 1150, 0), "y": _f(n.get("y"), -1150, 1150, 0)})
            except (TypeError, ValueError):
                pass
        if nts: out["notes"] = nts
        wps = []
        for w in (cmd.get("waypoints") or [])[:8]:
            try:
                wps.append({"x": max(-1150, min(1150, float(w["x"]))),
                            "y": max(-1150, min(1150, float(w["y"])))})
            except (TypeError, ValueError, KeyError):
                pass
        if len(wps) >= 1:
            out["waypoints"] = wps
        out["check"] = str(cmd.get("check", ""))[:120]
        out["step_done"] = bool(cmd.get("step_done", False))
        out["need_replan"] = bool(cmd.get("need_replan", False))
        ans = cmd.get("answer")
        if isinstance(ans, dict) and "number" in ans:
            try:
                out["answer"] = {"number": int(ans["number"]),
                                 "color": str(ans.get("color", ""))[:24]}
            except (TypeError, ValueError):
                pass
        add_usage(tin, tout, cost)
        session_log({"type": "think", "t": round(time.time(), 1), "tab": payload.get("tab"), "sensors": sensors,
                     "pose": payload.get("pose"), "recent_motion": rm,
                     "situation": payload.get("situation"), "events": evs,
                     "map_landmarks": payload.get("landmarks_map"),
                     "model": body["model"], "camera": bool(img),
                     "cmd": {"subgoal": out["subgoal"], "action": clean,
                             "scene": out["scene"],
                             "observe": out["observe"], "assess": out["assess"],
                             "say": out["say"], "check": out["check"], "memory": out["memory"], "landmarks": lms,
                             "answer": out.get("answer"), "notes": out.get("notes"),
                             "step_done": out["step_done"],
                             "need_replan": out["need_replan"], "step_idx": step_idx},
                     "usage": out["usage"], "cost_usd": cost, "latency_ms": latency_ms})
        return out
    except Exception as e:
        err = {"error": str(e)[:300], "latency_ms": round((time.time() - t0) * 1000)}
        session_log({"type": "error", "loop": "think", "t": round(time.time(), 1), **err})
        return err

def sim_drive_fast(payload):
    key = openai_key()
    if not key: return {"error": "No OpenAI API key — add yours in the Settings section (left panel)"}
    sensors = payload.get("sensors", {})
    prompt = DRIVE_FAST_PROMPT.format(
        subgoal=payload.get("subgoal") or "hold position",
        done_when=payload.get("done_when") or "(planner did not specify)",
        mission=(payload.get("mission") or "(none)")[:200],
        scene=(payload.get("scene") or "(no visual context yet)")[:700],
        safety_mode=("A code standoff override backstops you."
                     if payload.get("guards")
                     else "NO code safety stops exist: command into an obstacle and the rover WILL hit it."),
        telemetry=json.dumps(sensors))
    body = _mk_body(payload.get("model") or "gpt-4o-mini",
                    [{"role": "system", "content": prompt},   # TEXT ONLY — no image
                     {"role": "user", "content": "Reply with the JSON."}], 60)
    t0 = time.time()
    try:
        reply = _openai_post(body, key)
        latency_ms = round((time.time() - t0) * 1000)
        raw = reply["choices"][0]["message"]["content"]
        tin, tout, cost = _cost(reply.get("usage", {}))
        cmd = json.loads(raw)
        out = {"left": max(-1, min(1, float(cmd.get("left", 0)))),
               "right": max(-1, min(1, float(cmd.get("right", 0)))),
               "done": bool(cmd.get("done", False)),
               "blocked": bool(cmd.get("blocked", False)),
               "say": str(cmd.get("say", ""))[:80],
               "latency_ms": latency_ms, "usage": {"in": tin, "out": tout},
               "cost_usd": cost, "context": prompt, "raw": raw, "model": body["model"]}
        add_usage(tin, tout, cost)
        session_log({"type": "drive2", "t": round(time.time(), 1), "tab": payload.get("tab"), "sensors": sensors,
                     "pose": payload.get("pose"), "events": payload.get("events", []),
                     "cmd": {"left": out["left"], "right": out["right"], "done": out["done"],
                             "blocked": out["blocked"], "say": out["say"]},
                     "usage": out["usage"], "cost_usd": cost, "latency_ms": latency_ms})
        return out
    except Exception as e:
        err = {"error": str(e)[:300], "latency_ms": round((time.time() - t0) * 1000)}
        session_log({"type": "error", "loop": "drive", "t": round(time.time(), 1), **err})
        return err

# ---------- session logging (JSONL per autopilot run, study-able later) ----------
_sess_file, _sess_lock = None, threading.Lock()

def session_start(goal, guards=None, secret=None, tab=None, map_name=None):
    global _sess_file
    with _sess_lock:
        f = pdir("sessions") / (time.strftime("%Y%m%d-%H%M%S") + ".jsonl")
        f.write_text(json.dumps({"type": "session_start", "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                 "goal": goal, "guards": guards, "secret": secret, "tab": tab, "map": map_name}) + "\n")
        _sess_file = f
        return f.name

def session_log(rec):
    with _sess_lock:
        if _sess_file:
            with open(_sess_file, "a") as fh:
                fh.write(json.dumps(rec) + "\n")

def session_end(summary):
    global _sess_file
    session_log({"type": "session_end", "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "summary": summary})
    with _sess_lock:
        name = _sess_file.name if _sess_file else None
        _sess_file = None
    return name

# ---------- lab-lifetime usage accounting (persists across sessions) ----------
USAGE_F = ROOT / "usage.json"
_usage_lock = threading.Lock()
try:
    _usage = json.loads(USAGE_F.read_text())
except Exception:
    _usage = {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "calls": 0}

def add_usage(tin, tout, cost):
    with _usage_lock:
        _usage["tokens_in"] += tin
        _usage["tokens_out"] += tout
        _usage["cost_usd"] = round(_usage["cost_usd"] + cost, 6)
        _usage["calls"] += 1
        USAGE_F.write_text(json.dumps(_usage))

def _mk_body(model, messages, max_out):
    """Model-family param differences: gpt-5 wants max_completion_tokens + reasoning
    effort (minimal keeps latency sane for control loops)."""
    b = {"model": model, "messages": messages, "response_format": {"type": "json_object"}}
    if str(model).startswith("gpt-5"):
        b["max_completion_tokens"] = max_out + 150
        b["reasoning_effort"] = "minimal"
    else:
        b["max_tokens"] = max_out
    return b

# persistent keep-alive connection: saves TLS handshake (~100-300ms) per call
_oa_conn, _oa_lock = None, threading.Lock()

def _openai_post(body, key):
    global _oa_conn
    data = json.dumps(body).encode()
    hdrs = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    with _oa_lock:
        for attempt in (1, 2):
            try:
                if _oa_conn is None:
                    _oa_conn = http.client.HTTPSConnection("api.openai.com", timeout=30)
                _oa_conn.request("POST", "/v1/chat/completions", body=data, headers=hdrs)
                return json.loads(_oa_conn.getresponse().read())
            except Exception:
                try: _oa_conn.close()
                except Exception: pass
                _oa_conn = None
                if attempt == 2: raise

def sim_drive(payload):
    key = openai_key()
    if not key:
        return {"error": "No OpenAI API key — add yours in the Settings section (left panel)"}
    goal = payload.get("goal") or "Explore. Drive around, avoid obstacles."
    sensors = payload.get("sensors", {})
    memory = (payload.get("memory") or "").strip() or "(empty — this is your first call)"
    hist = payload.get("history") or []
    history = "\n".join(
        f'  [{h.get("left")}, {h.get("right")}] {h.get("say", "")}' for h in hist
    ) or "  (none yet)"
    prompt = DRIVE_PROMPT.format(goal=goal,
                                 telemetry=json.dumps(sensors, indent=2),
                                 memory=memory, history=history,
                                 cam_pan=sensors.get("cam_pan_deg", 0))
    body = {
        "model": payload.get("model") or "gpt-4o-mini",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": payload["image"], "detail": "low"}},
        ]}],
        "max_tokens": 280,   # room for memory + landmark fields
        "response_format": {"type": "json_object"},
    }
    t0 = time.time()
    try:
        reply = _openai_post(body, key)
        latency_ms = round((time.time() - t0) * 1000)
        raw = reply["choices"][0]["message"]["content"]
        usage = reply.get("usage", {})
        tin, tout = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        cmd = json.loads(raw)
        out = {"left": max(-1, min(1, float(cmd.get("left", 0)))),
               "right": max(-1, min(1, float(cmd.get("right", 0)))),
               "say": str(cmd.get("say", ""))[:200],
               "memory": str(cmd.get("memory", ""))[:800],
               "latency_ms": latency_ms,
               "usage": {"in": tin, "out": tout},
               "cost_usd": round(tin * PRICE_IN / 1e6 + tout * PRICE_OUT / 1e6, 6),
               "context": prompt,          # exact text sent alongside the image
               "raw": raw,                 # exact model reply
               "model": body["model"]}
        lms = []
        known = {k.get("label") for k in sensors.get("known_landmarks", [])}
        for lm in (cmd.get("landmarks") or [])[:3]:
            try:
                label = str(lm.get("label", "")).strip()[:40]
                dist = float(lm.get("distance_mm", 0))
                # reject junk: empty/duplicate labels, degenerate distances (0mm reports
                # observed in session 124208 — they'd map to the rover's own position)
                if not label or label in known or dist < 100:
                    continue
                known.add(label)
                lms.append({"label": label,
                            "bearing_deg": max(-90, min(90, float(lm.get("bearing_deg", 0)))),
                            "distance_mm": min(5000.0, dist)})
            except (TypeError, ValueError):
                pass
        if lms:
            out["landmarks"] = lms
        session_log({"type": "drive", "t": round(time.time(), 1),
                     "sensors": sensors, "pose": payload.get("pose"),
                     "events": payload.get("events", []),
                     "cmd": {"left": out["left"], "right": out["right"],
                             "say": out["say"],
                             "memory": out["memory"], "landmarks": lms},
                     "usage": out["usage"], "cost_usd": out["cost_usd"],
                     "latency_ms": latency_ms})
        return out
    except Exception as e:
        err = {"error": str(e)[:300], "latency_ms": round((time.time() - t0) * 1000)}
        session_log({"type": "error", "t": round(time.time(), 1), **err})
        return err

# ---------- HTTP ----------
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))

    def do_GET(self):
        if self.path == "/api/projects":
            out = []
            for p in sorted(PROJECTS.iterdir()):
                if p.is_dir():
                    n = len(list((p / "models").glob("*.stl"))) if (p / "models").is_dir() else 0
                    out.append({"name": p.name, "models": n, "active": p.name == active()})
            return self._json(out)
        if self.path == "/api/project":
            a = active()
            if not a: return self._json({"error": "no projects"}, 404)
            meta = json.loads((PROJECTS / a / "project.json").read_text()) if (PROJECTS / a / "project.json").exists() else {"name": a}
            parts = json.loads((PROJECTS / a / "parts.json").read_text()) if (PROJECTS / a / "parts.json").exists() else {"parts": []}
            return self._json({**meta, **parts, "freecad": bool(find_freecadcmd()),
                               "llm_key": bool(openai_key())})
        if self.path == "/api/models":
            d = pdir("models")
            return self._json([{"name": f.name, "size": f.stat().st_size, "mtime": f.stat().st_mtime}
                               for f in sorted(d.glob("*.stl"))] if d else [])
        if self.path == "/api/settings":
            k = openai_key()
            return self._json({"key_set": bool(k),
                               "key_hint": (k[:5] + "…" + k[-4:]) if k else None,
                               "source": "env" if os.environ.get("OPENAI_API_KEY") else
                                         ("config" if _config().get("openai_api_key") else None)})
        if self.path == "/api/usage":
            with _usage_lock:
                return self._json(dict(_usage))
        if self.path == "/api/sessions":
            d = pdir("sessions")
            out = []
            for f in sorted(d.glob("*.jsonl"), reverse=True):
                lines = f.read_text().strip().split("\n")
                first = json.loads(lines[0]) if lines else {}
                lastl = json.loads(lines[-1]) if lines else {}
                out.append({"file": f.name, "goal": first.get("goal", ""),
                            "records": len(lines),
                            "summary": lastl.get("summary") if lastl.get("type") == "session_end" else None})
            return self._json(out)
        if self.path == "/api/mtimes":
            d = pdir("models")
            return self._json({f.name: f.stat().st_mtime for f in d.glob("*.stl")} if d else {})
        if self.path.startswith("/models/"):
            fname = os.path.basename(self.path.split("?")[0])
            fpath = pdir("models") / fname
            if fpath.is_file():
                data = fpath.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            return self._json({"error": "not found"}, 404)
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/projects":
            name = "".join(c for c in self._read().get("name", "") if c.isalnum() or c in "-_").strip()
            if not name: return self._json({"ok": False, "error": "bad name"}, 400)
            base = PROJECTS / name
            for sub in ["designs", "models", "snapshots", "exports"]:
                (base / sub).mkdir(parents=True, exist_ok=True)
            if not (base / "project.json").exists():
                (base / "project.json").write_text(json.dumps(
                    {"name": name, "created": time.strftime("%Y-%m-%d"), "notes": ""}, indent=2))
            if not (base / "parts.json").exists():
                (base / "parts.json").write_text('{"parts":[]}')
            set_active(name)
            return self._json({"ok": True, "name": name})
        if self.path == "/api/projects/open":
            name = self._read().get("name", "")
            if not (PROJECTS / name).is_dir(): return self._json({"ok": False}, 404)
            set_active(name)
            return self._json({"ok": True})
        if self.path == "/api/parts":
            (pdir() / "parts.json").write_text(json.dumps({"parts": self._read().get("parts", [])}, indent=2))
            return self._json({"ok": True})
        if self.path == "/api/snapshot":
            payload = self._read()
            ts = time.strftime("%Y%m%d-%H%M%S")
            d = pdir("snapshots")
            img = payload.get("image", "")
            if img.startswith("data:image/png;base64,"):
                (d / f"{ts}.png").write_bytes(base64.b64decode(img.split(",", 1)[1]))
            (d / f"{ts}.json").write_text(json.dumps({
                "time": ts, "note": (payload.get("note") or "").strip(),
                "models_visible": payload.get("models", []),
                "camera": payload.get("camera", {})}, indent=2))
            return self._json({"ok": True, "saved": [f"{ts}.png", f"{ts}.json"]})
        if self.path == "/api/export":
            stem = Path(self._read().get("model", "")).stem
            return self._json(export_step(stem))
        if self.path == "/api/sim/drive":
            return self._json(sim_drive(self._read()))
        if self.path == "/api/sim/think":
            return self._json(sim_think(self._read()))
        if self.path == "/api/sim/plan":
            return self._json(sim_plan(self._read()))
        if self.path == "/api/sim/drivefast":
            return self._json(sim_drive_fast(self._read()))
        if self.path == "/api/settings":
            key = str(self._read().get("openai_api_key", "")).strip()
            cfg = _config()
            if key: cfg["openai_api_key"] = key
            else: cfg.pop("openai_api_key", None)
            CONFIG_F.write_text(json.dumps(cfg))
            try: os.chmod(CONFIG_F, 0o600)
            except OSError: pass
            return self._json({"ok": True, "key_set": bool(openai_key())})
        if self.path == "/api/session/start":
            p = self._read()
            return self._json({"ok": True, "file": session_start(p.get("goal", ""), p.get("guards"),
                                                                 p.get("secret"), p.get("tab"), p.get("map"))})
        if self.path == "/api/session/end":
            return self._json({"ok": True, "file": session_end(self._read().get("summary", {}))})
        return self._json({"error": "unknown endpoint"}, 404)

def bootstrap():
    PROJECTS.mkdir(exist_ok=True)
    if not any(p.is_dir() for p in PROJECTS.iterdir()):
        base = PROJECTS / "demo"
        for sub in ["designs", "models", "snapshots", "exports", "sessions"]:
            (base / sub).mkdir(parents=True, exist_ok=True)
        (base / "project.json").write_text(json.dumps(
            {"name": "demo", "created": time.strftime("%Y-%m-%d"),
             "notes": "Default project — sessions and snapshots land here."}, indent=2))
        (base / "parts.json").write_text('{"parts":[]}')

if __name__ == "__main__":
    bootstrap()
    os.chdir(UI)
    print(f"Robotics Lab v2 -> http://127.0.0.1:{PORT}  (active project: {active()})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
