# Tasks: HITL Opt-In / Loop-Excluded

- [x] 1.1 Confirm `hitl_node.py` already implements the two-flag + TTY + CI gate
      (verified: lines 19, 26, 33-49 return state unchanged when not opted-in).
- [x] 1.2 Write `specs/hitl-optin/spec.md` (ADDED Requirements above) and `proposal.md`.
- [x] 1.3 Fix `test_collaborative_hitl_e2e.py`: replaced the flaky `test_hitl_node`
      (asserted `'human_feedback' in state` — only true on an interactive TTY, never in
      the loop) with TWO tests:
        - `test_hitl_node_pass_through_when_not_opted_in` — asserts the loop-excluded
          pass-through (no flags, no TTY -> state unchanged, NO `human_feedback` key).
        - `test_hitl_node_opt_in_adds_feedback` — properly gates the interactive path
          (both flags + monkeypatched `isatty()==True`) and asserts `human_feedback`.
      Verified: 5/5 tests pass in 2.6s (no TTY/model flake).
- [x] 1.4 Run the fast loop-integration subset
      (`pytest tests/integration/ -m "integration and not e2e and not slow"`): the HITL
      test now passes deterministically (see 1.3). Previously this was the only red in the
      fast subset (80 passed / 1 failed on the flaky assertion); that failure is resolved.
- [x] 1.5 Run `openspec validate hitl-optin-loop-excluded` and
      `openspec status --change hitl-optin-loop-excluded`; tick tasks as verified, then
      `make phase7-archive CHANGE=hitl-optin-loop-excluded`.
