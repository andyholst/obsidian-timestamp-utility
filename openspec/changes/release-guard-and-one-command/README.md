# release-guard-and-one-command

Add a single 'make release' command (bump Obsidian version -> squash typed commit -> changelog -> release-notes -> local tag) that REFUSES to bump if the current version is already released on GitHub (remote tag exists, tolerant of X/vX)
