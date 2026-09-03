# Notable Moments — Robotics Lab

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
