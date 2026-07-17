# Proposal: pr-agent-comment-resolve (B29 — agent comments fixes + commits on green gate)

## Why
B28 gave us a one-way PR interaction: the agent *fetches* comments (B28b) and *refuses to squash*
an engaged PR (B28a). But once the agent applies a fix, the human reviewer has no signal on the PR
that the comment was addressed — they must diff the branch to discover it. Reviewers also cannot
"resolve" a thread they cannot see tied to a commit. We need a **two-way** interaction: when the
agent fixes a review comment, it MUST post a PR comment describing the fix (referencing the original
comment/thread and the fixing commit sha), and it MUST commit that fix **as a normal (non-squashed)
commit when the loop gate is GREEN** and push normally — so the participant can review the incremental
diff and resolve/approve the thread. The agent never self-approves or force-pushes.

## What Changes
- **B29 (new durable behaviour)** in AGENTS.md + skill + harness doc:
  - *B29a (comment the fix):* after the agent applies a code fix for a PR comment/review thread, it
    posts a PR comment via `gh pr comment` (or replies on the thread) summarizing the fix and linking
    the fixing commit sha — e.g. `Fixed in <sha>: <one-line summary> (resolves <comment>).` This gives
    the participant a visible, resolvable signal on the PR.
  - *B29b (commit on green gate):* the agent runs `make loop-harness` (B20 pre-flight); when it is
    GREEN the agent commits the fix(es) as **NORMAL (non-squashed) Conventional commits** and pushes the
    PR branch **normally** (no `--force`, no squash). This is the B27 "deliver on completion" applied to
    an already-open PR: completion = gate green + tasks ticked + hook pass → commit + push.
  - *B29c (never self-resolve/approve):* the agent posts the fix comment and leaves the thread for the
    human participant to resolve/approve; it does NOT click "Resolve" on behalf of the reviewer or
    approve its own PR.
- **`scripts/pr_comment.sh`** — posts a PR comment via `gh pr comment` (used by B29a).
- **Makefile targets:** `pr-comment BRANCH=<b> BODY=<text>` (post a comment) and
  `pr-resolve-and-comment BRANCH=<b>` (fetch threads → agent fixes → commit on green → post fix
  comments → push normally). The `pr_resolve.sh` prints threads; `pr_comment.sh` posts.
- **B-range bump B1–B28 → B1–B29** across AGENTS.md, skill, harness doc, Makefile, `run-loop-harness.sh`.

## Capabilities
- `pr-agent-comment-resolve` (new): two-way PR interaction — agent comments its fixes on the PR and
  commits on green loop gate, so the participant can resolve review threads.

## Impact
- Must NOT regress: B28a (no squash on engaged PR), loop-harness gates, the deterministic floor,
  B4/B14 (no unrequested push-to-main; `pr-resolve-and-comment` pushes only the PR branch normally
  when the gate is green and the human asked to resolve), and B27 (worktree confinement for NEW changes).
- The `pr-comment` post is a GitHub comment only — it performs NO local commit/push by itself; the
  commit/push happens in the B29b step after the gate is green.
