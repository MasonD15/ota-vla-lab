# Notable Moments — Robotics Lab

## #2 · FIRST FULL MISSION WIN (2026-09-03, session 083316) 🏆

**Secret: number 4 on the blue block. Final think: `answer {number: 4, color: blue}` — CORRECT.**
114.6s · 26 thinks · $0.0228 · 1 grazing collision · big arena (4.8m).

The run, compressed:
- t0: labels blue immediately, step 1 auto-advances
- t1-4: face → advance 1000mm → advance 580mm → reverse for clearance (1345→219mm)
- t5-24: the orbit — plots arcs, absorbs 8 pre-flight rejections without a single
  collision from them, and crucially RIDES its paths with the new `continue` action
  (8 uses; seven consecutive continues across t11-17 while the arc physically swept
  around the block; one full path ran to completion; ZERO path abandonments)
- t25: "We have visually confirmed the number on the blue block" — its own
  self-written check ("Number on blue block clearly visible") satisfied — answers.

Every mechanism built over six days participated in the win: planner steps with
code checks · scan-and-label · bearing navigation · plotted trajectories with
look-points · pre-flight validation · continue · self-written action checks
(26/26 replies carried one) · map notes ("begin_arc_blue", "widen_arc_blue") ·
eyes-beat-theory answering. The failure catalog in LAB_NOTES.md is, in
retrospect, the exact recipe list for this success.

What was still rough: 8 path rejections during the orbit phase (arcs plotted too
tight for its own map — safety did its job, but replot churn cost ~30s).

One line for the README someday: it took six days to teach an over-the-air LLM
that language ends where geometry begins — and one clean run to prove the split
works.

---

A permanent record of runs that taught us something worth keeping, with raw log
excerpts preserved verbatim (sessions may get cleaned; this file does not).

---

## #1 · "Number 3 visible — but this is the near face" (2026-09-01, session 172348)

**The setup:** directed hunt, secret = number **3** on the **purple** block, hidden
on the face turned away from the arena center. The rover executed its best run to
date — located and labeled purple, approached with buffer, escaped two wall contacts
with correct reverse maneuvers, and plotted waypoint arcs around the block.

**The moment (think #9, verbatim from the log):**

```json
{
  "scene": "The camera shows the left edge of the purple block (number 3 visible, but this is the near face), with a wall directly ahead and to the right side, orange band on top. The immediate right and front are blocked by the wall and corner.",
  "observe": "Blocked against the wall, left side of purple block visible.",
  "assess": "Need to plot a go-around maneuver behind the purple block.",
  "say": "Plotting a leftward arc to pass around the block and reach its rear face.",
  "action": {
    "name": "follow_waypoints",
    "args": {
      "points": [
        {
          "x": 950.0,
          "y": 300.0
        },
        {
          "x": 850.0,
          "y": 650.0
        },
        {
          "x": 700.0,
          "y": 700.0
        },
        {
          "x": 600.0,
          "y": 500.0
        }
      ]
    }
  }
}
```

Pose at that instant: {"x": 1055, "y": 101, "th_deg": 84} — standing in the gap between the
purple block and the wall, i.e. almost certainly looking AT the away-face.

**What happened:** the model READ THE CORRECT ANSWER — "number 3 visible" — and then
rejected its own observation, reasoning the visible face must be the "near face" and
therefore couldn't hold the hidden number. It drove on to continue searching for a
face it was already looking at.

**Why this is remarkable rather than embarrassing:** this was not a perception
failure, a compliance failure, or a laziness failure — it was the mission brief
being followed TOO faithfully. The goal said the number is on the face turned away
from the center; the model treated that spatial claim as a constraint strong enough
to override direct visual evidence. It chose instruction-fidelity over opportunism —
the exact opposite of the duty-drop failures that dominated earlier sessions. The
model's failure mode had matured from "ignores the mission" to "believes the
mission more than its own eyes." That is a fundamentally more advanced way to be
wrong, and it says the mission text is now load-bearing in its reasoning.

**Also notable in the same session:** first correct uses of the contact-escape
reverse doctrine (twice), and the cleanest waypoint-arc navigation observed to date
(Mason: "it did a very cool job of navigating waypoints").

**Countermeasures shipped:** the EYES-BEAT-THEORY doctrine (a legible digit on the
target IS the answer, whatever face you think it is), and the scene-digit watchdog
(code flags any digit mentioned in its own scene narration during a hunt).

**The lesson for the lab:** as instruction-following improves, mission text stops
being advice and starts being physics for the model. Write mission briefs the way
you would write specifications — every clause will eventually be obeyed, including
the ones you meant only as hints.
