# openspec-change-worktree-flow

An OpenSpec change triggers an agent that creates a dedicated git worktree, runs the harness/loop, and on green archives the change + runs loop-finalize (squash, changelog, bump). Redelivery regenerates the squashed commit and force-pushes to the same PR branch.
