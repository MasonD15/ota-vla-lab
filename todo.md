# TODO / next steps

## Immediate experiments (ready to run, no code needed)
- [ ] First HOUSE map win (arena won 09-03; house still unbeaten — stuck-scan fixes
      + occlusion map + step-stall escape are in, untested end-to-end)
- [ ] Run `house_blue` ambiguity mode: does it discover multiplicity and run a
      verify/cross-off checklist? (Watch: twin labels, notes usage, candidate order)
- [ ] Metrics to pull from next reviews: notes/session, continue-usage,
      path_abandoned count, map_seen_pct growth rate, phantom-mirror firings

## Code refinements (backlog, evidence-driven)
- [ ] Path-rejection messages could name the nearest passable gap (rejection churn
      cost ~30s in session 081852)
- [ ] arena.html retrofit: still uses pre-action-era API (flat radar, old think
      fields) — port to action library or retire
- [ ] Planner-led vs flat-strategy tournament (old idea, now feasible)
- [ ] Consider seen-map decay/staleness (world is static now, fine — matters if
      objects ever move)

## Bigger arcs
- [ ] Environment randomization at session start (positions/counts) — everything
      is ready for it post-de-hardcoding
- [ ] VLA fine-tune on session logs (frame + scene + telemetry + action records
      are already the right format) — the "habits from training" endgame
- [ ] Real rover port: motion layer ↔ Pi + L298N (action API designed to match);
      parts list in projects/rover-v1/parts.json
- [ ] Publicity: GitHub topics, pin repo, write the first-win post (material in
      NOTABLE_MOMENTS #2)
