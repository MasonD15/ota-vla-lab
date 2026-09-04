# CLAUDE.md — OTA-VLA Lab

Browser robotics sim where cloud LLMs (OpenAI API) drive a simulated rover like a
VLA model. Zero-dependency Python stdlib server + Three.js UI. Public repo
(github.com/MasonD15/ota-vla-lab), MIT, author Mason DuPree.

## Run / dev
```bash
python3 server.py            # -> http://127.0.0.1:8321/sim.html
lsof -ti:8321 | xargs kill   # stop (ALWAYS restart after editing server.py)
# smoke-test after UI edits (title shows load-time JS errors via built-in catcher):
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
  --dump-dom --virtual-time-budget=3000 http://127.0.0.1:8321/sim.html | grep title
```
API key: Settings section in UI → `config.json` (gitignored) or `OPENAI_API_KEY` env.

## Architecture (4 layers, top→bottom)
1. **Planner** (LLM, gpt-4.1, once/mission): mission → steps with machine-checkable
   checks (`landmark_known` / `near_landmark` / `telemetry` / `perception`).
2. **Thinker** (LLM, free-running ~0.3Hz, vision + mind-map image + ASCII grid):
   emits ONE `action {name,args}` per reply + scene/observe/assess/say/memory/
   landmarks/notes/check/forget. Model selectable in UI (gpt-4.1 default).
3. **Motion layer** (code, in `step()` @60fps): executes primitives — move, turn,
   turn_to, face, goto, scan, rotate_until_clear, follow_waypoints (look-points:
   face/look_s per point), mark, continue, stop. Measured progress, speed taper,
   pre-flight path validation vs occupancy (170mm rule).
4. **Physics/safety** (code): slew-limited motors, watchdog (2.5s), optional guards
   (governor/standoff/recoil — "informed-only" mode off by default), collision
   events, bumper-origin sensors (0 = touching, hull RADIUS=110).

## Key files
- `server.py` — all endpoints + ALL PROMPTS (THINK_PROMPT, PLAN_PROMPT, sanitizers)
- `ui/sim.html` — sim, physics, executor, maps, mind map, all client logic (one file)
- `ui/arena.html` — 10-strategy tournament (STALE: pre-action-era API, needs retrofit)
- `LAB_NOTES.md` — the engineering journal. EVERY feature/failure gets an entry
- `NOTABLE_MOMENTS.md` — preserved runs (#1 eyes-vs-theory, #2 first win)
- `projects/<p>/sessions/*.jsonl` — full telemetry logs (gitignored); review via
  python scripts reading think/drive2/plan/session_start records

## Design laws (hard-won — see LAB_NOTES for evidence)
1. **LLM = semantics & choice; code = geometry, execution, measurement, safety.**
   Prose rules WILL eventually be ignored (~6 confirmed cases) — safety and
   bookkeeping must be code.
2. **"Long-horizon" = missing progress variable.** Give progress a number
   (turned_deg, swept°, map_seen_pct) and the horizon collapses.
3. **Elicitation, not scripting**: code may shape affordances (free notes field),
   incentives (durability framing), and mirrors (factual situation lines —
   STATIONARY, TRAIL CROSSING, PHANTOM SUSPECT, REPEATING) — never the ontology
   or the decision. No object inventories in any prompt (de-hardcoded 09-02).
4. **One source of truth per rule** — overlapping safety geometries contradict
   (the 450mm-clamp vs pre-flight corridor trap).
5. Landmarks: image-convention bearings (positive=RIGHT); place with CAPTURE-time
   pose; positions self-refine toward sonar clusters; same-label far apart =
   numbered twins; corrective re-reports + `forget` allowed.

## Gotchas / never-do
- `<script>` is one big top-level block: referencing a `const` before its line =
  TDZ crash that kills the whole page (happened 2×: hullRing, mapSpawn). The title
  error-catcher + frame-loop armor report these — CHECK THE TITLE after edits.
- Never bulk replace_all code text (`stopMotors` self-recursion incident).
- Multiple sim tabs corrupt session logs (server log is a singleton) — red banner
  warns; keep one tab.
- gpt-4o refuses agentic prompts in user role — instructions go in system role.
- gpt-5 family needs `max_completion_tokens` + `reasoning_effort` (see `_mk_body`).
- Never commit config.json/usage.json/sessions (gitignored; audit before push).
- Mason's OpenAI key comes from env here; NEVER hardcode paths to his dotfiles.

## Conventions
- Every change: LAB_NOTES entry (Added/Observed) + commit + push (repo is the doc).
- Reviews = read newest sessions/*.jsonl, measure, then fix root causes.
- Verify prompts changes with a curl to /api/sim/think using a synthetic payload.
- Maps: a map = build function + env_desc sentence + spawn point (see buildWorld).
