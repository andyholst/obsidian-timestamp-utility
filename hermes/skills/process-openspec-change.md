# Process OpenSpec Change Skill

This skill guides you through working on an OpenSpec change folder.

## When to Use
Use this skill when a new or active change exists in `openspec/changes/`.

## Step-by-Step Process

1. **Read the full spec**
   - Read `proposal.md`, `tasks.md`, and everything in `specs/`.

2. **Understand the goal**
   - Summarize what needs to be achieved in your own words.

3. **Create a plan**
   - List the main steps you will take based on `tasks.md`.

4. **Implement**
   - Create a git worktree.
   - Make the necessary changes.
   - Commit your work in the worktree.

5. **Verify**
   - Go through every requirement and scenario in the spec.
   - Test if the implementation satisfies them.
   - Be strict.

6. **Document**
   - The Phase-7 work-log entry is created automatically by `make phase7-archive CHANGE=<name>`
     (it runs `scripts/record-work.py` after `openspec archive`). No separate `make record-work`
     call is needed; it remains callable standalone for re-runs.

7. **Report status**
   - Clearly state:
     - What is done
     - What is still missing
     - Whether the change is ready to be archived

8. **Ask for next action** if human input is needed.
