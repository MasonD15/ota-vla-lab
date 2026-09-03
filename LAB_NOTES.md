# Robotics Lab — Feature & Performance Notebook

## 2026-09-02 — Sensor calibration bug (Mason's catch): sonar measured from CENTER
**Mason asked the right instrument question: "would a front-mounted ultrasonic read
zero flat against a wall?" Answer: NO — it read 110mm.** Rays marched from the
rover's CENTER, so every distance the AI ever received was inflated by its own
hull radius. Related visual confusion: the physics hull is a 110mm circle
(≈ the body's corner diagonal), so side-on the rover LOOKS ~20mm short of things
it is physically touching — hitbox and mind map disagreed with the eye.
**Fixed:**
1. All REPORTED distances re-origined to the front bumper (0 = touching):
   ultrasonics, forward_clearance, radar sectors, rear memory. Verified: flush
   wall = 0mm, 100mm gap = 100mm. Internal geometry (occupancy, landmarks,
   collision) stays center-based — world coordinates were always correct.
2. Budgets recomputed for the new origin (bumper clearance − 40mm margin —
   numerically equivalent to before, so behavior unchanged; meaning now honest).
3. Prompt: "all distances measured from your FRONT BUMPER — 0 = touching";
   contact threshold text 200→100mm.
4. THE HULL IS NOW VISIBLE: a translucent green ring at true collision radius on
   the 3D rover and a matching circle on the mind map — "touching" finally looks
   like touching. Sim-to-real note: on the physical rover this same offset exists
   (sensor mount position vs hull extent) and must be calibrated identically.


## 2026-09-02 — De-hardcoding the ontology (Mason's catch)
**Mason noticed the object inventory was leaking into the AI:** the planner prompt
literally listed "five colored blocks (red, blue, green, yellow, purple)"; the
label-conflict guard and the scene auto-label extractor both hardcoded the same
color palette. The AI wasn't discovering the world — it was confirming a cheat
sheet. All three removed:
1. Planner now told the arena CONTENTS ARE UNKNOWN — discovery/naming/mapping is
   the rover's job.
2. Thinker told labels are ITS OWN INVENTION — name objects by whatever it
   observes; be self-consistent. No predefined list anywhere in its context.
3. Code generalized: conflict guard compares the AI's own first descriptor words
   (any vocabulary); auto-label extraction now parses any "<descriptor> <object-
   noun>" phrasing (block/cube/box/pillar/object/obstacle) with a stopword filter.
The mission may still NAME its target ("the yellow block") — that's the task
brief, not a world inventory. Ground-truth block definitions remain only in the
WORLD-BUILDING code (the sim must construct something) and the answer scorer —
neither is visible to any model. The system is now genuinely
randomization-ready: change shapes, colors, counts — nothing in the AI's context
would know the difference.


## 2026-09-01 — The best near-miss yet: read the answer, drove on (session 172348)
**→ Preserved verbatim with full analysis in NOTABLE_MOMENTS.md (#1) — per Mason:**
**the model followed the mission direction BETTER than expected; over-fidelity,**
**not failure. Raw think record embedded there permanently.**
**Huge progress run:** clean goto→approach→plot→arc sequence, contact-escape reverse
used correctly (twice), waypoint navigation "very cool" (Mason). And at think 9 its
own scene read: "left edge of the purple block (NUMBER 3 VISIBLE, but this is the
near face)" — the secret WAS 3-on-purple. It read the correct answer aloud and
REJECTED it, theorizing it was looking at the wrong face (it was standing between
block and wall — i.e., almost certainly looking AT the away face). Epistemology
bug: inference overrode direct observation.
**Fixed:**
1. *EYES BEAT THEORY doctrine* — a clearly legible digit on the target IS the
   answer, regardless of which face you believe it is; the hidden-face hint says
   where to search, not what to reject. (There is only one number.)
2. *Scene-digit watchdog (code net)* — if its own scene text mentions a digit while
   a hunt goal names a target, the situation headline screams: ANSWER NOW.
3. *Mason's seen-faces doctrine for mark* — POIs as the AI's OWN search ledger:
   cross off inspected faces/viewpoints with its own naming convention ("purpleW-
   seen"); check POIs before re-searching. Deliberately un-hardcoded — shapes and
   environments change; the convention lives in the model, the persistence in code.


## 2026-09-01 — Wedged-on-target diagnosis + precision/marking package (Mason)
**Session 171728 stuck cause:** blue's landmark was ~480mm off truth; goto steered
at the phantom, physically hit the real block en route (informed-only = no stop),
ended WEDGED IN CONTACT — where every plotted path's first hop instantly re-blocked
(7x action_blocked). And it never tried reverse — the one guaranteed exit.
**Added (Mason's package):**
1. *CONTACT ESCAPE doctrine* — contact stop → reverse first (move -200; the space
   behind is guaranteed-known), then turn/face, then re-plot. Never re-issue
   forward from contact.
2. *Precision*: motion tapers on approach (turn: 0.3→0.12→0.05 power at 20°/6°
   remaining; move: 0.5→0.25→0.12 at 120/30mm) — fine commands land accurately;
   args are floats (~0.5° / ~1mm resolution). Prompt: buffer distances, re-check.
3. *turn_to(heading_deg)* — absolute-heading rotation, shortest way; *face(label)*
   — live-tracking rotation until a landmark is dead ahead.
4. *mark(label,x,y)* — thinker annotates its own map with POIs (blue diamonds on
   both maps, lowercase letters in grid, live distance/bearing in telemetry).
   Planning artifacts now persist spatially, not just in prose memory.
5. *Map fidelity*: mapShot 360→512px, bigger dots; grid 16x150mm → 24x100mm cells;
   and LANDMARK REFINEMENT — every 2s each label drifts 30% toward the nearest
   scanned cluster within 450mm, so placement error self-corrects as sonar
   densifies (attacks the root cause of the wedge directly).


## 2026-09-01 — The armor catches its first bug + search coverage (Mason's ask)
**ROOT CAUSE OF THE FREEZES FOUND — by the new error armor, first session:**
js_error events captured an infinite recursion: stopMotors() called ITSELF —
an old bulk replace_all ("state.l=0; state.r=0;" → "stopMotors();") had rewritten
the function's own body. Every idle watchdog tick → stack overflow → dead frame
loop. Explains the frozen camera AND "plotted but never moved." One-line fix.
Lesson recorded: bulk text replacement is not refactoring; and error telemetry
pays for itself immediately.
**Scan oscillation diagnosed (session 171130):** 18 consecutive scans flipping
right/left every ~4 thinks, pinballing 167°-336°, NEVER covering 0-160° — where
the target was. Cause: no representation of where it has already looked.
**Added (Mason's design):**
1. *Visual coverage tracking* — 36x10° world-heading buckets marked as looked-at
   (~70° FOV per frame), reset when the rover relocates >300mm. Fed to the AI as
   visual_coverage {pct, unseen arcs}; prompt adds SCAN DISCIPLINE: one direction,
   hold until unseen empty; never flip.
2. *Coverage fan on both maps* — translucent wedges around the rover showing
   searched directions, drawn in the user mind map AND in the AI's mapShot.
3. *"What the AI receives" panel* — the actual map image + ASCII grid sent to the
   thinker, displayed in the UI each think. No more guessing what it sees.


## 2026-09-01 — Orbit demoted to thinking; grid map; rich stop signals (Mason)
**Log review (session 165309, green hunt) confirmed Mason's critique of the blind
orbit:** it swept 49° then drove its fixed circle into the wall zone (6 collisions,
5 thinks of recovery flailing) — a hardcoded arc can't see. Poetic detail: the
model's final move was follow_waypoints, "plotting a safe path around the green
block" — it invented the replacement on its own.
**Changes:**
1. *Orbit primitive REMOVED.* Going around is now a THINKING task: ORBIT RECIPE in
   the prompt — plot 4-6 arc points (45-60° apart, r=450-550) around the target's
   map coords with follow_waypoints, checked against the grid, routed away from
   walls/neighbors. (Verified: wall-adjacent far-face scenario → correct arc shape,
   W→N→behind; radii came in tight at 100-224mm but the 450mm clearance clamp
   pushes them out — prompt suggests, code guarantees.)
2. *Rich stopped-signals upward* (Mason's ask): any blocked action now events with
   WHAT stopped, contact-vs-standoff, measured progress at stop, pose, heading,
   and obstruction distance — ending "re-plot AROUND this spot." Failed motion is
   now a well-described replanning input, not a mystery.
3. *Grid-array mind map* (Mason's ask): 16x16 ASCII grid (150mm cells) alongside
   the map image — '.' unknown, '#' scanned obstacle, letters = labeled blocks,
   '@' = rover, plus legend + cell→mm conversion. ~120 tokens; gives the planner
   numeric cells to reason over instead of only pixels.


## 2026-09-01 — FUNCTION-CALLING ARCHITECTURE (Mason's redesign): actions replace missions
**The big pivot:** thinker now commands via a fixed function library; a hardcoded
motion layer executes. The LLM DRIVER IS RETIRED (halves LLM traffic; kills its
compliance/latency issues permanently). Natural language retained ("say" +
observe/assess/scene) so the thought process stays readable.
**Action library (all code-executed, all with measured progress):**
move(mm) · turn(deg, +=right) · scan(direction, auto-speed ≤50°/think-gap) ·
rotate_until_clear(direction, clearance) · goto(label, standoff — bearing-servo) ·
**orbit(label, deg, cw/ccw — radial-hold + tangential steer, progress = degrees
swept)** · follow_waypoints(points — clamp+densify) · stop.
**Mechanics:** one action per think; same action = continue, different = replace,
absent = carry on. Server sanitizes args (clamps, landmark existence). Blocked
(standoff/collision) auto-clears the action + events the thinker. goto/orbit
require the landmark to be labeled first (grounding by construction). Planner told
to write steps that map onto the library.
**Verified first-try:** far-face scenario → orbit{green,180,cw}; hunt scenario →
scan{right}. The maneuver that failed for 3 days (0° sweep over 11 thinks) is now
one function call with code-measured sweep.
This completes the lab's arc: LLM = semantics + choice; code = geometry, execution,
measurement, safety. The interface between them is now a typed function boundary —
same shape as the real Pi rover's future API.


## 2026-08-31 — Session 223457: "why didn't it label green?" — seen-but-not-labeled
**Mason's question answered from the log:** it did NOT spin past green — at h=93 its
own scene read "Large green block dominates the right side, 400mm away" and it even
switched subgoal to "drive toward the green block"… while emitting NO landmark.
The landmark_known step check never fired, the plan stayed on "scan," and it went
back to searching for a block it had already found. 5th confirmed case of duty-drop
under attention (the exciting moment — target found — is exactly when labeling gets
skipped). Secondary: scan hopped 90-180°/look — the ±0.09 clamp assumed ~2.5s think
cadence but gpt-4.1 default = 4s floor + 2s latency = 6.2s gaps; plus some scans
came back turned_deg-typed, dodging the clamp.
**Fixed (code does the bookkeeping, per the law):**
1. *Auto-label from scene text* — the mandated scene format already contains
   "<color> block … Nmm … N deg left/right"; code regex-extracts any color block
   the model described but failed to put in landmarks and ingests it through the
   normal pipeline (occ-snap, conflict guard). Duty-drop no longer costs anything;
   logged as auto_label events.
2. *Dynamic scan clamp* — rotation capped at ≤50°/measured-think-gap (not a fixed
   power), and the clamp now also applies whenever the CURRENT STEP is a
   landmark_known search regardless of done_when type.
3. gpt-4.1 think floor 4000→2000ms (latency ~2s → ~2.5-3s looks).
4. Prompt: SEARCH LABELING PRIORITY — labeling the sought object outranks
   everything; scene description is not enough.

## 2026-08-31 — Mind's eye + plotted paths (Mason's design; the orbit answer)
**Added, following the 0°-sweep result:**
1. *Mind's-eye map to the thinker* — second image per think: ITS OWN discovered map
   (never ground truth; environment-randomization-safe): sonar dots, labeled
   landmarks with (x,y) mm, trail, rover arrow + printed pose, coordinate grid.
   Landmarks also carry map_x/map_y numerically; pose_mm in telemetry. Low-detail
   second image ≈ +90 tokens.
2. *Plotted paths* — thinker may reply "waypoints":[{x,y}...] (2-6, map mm); CODE
   executes them (pivot→advance w/ proportional steer, arrive<120mm→next) at
   physics rate, feeds the watchdog, reports "waypoint k/n, Xmm" upward. Clearance
   clamp pushes plotted points ≥350mm from known landmarks (4.1 plotted one inside
   a block). LLM driver + done-checks suspend while a path runs; fresh ordinary
   mission supersedes. Orange path overlay on the mind map.
3. Prompt mandate: go-around/far-side steps MUST be waypoints (turning cannot
   achieve them).
**Model finding — plotting is a capability cliff:** gpt-4.1 plotted 1/1 with an
excellent sweep (W→N→E ending at the true far face); gpt-5-mini 1/2 (mediocre);
gpt-4.1-mini 0/3 even under mandate (reverts to turn habits). → thinker default
switched to gpt-4.1. Its old rotated-digit weakness is moot (digits are upright
sign planes now).
_(pending: live orbit run — swept-angle through the plotted path, does step 3
finally complete + read the number?)_

**First live path run (Mason watched): plotted but STALLED.** Three defects fixed:
1. *Sparse routes* — ~2 waypoints can't trace a curve; prompt now mandates 4-6 for
   go-arounds AND code densifies every segment into 300mm hops (≤24 pts) — the
   route now appears as a full dotted curve on the mind map ("routes get mapped").
2. *Clearance too tight* — 350mm from an ESTIMATED center (~200mm map error +
   130mm half-extent) can sit inside the 230mm physics standoff → mission blocks →
   freeze. Clamp widened to 450mm; prompt teaches ≥450.
3. *Silent stall* — a blocked mission left wpActive frozen forever. Now any block
   (standoff or collision) CLEARS the path + fires "path_blocked" event telling
   the thinker to replot wider.

## 2026-08-31 — Dense semantics + detailed progress (Mason's two experiments)
**1. Pixels→tokens at max rate:** thinker now MUST emit "scene" every call — an
exhaustive frame inventory (every object w/ color/kind, distance via 200mm tiles,
bearing, size; walls/corridors/gaps; digits + which face), 40-80 words telegraphic.
Previous scene fed back next call for continuity ("note what changed"). Scene shown
in the story feed (🎞) and logged per think — the session logs are now a dense
perceptual record (also ideal future VLA training data). Output budget 300→480.
**2. Rich reading down, tiny output out (Mason's split):** the fast driver now
RECEIVES mission context (step N/M) + the latest scene (~few s old) — but its
output schema is unchanged (left/right/done/blocked/say≤8 words). Reading is cheap;
generation is latency.
**3. Detailed mission progress upward:** code-computed per-step report in every
think: "✓ step 1 DONE 34s ago / ▸ step 2 CURRENT: approach red — 663mm from red
block, need ≤500 / · step 3 pending". Landmark-relative distances measured live.
**Measured (first calls):** scene ~38-80 words; think out tokens ~60→147; cost
$0.00025→$0.00048/think; latency ~+1s (3.6s cold, expect ~2.5s warm). The limit
dials: scene word budget (40-80) and output cap (480) — push until latency hurts.
**RESULT (session 221800, purple hunt) — the experiment answered cleanly:**
- IMPROVED: scene inventories rich and accurate (colors all correct, tile-counted
  distances, wall/corridor descriptors — 44 words avg, 2.7s med latency); locate
  instant (1 think); approach clean (901→627mm); steps auto-advanced correctly.
- NOT IMPROVED — the decisive part: step "circle around" ran 11 thinks with
  **0° of orbital sweep** (parked at d=640, orbit-angle 197° the whole time),
  issuing pure rotational thrash (turn left/right/left...) while narrating the
  scene PERFECTLY. It knew where it was, what surrounded it, what the step was —
  and still could not produce the maneuver. 11 collisions while wedged near the
  red block (informed-only mode).
**Conclusion: semantics was not the bottleneck for the orbit. Dense scene +
explicit progress ≠ trajectory generation. The theory holds: "go around" needs a
code-measured motion primitive (orbit mission type with swept-angle progress),
not more understanding.** This was the cheap way to prove it before building.

## 2026-08-28 — Session 211024: FIRST FULLY-CORRECT MAP + the two-tab bug
**Milestone: final fused map 5/5 blocks correctly labeled** (errors 168-395mm, every
label on the right block). The color-conflict guard fired in the wild and WORKED:
a farther look claimed "yellow" where purple lives → kept purple (Mason watched the
self-correction live and doubted his own eyes — the event log confirms it).
**Bug Mason caught: plan said purple, mission said yellow.** Plan record's logged
goal = "Explore the arena" (default) while session goal = yellow hunt. Cause:
MULTIPLE SIM TABS — server session logging is a global singleton, so a stale tab
(default goal, autopilot on) interleaved its plan into the active tab's session.
We had open()ed the sim ~8 times today.
**Fixed:** per-tab identity (TAB_ID) in every payload + logged in every record
(think/drive/plan/session_start) so reviews can attribute; localStorage heartbeat
shows a red banner when another live sim tab is detected. → Close old tabs.

## 2026-08-28 — Camera pan REMOVED (Mason's scope call)
**Removed the pan servo from the prototype entirely**: camera is now fixed forward.
Looking elsewhere = turn the rover; seeing a far face = drive around it. Stripped
from: thinker prompt (+"THE CAMERA IS FIXED" rule), planner prompt (never write
camera-pan steps), reply schema, telemetry (cam_pan_deg gone), client actuation.
**Why:** (1) matches the simplest physical build (one less servo/wire/failure mode);
(2) eliminates the pan-deadlock class permanently — session 210423's freeze was
pan-confusion; no actuator, no confusion; (3) fewer action dimensions = simpler
missions for the LLM stack. The pan hardware can return later as its own upgrade
if fixed-camera hunts prove it's needed (that would then be a measured decision).
Landmark bearing math simplified (capture heading only). Repetition detector +
forced replan retained as the general anti-deadlock backstop.

## 2026-08-28 — Session 210423 (yellow hunt): best run yet + the pan-deadlock
**Confirmed working (three same-day fixes verified in one run):**
- **Mind map CORRECT for the first time**: final audit yellow 192mm / green 226mm /
  purple 170mm error, every label on the right block (capture-pose fix).
- Scan found target in ~1 revolution (~100°/look, clamp working); face-before-chase
  used real bearings ("turn right to face yellow at bearing 102"); approach closed
  929→509mm.
- Wrong-answer flow exercised: answered {1, yellow} vs truth {2, yellow} — misread
  the digit at a glancing angle; rejected, search continued. (Digit-at-angle is
  gpt-5-mini's benchmark edge — use it for hunts.)
**New failure — the pan deadlock:** final 10 thinks identical, rover frozen:
subgoal "Pan camera left to inspect far face". Action-space mismatch: cam_pan is
the THINKER's reply field, but it kept requesting the pan as a DRIVER mission; the
driver (wheels only) idled; frame never changed; loop forever. Also step 2 (orbit)
auto-passed via a weak telemetry check, so it never actually reached the far side.
**Fixed:** (1) prompt: camera pan is YOUR actuator, never a subgoal; to see a far
face DRIVE around, don't pan at it; (2) code repetition detector: same subgoal
3x with <80mm displacement → situation() flags "REPEATING YOURSELF — approach NOT
WORKING"; 6x → forced replan (logged as forced_replan event).

## 2026-08-28 — Session 205719 (red hunt): narration works; think-latency overshoot found
**First narrated session — the observe/assess stream made diagnosis trivial.**
- Scan phase: honest perception every cycle ("no red; only purple and blue"), all
  labels correct, red found + step auto-advanced. BUT poses show 310-320 deg of
  rotation BETWEEN looks (scan far too fast for the think cadence) — 2.5 revolutions
  before red was caught in a snapshot.
- **The error: think-latency overshoot at the scan→chase handoff.** "Red directly
  ahead" → mission swap takes ~2s → still-running rotation carried the nose ~200 deg
  past → next narration honestly says "no red visible yet" → first advance went the
  OPPOSITE direction (674→855mm). Recovery worked (real bearing-guided turns, "49
  deg"/"27 deg" from the map) but led into the green block's standoff zone; session
  expired mid-escape. No collisions with narration-era reasoning failures — purely
  mechanical.
**Fix:** code clamp — perception-mission motor targets capped at ±0.09 (~16 deg/s):
one think cycle can no longer sweep past a 70-deg FOV. Prompt guidance alone had
been ignored (scan_power hint existed; model commanded more anyway) — prose rule
broken again, code rule added. (4th confirmation of the lab law.)

**Follow-up (Mason spotted "labeled the blue block red"): CAPTURE-POSE BUG —
model fully exonerated.** Replayed every landmark report from 205719 against both
poses: at CAPTURE-time pose, 4/4 reports land on the correct blocks (blue✓ yellow✓
red✓ green✓); at reply-time pose (after ~1-2s of latency rotation), they land on
WRONG blocks (yellow→blue, red→purple). Ingestion was using live heading at reply
time — labels pinned where the nose points NOW, not where the camera looked when
the frame was taken. Vision was never wrong; the timestamp was.
**Fixed:** pose frozen at frame capture ({x,y,th,pan}); landmark math + occupancy-
ray snap use the capture pose. Dropped the live-sonar distance fallback (same
staleness class). Fused landmark map now logged every think (map_landmarks) so
label placement is directly auditable — closes the "can you tell from telemetry"
gap. Combined with the scan clamp, label placement error should now be bounded by
a few degrees instead of a few hundred.

## 2026-08-28 — Session 174310: the drunken-walk bug + thinker narration
**Log review:** step 0 (scan) now works PERFECTLY — slow rotation labeled all five
blocks correctly, code check auto-advanced. Then step 1 ("drive toward green")
produced a drunken walk: 8 advance missions, poses orbiting the origin, ended 9mm
from start, never closed on green 585mm away.
**Root cause:** "toward X" subgoals never encoded DIRECTION. The blind driver had
known_landmarks (with live bearings) in its telemetry but no instruction to use
them — "forward" went wherever the nose pointed; thinker corrected each cycle;
net random walk. The map and the wheels were never connected.
**Fixed:**
1. *Bearing-servoing driver* — if the subgoal names a landmark, steer to keep its
   bearing near 0 (proportional bias, pivot if |bearing|>90, distance falling =
   closing). The blind driver is now a course-holding controller.
2. *Face-before-chase (thinker)* — |bearing|>25 → pivot first (sized to bearing),
   then advance; name the target in the subgoal so the driver can servo on it.
**Verified:** green at +35° → thinker pivots right 35 first; driver curves right
[0.6,0.5] on a named target.
**Also added (Mason's ask): thinker narration** — every think reply now includes
observe (what I see) and assess (what it means for the step); shown as a running
👁/🤔/➜ story feed in the UI, logged in sessions. ~30 extra output tokens/think.
Reviews can now diagnose reasoning failures from the narration itself.

## 2026-08-28 — GPT-5 family benchmark ("should we try a bigger model?")
**Perception (8 shots):** 4.1-mini 8/8 colors 7/8 digits (0.9s, $0.00011) ·
gpt-5-mini **8/8 + 8/8** (1.2s, $0.00010) · gpt-5 8/8 + 7/8 (4× cost, no better) ·
gpt-5-nano 7/8 + 5/8. All gpt-5 runs at reasoning_effort=minimal (control-loop
latency; higher effort untested).
**Dual-duty (label everything + valid subgoal, one reply):** 4.1-mini, 5-mini, and
5 ALL PERFECT (6/6 labels, 0 wrong, 4/4 subgoals). 4.1-mini fastest (1.9s vs 2.8s).
**Conclusions:** (1) model scale is NOT the bottleneck — big gpt-5 = mini scores at
4× price; (2) the historical "can't label AND drive" failures were PROMPT STRUCTURE,
not capability — every modern model aces dual-duty when the prompt demands all
outputs explicitly (validates the harness-fix history); (3) gpt-5-mini has a real
edge only on rotated digits.
**Actions:** _mk_body() handles gpt-5 API differences (max_completion_tokens,
reasoning_effort=minimal) across all three endpoints; gpt-5-mini added to thinker
dropdown; 4.1-mini stays default (fastest at equal dual-duty). Benchmark ~$0.03.

## 2026-08-28 — Session 172914: the hallucinated-navigation bug + label grounding
**What the log showed (blue-block hunt):** rover reached **381mm from the actual
target**, then drove away for the whole rest of the session — every subgoal saying
"toward the blue block" while distance grew 381→1488mm, including invented bearings
("turn left 150 to face blue block bearing…"). Cause: it NEVER LABELED blue (one
landmark all session: yellow, correctly placed — bearing-sign fix confirmed working).
With no blue in its map and none in frame, the thinker navigated toward a
fabricated position. Mason's observed color-mislabels are the same weakness
(sloppy label acquisition/grounding) surfacing differently.
**Fixed:**
1. *Occupancy-ray snap* — sightings now snap to the first known cluster along the
   reported bearing (the dot outlines are accurate, so labels stick to REAL geometry
   at any bearing; old sonar-snap only worked within ±18° of a ray).
2. *Color-conflict merge guard* — a position-merge may only change a landmark's
   color word if the new observation was CLOSER than the one that named it (near
   looks beat far guesses); conflicts logged as label_conflict events.
3. *Navigation grounding rule* — "toward X" is only allowed if X is in
   known_landmarks or visibly in frame; otherwise the task is FINDING it (slow
   perception scan). Never fabricate target directions.
4. *Label-nearby-priority* — unlabeled radar obstacle under 800mm in view →
   identifying it is a priority (fixes standing-next-to-anonymous-target).
**Observed (verification):** target absent from map + frame → "rotate left slowly
until blue block spotted" (perception-gated), zero hallucinated steering.

## 2026-08-28 — Continuous control, perception-gated motion, semantic map (Mason)
**Added, per Mason's "inputs are too rigid" redesign:**
1. *Velocity slew* — driver commands are now TARGETS; motors ramp toward them at a
   rate tied to the MEASURED drive-loop period (full swing ≈ 0.8× period), so no
   command fully lands before the next correction arrives. Driver prompt reframed:
   "think in adjustments, not jumps — nudge up in open space, ease down as distances
   shrink." Safety stops remain instant (reflexes bypass the slew).
2. *Perception-gated missions* — done_when {"field":"perception","desc":...} never
   auto-completes; the free-running thinker ends it by issuing the next mission when
   its own look shows the target ("rotate until I spot the yellow block"). Scan
   power computed from think-period vs 70° FOV (~0.04-0.15) so rotation can't skip
   past the target between looks.
3. *Semantic occupancy map* — vision labels are stamped onto sonar geometry
   (occLabel: cells within 250mm of a landmark get its name). map_radar became
   semantic: each sector now {"mm": dist, "what": label|null} — e.g. "rear_right:
   1400mm (red block)". Prompt: LABEL EVERYTHING; labels enrich the radar forever.
**Observed (verification):** scan step → "Rotate slowly left to scan and find the
yellow block" with perception done_when. (Arena still uses flat radar — schema drift
to reconcile when it gets the planner retrofit.)
_(pending: full directed hunt on the new control — watch for smooth decel toward
blocks, slow scan rotations, semantic radar entries appearing in the sensors panel)_

## 2026-08-28 — Session 171352 review: bearing sign flip + the step-0 trap
**Mason reported:** rover stared right at the number face and ignored it; mind map
badly off. Both diagnosed from the log with hard evidence:
1. **Bearing sign flip (mind map):** purple reported at bearing -45; placed with our
   "positive=left" convention → 1352mm error; sign-flipped → 362mm. Models REPORT
   bearings image-style (positive=RIGHT) regardless of stated convention, while
   correctly CONSUMING our convention when reading known_landmarks (produce/consume
   asymmetry). Fixed by switching the whole system to image convention (positive=
   right): prompt, ingestion math, known_landmarks feedback, snap-to-sonar compare.
2. **Step-0 trap (stare-and-ignore):** entire session stuck on step 1 of the plan.
   The rover reached 340mm from the target but never emitted step_done — my "focus
   ONLY on the current step" instruction suppressed both step advancement AND
   opportunistic answering (reading the number was step 6, so it wasn't "allowed").
   Fixes: (a) OPPORTUNISM OVERRIDES THE PLAN — visible answer → answer immediately;
   (b) explicit evaluate-success-first instruction — which testing showed BOTH
   4.1-mini and 4.1 ignore (0/4 step_done on a clearly-met condition) → so
   (c) **structured step checks**: planner emits machine-checkable conditions
   (landmark_known / near_landmark / telemetry / perception) and CODE advances steps
   every 400ms; only perception steps rely on LLM judgment. Verified: directed-hunt
   plan came back with steps 1-2 code-checkable, 3-5 perception.
Session logs now record the secret (block+number) for automatic scoring.
Recurring lesson of the day, third confirmation: LLM does semantics, code does
checking — every time a rule lives only in prose, it eventually gets ignored.

## 2026-08-28 — Three-layer stack: Planner → Thinker → Driver (Mason's architecture)
**Added:** Mission planner layer above the thinker. On autopilot start the mission
goes to /api/sim/plan (gpt-4.1, ~$0.0002, one call): breaks it into 3-8 ordered
executable steps with observable success conditions. The thinker now receives the
full plan + its current step and is instructed to subgoal ONLY for that step; new
reply fields step_done (advance pointer) and need_replan (planner re-invoked, also
auto-invoked if steps exhaust without a result). Plan checklist panel in sidebar
(▸ current, ✓ done). Plans logged to sessions (type "plan"). Roles now clean:
planner = strategy (once), thinker = step execution + perception (~0.3Hz),
driver = movement (~1Hz), physics = safety/truth.
**Observed (verification):** directed-hunt plan came out textbook: scan 360 → approach
→ verify color → repeat if wrong → CIRCLE TO FAR SIDE → read. The circle-behind
insight appeared unprompted. Thinker on step 1 issued a scan rotation — no strategy
freelancing. _(Arena still uses per-strategy prompts without the planner layer —
retrofit candidate after sim validation.)_

## 2026-08-28 — Directed hunt (Mason's redesign of the mission)
**Changed:** goal now NAMES the target: "Find the number painted on the RED block —
it is on the face turned away from the arena center; go around behind it." Number
still lands on a random block each round; the goal text is generated from the secret.
Sim: 🎯 button + reset both re-aim at the current secret. Arena: each chamber's goal
names its own chamber's target.
**Why:** open-ended search tested wandering; directed hunt tests goal-driven
navigation — pick objective → navigate to named block → orbit to far side → read.
Exercises landmark identification (which block is red?), heading arithmetic
(bearing → turn), and purposive movement. Strategy tournament now measures how each
method reaches a KNOWN objective rather than how it stumbles on an unknown one.

## 2026-08-28 — Vision benchmark: which model can actually see?
**Method:** 10 deterministic stills from the real sim scene (Chrome headless +
test-shots.html): blocks at known distances/angles, digit "7" on red's away face,
wall close-up, overview. 4 models × 10 shots, detail:low, scored vs ground truth.
**Results (colors / digits, out of 10):**
- gpt-4.1-mini: **10/10 colors, 10/10 digits** — perfect, even the rotated glyph. 🏆
- gpt-4.1: 10/10 / 8/10 (missed rotated digit head-on; conservative null, not wrong)
- gpt-4o:  10/10 / 8/10 (same misses)
- gpt-4o-mini: 9/10 / **0/10 — hallucinated digits (4, 2, 3)**. Explains all early
  mislabeling/number failures. Never use for the hunt.
- Resolution irrelevant: 320x240 == 640x480 on every model. Model choice >> pixels.
**Bug found via the stills:** box-face textures render digits ROTATED (±x faces) or
MIRRORED (±y faces — unfixable by rotation). Fixed by mounting digits as separate
sign planes with explicit orientation (verified upright on both axes). Ported to
sim + arena.
**Actions:** thinker default → gpt-4.1-mini (cheaper than 4.1 AND best vision);
arena chambers → gpt-4.1-mini; dropdown annotated with benchmark scores.
Benchmark cost ~$0.05. Harness kept: ui/test-shots.html + Chrome headless — rerun
anytime a new model candidate appears.

## 2026-08-28 — Number hunt, strategy arena (10 chambers), lab usage meter
**Mind-map mislabeling diagnosed:** (1) scene too dim — muddy colors in 320x240 jpeg
(red/orange/purple → brown); (2) dedupe bug: position-match kept the OLD label
forever, so an early wrong guess could never be corrected. Fixed: ambient 0.5→0.75,
purer block hues (named red/blue/green/yellow/purple), latest-look-wins labels.
**Hidden-number hunt:** one random block per session gets a number (1-9) painted on
the face turned AWAY from arena center — must circle blocks to see it. Thinker may
reply "answer":{number,color} ONLY when readable (prompt: never guess). Code scores
vs ground truth; correct = session win + stop; wrong = logged, search continues.
🎯 button sets the hunt goal; reset re-randomizes.
**Strategy Arena (/arena.html):** 10 parallel chambers, one search strategy each
(perimeter-first, spiral-out, block-orbit, frontier, grid-sweep, random-bounce,
scan-then-move, camera-pan-heavy, label-then-visit, greedy-open). Each chamber: own
physics/occupancy/secret, shared single WebGL renderer for POV shots, global LLM
concurrency limiter (3), staggered loops (think ≥6s, drive ~2s per chamber). Guards
ON in chambers (isolate search skill from crash noise). Scoreboard: time-to-find,
tokens, cost, collisions, wrong answers per strategy. ~$3/hr while running.
**Usage meter:** server-side lifetime token/cost accounting (usage.json, every LLM
call), /api/usage, displayed in sim sidebar + arena header. Camera unlock toggle
("camera follows rover", default off) added to sim.
_(pending: first arena run — which strategy finds the number fastest/cheapest?)_

## 2026-08-28 — Informed-only mode: guards → toggle, budgets → the law (Mason's call)
**Philosophy fork:** instead of hardcoded collision prevention, feed the LLM the
numbers it needs to not crash — "you have 700mm of budget, don't say 1000."
**Added:**
1. *Mission budgets in telemetry* — advance_budget_mm (live forward cone minus hull
   width = how far it can ACTUALLY advance before contact) and reverse_budget_mm
   (memory-only). Prompt: "budgets are the law — advanced_mm target ≤ budget − 150;
   budget < 300 → don't advance, turn."
2. *Safety guards became a toggle* (default OFF = informed-only, per Mason). OFF
   disables: speed governor, 140mm ray-halt, standoff shell, bump recoil. Collision
   detection/blocking/events all REMAIN (measurement + truth, not protection). Motor
   watchdog remains (liveness, not collision guard). Both prompts told the mode:
   informed-only = "NO code overrides; every collision is your planning failure."
3. Sessions log guards on/off → clean A/B: guards-vs-information, scored in
   collisions. Same explore goal both modes.
**Observed (verification):** informed-only, budget 700mm → "advance forward 500mm"
— self-sized under budget, first try.
_(experiment pending: informed-only session vs guarded session, collision counts.
Honest hypothesis on record: ray-blind corner clips may still occur in informed-only
mode because budgets come from the same 3 rays; if so, the fix is better DATA
(denser perception), which is the same philosophy.)_

## 2026-08-28 — Standoff override: geometric no-hit guarantee (Mason's call)
**Trigger:** thinker said "go forward 700" and the rover drove straight into a box.
Root cause of "how can the bottom layer not realize": its stop rules live in an LLM
prompt (suggestions, not guarantees), and its senses are 3 skinny rays (0/±30°) vs a
~220mm-wide hull — off-angle box corners are invisible to all three rays.
**Added:** STANDOFF shell (120mm beyond hull radius), enforced in physics: powered
motion can never carry the hull inside the shell. On contact-with-shell: force stop,
mission → blocked, "standoff_stop" event to the thinker (free-running, reacts within
~2-5s). Recoil is exempt (moving away); rotation unaffected; if somehow already
inside the shell, escape is allowed. Both prompts told the override exists and that
a standoff stop means "path genuinely too tight — pick another direction."
**Design principle now complete:** every safety property is code (standoff shell,
ray-halt, governor, reverse memory-guard, recoil, watchdog); the LLMs only ever
decide WHERE to go, never whether physics lets them. Collisions should now be
structurally impossible under power — remaining contacts only via recoil paths.
_(session pending — the target is finally 0. If any collision appears, log the
geometry; it's a hole in the shell model.)_

## 2026-08-28 — Motor watchdog: default is inactive
**Added (Mason's requirement — nothing moves unless the thinker dictates it):**
Confirmed the architecture already had thinker-dictates semantics (driver only acts
under an active running mission; no mission at autopilot start = parked). Closed the
one gap: motors held the LAST driver vector between commands, so a stalled/erroring
driver call would have kept the rover moving on stale orders. Now a physics-layer
watchdog zeroes motors if there is no mission, the mission ended, or no fresh driver
command within 2.5s. Same pattern the real Pi build needs (command timeout in the
motor loop so a hung process can't leave wheels spinning).

## 2026-08-28 — Purposive turns + heading understanding (session 160823 review)
**Log findings (60s, 20 collisions):** 7/11 missions were blind fixed-angle turns
thrashing left-right-left (L90→L120→R120→R90→R90→L90) — open-loop turning: guess an
angle, discover the new facing is also bad, guess again. Mason's diagnosis: turns
should close the loop with perception ("turn until there's room"), not pick angles.
**Added:**
1. *forward_clearance_mm* — worst of the 3 forward rays = "room ahead" as a number.
   New done_when field. Purposive turns: "rotate right until there is room ahead"
   (done_when forward_clearance_mm gt N; thinker picks N per situation — nothing
   hardcoded, code just measures). Prompt: purposive preferred for searching/escape;
   fixed-angle only when the angle is known; two failed fixed turns → switch to
   purposive. Verified: cornered + thrash history → "rotate right until there is
   room ahead", clearance gt 900.
2. *Orientation semantics* (Mason: "does it know it's facing 60 and needs to rotate
   30?") — heading_deg existed in telemetry but its frame was never explained. Prompt
   now teaches: heading increases turning left; radar/landmark bearings are nose-
   relative; a landmark's bearing_deg IS the degrees to turn to face it. Plus mission
   progress line ("turned 60 deg, advanced 0 mm since issued") so the thinker sees
   mid-mission state instead of only endpoints.
**Observed (verification):** landmark at bearing -130 → "rotate right 130 degrees to
face the red cube" (turned_deg gt 128) — exact heading arithmetic on the first try.
_(session pending — watch: purposive vs fixed turn ratio, thrash gone, collisions
vs the 20 baseline)_

## 2026-08-28 — The 37-collision session: three compounding sim bugs (session 160211)
**What the log showed:** 37 collisions in 70s — but the thinker was behaving WELL
(situation headlines accurate, sensible responses, 11/12 subgoal variety, 4 cubes
labeled). All three root causes were sim/design bugs, not model failures:
1. *Recoil bounce loop* — recoil backed off, driver re-advanced, hit again: one
   encounter counted as 5-8 collisions (events every 1-2s in the log).
2. *Uncontrollable turns* — full pivot spun at 320 deg/s; the 1s min-age on completion
   plus turned_deg wrapping at 180 meant turns overshot wildly (rotation per 15s
   window hit 1221/1728/2085 deg). The spinning was physics+evaluator, not planning.
3. *Mission grammar forced wall-approaches* — drive subgoals could only end on
   "front lt X", i.e. "drive until close to an obstacle."
**Fixed:**
- Turn rate clamped to ~92 deg/s (realistic for a TT rover).
- turned_deg now accumulates unwrapped (sgTurnAccum); progress fields (turned_deg,
  advanced_mm) complete IMMEDIATELY (they start at 0, can't be pre-true) — min-age
  guard only applies to sensor-distance conditions.
- Collision now BLOCKS the mission (recoil + hold + forced replan) — no re-ram.
- New done_when field advanced_mm (distance traveled since subgoal start); prompt:
  drives prefer advanced_mm 200-1500; front-lt only for deliberate landmark approach,
  never below 500.
**Observed (verification):** thinker immediately used the new grammar — "Drive
forward 1000 mm to scan open area ahead right" / advanced_mm gt 1000.
_(session pending — this is the big integration test: collisions should drop to ~0-2,
turns should land near their targets, no bounce clusters in events)_

## 2026-08-28 — Situation awareness + bump-recoil reflex
**Bug found answering "does the thinker get telemetry?":** yes (full sensors JSON),
BUT collision events were drained into the DRIVER's payload — the thinker literally
never heard about hits that happened between its plans. Also `stuck_s` buried in JSON
has no salience.
**Added:**
1. *Thinker event stream* — separate buffer (collisions, driver-blocked, instant-done)
   drained into every think call with ages: "(6s ago) collision: hit while moving
   forward, auto-recoiled".
2. *Code-assessed situation headline* (chose deterministic code over Mason's suggested
   mini-model narrator: free, instant, can't hallucinate) — top of thinker prompt:
   IN CONTACT / STUCK Ns / obstacle CLOSING (front-distance trend from history) /
   SPINNING / N collisions in 20s / "nominal". Prompt rule: unsafe situation → first
   priority is a clearance subgoal; big goal waits.
3. *Bump-recoil reflex* (never-hit-anything work, physics layer) — on contact the sim
   auto-backs-off opposite the motion direction for 400ms; reported to the thinker as
   an event. Also tightened advance halt: ANY of the 3 forward rays < 140mm (was
   front-only < 120mm) — catches angled approaches the front ray misses.
**Observed (verification):** stuck-in-contact scenario with right sector open →
"turn 120 degrees right to face open sector", turned_deg gt 110. Read the headline,
used the radar, correct direction, correct priority.
_(session pending — watch: collisions ≤1? recoil visible on contact? does the
situation line stay "nominal" most of the run?)_

## 2026-08-28 — Spin diagnosis, smart thinker, temporal self-awareness
**Diagnosed (session 134748):** rover repeatedly pivoted 120° — six consecutive
"pivot left about 120 degrees" missions. TWO root causes: (1) the model was PARROTING
the literal example subgoal from the prompt; (2) 4o-mini can't infer "I'm spinning"
from history alone. Mechanics were all working (turns completed, done_when fired,
verbatim-reissue continued missions).
**Added:**
1. *Anti-parrot* — removed copyable example subgoals from the prompt; "phrase subgoals
   in your own words"; explicit no-repeat-turn rule.
2. *Spin signal* — code-measured recent_motion (total rotation + net displacement over
   15s) fed to the thinker: rotation high + displacement low = "YOU ARE SPINNING."
3. *Smart thinker option* (Mason's call) — model dropdown. gpt-4o REFUSED agentic
   control prompts ~2/3 of the time ("I'm sorry, I can't assist"); fixed by moving
   instructions to the system role (0/3 refusals) AND switching smart option to
   gpt-4.1 (0 refusals, better judgment). All calls now use system/user split.
4. *Temporal self-awareness* (Mason's idea) — thinker now knows its own tempo: called
   every ~Ns, reply lands ~Ls later, driver acts every ~Ds; subgoal history is
   timestamped ("18s ago … -> done"); prompt says plan for where the rover WILL BE
   and size subgoals to survive ≥2 planning cycles.
**Observed (verification, 3 runs, spin scenario):** gpt-4.1 broke the spin 3/3 —
"drive forward 600-700mm" with sane thresholds. Measured $0.00022/plan, 0.9-1.5s
latency — near-mini price/speed with much better judgment. Smart floor kept at 4s.
_(session pending — watch: spin gone in practice? subgoal variety? does it pre-plan
for latency, e.g. shorter turns when moving fast?)_

## 2026-08-28 — Occupancy memory, sensor-grade mind map, code-judged done_when
**Added (design rule: LLM does semantics, code does geometry — now applied everywhere):**
1. *Occupancy map* — every sonar return painted into a 60mm world grid (~5Hz, pure
   code). Collisions also paint the contact point (touch teaches the map, including
   reverse hits). Mind map now renders it: grey = scanned geometry, brighter = repeat
   hits, red × = collisions. Map self-builds as it drives.
2. *Virtual rear sense from memory* (per Mason: NO rear sensor) — `rear_memory_mm` =
   nearest remembered obstacle in the rear 120° arc. Reverse governor now keyed to it
   (slow <400mm, stop <130mm). HONEST LIMIT: only protects where already scanned;
   unscanned space behind = no protection. Prompts teach "pivot and drive forward
   eyes-first; sweeping turns grow your map."
3. *Landmark snap-to-sonar* — mind map was "kinda bad" because positions were LLM
   distance guesses. Now: label from thinker, distance snapped to the sonar ray when
   report bearing aligns within 18° of a ray. Geometry from sensors, names from LLM.
4. *Structured done_when* — thinker emits {field, op, value}; sim code evaluates every
   150ms (incl. turned_deg since subgoal start, elapsed_s). Fixes the dead handoff
   (0/49 done reports); server falls back to elapsed_s>8 if the thinker emits junk.
**Observed (verification):** think returned {'field':'ultrasonic_front_mm','op':'gt',
'value':220} — machine-checkable. Driver with rear_memory 300mm chose a left arc, no
reverse.
**Observed (Mason's session):** REPLAN STORM — thinker ticked at driver Hz and the
rover spun in place. Root cause: thinker set done_when thresholds at/near current
readings (e.g. front>220 while front=220) → instant-complete → immediate replan →
new pivot subgoal → spin. Mind map itself "great, getting better." Also surfaced:
models were nearly blind to the occupancy map (only rear_memory_mm was fed).

## 2026-08-28 — Anti-storm guards + memory radar
**Added:**
1. *Replan-storm guards* — (a) thinker hard-limited to one call per 2.5s; (b) condition
   met within 500ms of issue = "instant-done" with corrective feedback fed back via
   driver_status + subgoal history ("your done_when was ALREADY TRUE — pick a farther
   threshold"); (c) normal completion requires subgoal age ≥1s.
2. *Prompt rules* — subgoals must be SINGLE-PHASE (turn OR drive, never "turn then
   drive"); done_when must be false at issue; turns must use turned_deg.
3. *Memory radar* — occupancy map now FED to both models: map_radar = nearest
   remembered obstacle per 45° sector (8 sectors, 3000 = unscanned ≠ open). Thinker
   told to use it for direction picking; driver for reverse caution.
**Observed (verification):** corner scenario → "pivot left about 120 degrees" with
turned_deg gt 110 — single-phase, non-trivial condition. (Radar direction choice was
suboptimal — picked left toward 1200mm over right toward 2600mm; watch in session.)
_(superseded same day — see free-running planner below)_

## 2026-08-28 — Free-running planner (Mason's redesign)
**Changed:** Dropped the wake/event model entirely. The thinker now FIRES CONTINUOUSLY,
paced only by its own latency (~0.4-0.5Hz; 1.5s floor to stop error-hammering), and
each reply REPLACES the driver's current mission. done_when still code-evaluated;
done/blocked now just stops the motors and holds until the next mission lands (≤~2s) —
no wake signaling. Instant-done feedback retained as a teaching signal in history.
Key subtlety handled: a fresh subgoal each cycle would reset turned_deg mid-turn, so
VERBATIM reissue (identical subgoal + done_when) continues the mission without
resetting progress — prompt instructs "reissue verbatim if still correct." Verified:
thinker mid-mission reissued 'drive forward into open space' word-for-word.
**Why:** simpler control flow, thinker always has fresh eyes (~2s-old view max), no
storm possible by construction (pace = its own latency), and it can interrupt a bad
mission mid-flight instead of waiting for completion.
**Observed:** _(session pending — watch: mission churn vs verbatim-reissue rate,
turns completing despite replacement, think ~0.4Hz vs drive ~0.9Hz on the bars)_

## 2026-08-28 — Split-brain architecture (thinker + driver)
**Added:** Hierarchical control replacing the single-model autopilot:
- *Thinker* (slow loop): vision + memory + landmarks + subgoal history. Sets short
  imperative subgoals with a telemetry-readable "done_when". Re-plans when the driver
  reports done/blocked, or every 12s. Explicit dead-end doctrine in prompt ("facing a
  wall = turn 120-180 deg and drive away").
- *Driver* (fast loop): TEXT-ONLY telemetry, no camera — executes the current subgoal,
  reports done/blocked (blocked wakes the thinker immediately). Hard limits in prompt:
  stop+blocked under 300mm, never forward under 250mm. Explicit wheel convention added
  after test showed inverted turns ("pivoting left" while commanding a right spin).
- UI: current-subgoal display, think/drive frequency bars, purple thinker rows vs
  driver rows in log. Session summary now splits think_cmds/drive_cmds.
**Motivation:** session 124527 wall-loop: 6 fwd/rev flips in 19 cmds; at front=120mm
the single model said "path ahead is clear." Reactive single-loop can't hold the
concept "dead end — leave." Also user-requested: driver restricted to telemetry,
thinker owns memory/labels.
**Observed (verification calls):**
- Thinker at 220mm wall + blocked history → "turn right ~150 deg then drive forward,"
  done_when "front > 500mm" — the exact concept the old system never formed.
- Driver: 892ms text-only calls, 318 in / 33 out tokens = **$0.000067/cmd (~7% of a
  vision call)**. Expect ~1.1-1.5Hz driver vs ~0.1-0.3Hz thinker.
**Observed (first split-brain session, 125433: 56.4s, 4 thinks / 49 drives):**
- **Wall oscillation ELIMINATED: 0 fwd/rev flips in 49 cmds** (old: 6 in 19). The
  headline failure mode is gone.
- **Hard limits: 0 violations** — driver never commanded forward under 250mm front.
- **3.5× cheaper per minute** than single-model ($0.0066/min vs $0.023/min) — cheap
  text driver carries the call volume. Freq: driver 0.87Hz, thinker 0.07Hz.
- Labeled all 4 colored boxes correctly. Coverage: NW quadrant of arena.
- **Defect 1 — done_when handoff dead: 0 done / 0 blocked in 49 calls.** 4 clear cases
  where front exceeded the done_when threshold but driver said running; all replans
  were timer-driven (12s). Fix direction: thinker emits a STRUCTURED condition
  (field/op/value) and sim code evaluates it deterministically every frame.
- **Defect 2 — driver turn vectors unreliable under load:** said "turning right" while
  commanding [-1,1] (left pivot) and even [-1,-1] (reverse) — despite the convention
  fix passing in isolation. Repeated wrong vectors while replanning never fired
  (defect 1) = flailing in the NW corner.
- **Defect 3 — all 4 collisions were blind-reverse/pivot in a corner** with front
  reading open (1280-2620mm): no rear sensor + reverse exempt from governor = the new
  collision mode. Old mode (frontal charge) is gone; remaining mode is rearward.


Running log of every feature added and what we observed after using it.
Convention: each entry gets **Added** (what/when) and **Observed** (measured numbers,
driving behavior, anything noticed in use). Observations get filled in after Mason
drives with the feature — tell Claude what you saw and it gets logged here.

---

## 2026-08-28 — Reflex speed governor
**Added:** Physics-enforced forward speed cap in the reflex loop: under 400mm front
clearance, forward speed scales down linearly (400mm→100%, 200mm→~38%, floor 25%);
hard stop under 120mm unchanged; **reverse never capped** (escape must stay possible).
LLM told about it via `speed_governor_active` telemetry + prompt line.
**Motivation:** baseline run showed prompt guidance alone was ignored (never slowed
below 0.50 power near obstacles; 3 collisions in 34s). Safety moved from the think
loop to the reflex loop where it can't be ignored.
**Observed (rerun, 2 sessions, same explore goal):**
- Run A (23.2s, 17 cmds): **0 collisions**, governor engaged 3×. Run B (11.1s, 8 cmds):
  2 collisions. Combined 2 col/34.3s vs baseline 3/34.4s — modest, BUT collisions are
  now gentle taps recovered in 1 call (max stuck 0.6s vs baseline scrapes).
- **Key finding from run B's trace:** rover drove at the east wall with front distance
  counting down 1200→840→540→260→140mm while the LLM commanded 0.5 forward the whole
  way. Cause: flat grey wall in the POV is indistinguishable from empty space — the
  image contradicted the ultrasonic and it trusted the image. → environment needs
  depth/texture cues (next entry). LLM still never chose speed <0.5 on its own.

## 2026-08-28 — Depth-friendly world, landmark memory, mind map
**Added:**
1. *Visual depth cues* — 200mm checkerboard floor (a measuring stick in every frame;
   prompt says count tiles), striped walls with orange top band (prompt: stripes filling
   frame = close to wall), real shadows in both main + POV renders. Walls raised to 220mm.
2. *Landmark memory* — division of labor: **LLM does semantics, code does geometry.**
   Model may label up to 3 NEW objects per reply (label + bearing + distance estimate);
   sim converts to world coords via pose+pan, dedupes (<250mm or same label), caps 24.
   Telemetry feeds back known_landmarks with live distance/bearing each call.
3. *Mind map display* — 200px top-down panel showing ONLY what the robot knows: driven
   trail + its own labeled landmarks + pose. Ground-truth obstacles deliberately not
   drawn — gaps in the map are things it hasn't learned yet.
**Observed (first new-world session, 124208: 27 cmds / 44.1s, explore goal):**
- **1 collision in 44s (~1.4/min) vs baseline 5.2/min — best run yet.** Governor
  engaged 6×; textured walls appear to help it react before contact.
- **First voluntary slow-down ever recorded:** min |power| 0.30 (was never <0.50 in
  any prior session). Still mostly 0.50; 1-of-7 near-obstacle calls chose slow.
- **Landmark labeling works:** 18 reports incl. purple_box, blue_box, green box
  (mislabeled "green_cylinder" — shape hallucination, color right). Two defects found
  and fixed same-day: re-reporting of known objects, and degenerate "0mm" reports that
  mapped junk landmarks onto the rover's own position (both now filtered server-side).
- Latency crept to med 1379ms (~0.61 cmd/s) from the bigger prompt+reply — the
  landmark protocol costs ~0.2 cmd/s of frequency.
- Gap found during review: session logs lacked true pose → landmark accuracy couldn't
  be scored vs ground truth. Pose now logged (study-only, never sent to the LLM).

## 2026-08-28 — Collision detection, speed freedom, session logs
**Added:**
1. *Collision/stuck detection* — sim counts real contact events (rising-edge, so one hit
   = one count), tracks "stuck seconds" (jammed while commanding movement). HUD collision
   counter turns red during contact.
2. *LLM collision awareness* — telemetry now carries `colliding`, `stuck_s`,
   `collisions_this_session`; collision events since the last call ride along too.
   Prompt: "every collision is a failure," reverse/pivot when in contact.
3. *Speed freedom* — removed "prefer 0.4-0.7"; prompt now says creep 0.1-0.3 near
   obstacles, 0.5-0.8 in open space. Speed fully the model's choice.
4. *Session logs* — every autopilot run writes `projects/<p>/sessions/<ts>.jsonl`:
   session_start (goal), one record per LLM call (full sensors, events, command, memory,
   tokens, cost, latency), session_end (summary: duration, commands, collisions, tokens,
   cost). `GET /api/sessions` lists them. Claude can read these files to study sessions.
**Observed:**
- Verified: fed `colliding:true` + 90mm front reading → model output `[-0.5,-0.5]`
  "reversing to get unstuck." Collision awareness works on the first try.
- Collisions/session is now the headline quality metric for comparing prompt/memory
  variants.
- **First logged session (34.4s, "explore" goal): 26 commands, 3 collisions, $0.0145.**
  0.83 cmd/s median · latency 922–1763ms (median 1098). Collision *recovery* works
  (reversed both in-contact calls) but *avoidance* doesn't yet: 3 hits in 34s.
- **Speed freedom ignored:** median |power| 0.50, never below 0.50 — 5 near-obstacle
  calls, 0 slow choices. Prompt guidance alone didn't change behavior → next lever is
  stronger prompt language or a reflex-loop speed cap near obstacles.
- Memory stayed coherent across the session (plans referenced past collisions/paths).

## 2026-08-28 — LLM session memory (scratchpad + command history)
**Added:** Two memory systems for the autopilot:
1. *Command history* — last 6 commands + reasons fed back into every prompt.
2. *Scratchpad* — model writes a `memory` field (≤60 words) each reply; round-tripped
   into its next prompt. Visible live in the sidebar ("LLM memory") and per-call in the
   expanded log. Reset button clears both.
Prompt instructs: use memory to avoid repeating failed maneuvers and explore new areas.
`max_tokens` 80 → 200 to make room for the memory field.
**Motivation:** driver was fully amnesiac per call — oscillated at obstacles, re-explored
the same corners.
**Observed:** _(pending — drive it and report)_
- Expected cost impact: ~+300–500 input tokens/call (text is cheap next to the image).

## 2026-08-28 — Sensor telemetry suite + full LLM transparency
**Added:** Simulated sensor suite sent as JSON with every LLM call: 3× ultrasonic
(front/left-30°/right-30°), heading, speed, motor powers, pan-servo angle, battery
voltage (fake drain). LLM can now command the pan servo (`cam_pan`, slews realistically).
Expandable log rows: exact frame sent, telemetry JSON, full prompt text, raw reply,
tokens, cost, latency. Session token/cost totals. Live sensors panel in sidebar.
**Observed:**
- Verified model *uses* telemetry: fake 300mm right-sensor reading → it steered in
  response and cited "obstacle on the right."
- **BUT** reasoning/action mismatch seen: said "turning right to avoid obstacle on
  right" while the vector did turn right (toward it). Prompt tuning candidate.
- Cost: ~3.1k tokens in / 42 out ≈ **$0.0005/command** (~$1.80/hr at 1 cmd/s).
  Image dominates input tokens.

## 2026-08-28 — Fast LLM path + frequency measurement
**Added:** Persistent keep-alive HTTPS connection to OpenAI (saves TLS handshake/call);
latency-bound think loop (fires on reply, not fixed timer); HUD shows last round-trip ms
+ rolling cmd/s; per-row latency in log.
**Observed:**
- Cold call **1216ms** → warm keep-alive **993ms** (tiny test image).
- Real frames: expect ~1–2s RTT ≈ 0.5–1 cmd/s. Reflex loop (120mm hard-stop) unaffected,
  runs every frame.

## 2026-08-28 — STEP export
**Added:** STP button per model → FreeCAD headless converts model STL → STEP into
project `exports/`. Mesh-based (faceted) STEP, not smooth parametric.
**Observed:**
- Two silent-failure bugs found and fixed: freecadcmd swallows CLI args (fixed via env
  vars); `Part.export()` writes an *empty valid-looking file* for bare shapes — must use
  `shape.exportStep()`. Chassis: 1.4MB STL → **8.5MB STEP**, volume checks out.
- FreeCAD's OpenSCAD importer can't handle `offset()` — importCSG path abandoned for
  mesh conversion.

## 2026-08-28 — Projects + Sim Harness v1
**Added:** Per-project folders (designs/models/snapshots/exports/parts.json), UI
switcher, parts panel. Sim: 2.4m arena, differential-drive kinematics, WASD manual
drive, simulated ultrasonic reflex stop, rover-POV camera, LLM autopilot loop
(frame + goal → motor vectors), command log.
**Observed:**
- Full pipeline verified: POV frame → gpt-4o-mini → `{left, right}` applied.
- Two-loop architecture works: 1Hz-ish brain + per-frame reflex = doesn't crash even
  when the LLM is slow or wrong.

## 2026-08-28 — Robotics Lab v1 (design loop)
**Added:** Local Three.js viewer (port 8321): STL auto-discovery, live-reload on file
change (2s poll), bounding-box dims, "Send view to Claude" (camera-view PNG + note →
snapshots/ for Claude to read). OpenSCAD → STL pipeline.
**Observed:**
- Design → regenerate → hot-reload loop works; snapshot round-trip verified.

## Backlog / ideas
- Prompt tuning for reasoning/action mismatch (see 2026-08-28 telemetry entry)
- Local VLM backend via Ollama on the Mac (model param already supported server-side)
- Breadcrumb odometry memory (deferred — cheaty in sim, drifts on real hardware)
- launchd service so the lab survives reboots
- Real rover: same two-loop code on the Pi (parts list in rover-v1 project)
