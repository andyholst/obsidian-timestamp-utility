#!/usr/bin/env python3
"""openspec_change_flow.py — agent-driven OpenSpec lifecycle, CONFINED TO A WORKTREE.

Contract (see openspec/changes/openspec-change-worktree-flow):
  1. Create a dedicated local worktree wt/<name> (NEVER touch the parent working tree).
  2. Scaffold the OpenSpec change INSIDE the worktree (B15 — via openspec new change).
  3. Generate + verify INSIDE the worktree (run-agentics, loop-harness via worktree-override).
  4. On green: archive (phase7-archive, spec only) INSIDE the worktree, then finalize IN the
     worktree (squash-commits -> changelog -> bump-from-changelog -> changelog-format).
     Squashing happens ONLY here, in the worktree (agent/harness behaviour).
  5. Deliver = git push origin feat/<name> (PR). NO file copy back to the parent dir.
  6. Independent/parallel: each run uses COMPOSE_PROJECT_NAME=otu-<name>.

This is the Python mirror of scripts/openspec-change-flow.sh — identical semantics + env handling.

Usage:
    python3 scripts/openspec_change_flow.py --name <change> [--push] [--no-push] [--no-agentics] [--no-loop] [--push-remote <remote>]

Env vars: REPO_ROOT should be the main repo (defaults to git rev-parse --show-toplevel).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys


def run_cmd(cmd: list[str], cwd: str | None = None, check: bool = True, timeout: int | None = None) -> subprocess.CompletedProcess:
    """Run a shell command via subprocess."""
    return subprocess.run(
        cmd, cwd=cwd, check=check, capture_output=True, text=True, timeout=timeout or 300,
    )


def run_cmd_live(cmd: list[str], cwd: str | None = None) -> int:
    """Run a shell command streaming live output to stdout/stderr."""
    return subprocess.run(
        cmd, cwd=cwd, check=False
    ).returncode


def main() -> int:
    parser = argparse.ArgumentParser(prog="openspec_change_flow", description="Agent-driven OpenSpec lifecycle, confined to a worktree.")
    parser.add_argument("--name", required=True, help="Change name")
    parser.add_argument("--push", action="store_true", default=True, help="Push feat/<name> as PR when green (DEFAULT)")
    parser.add_argument("--no-push", dest="push", action="store_false", help="Opt out of auto-delivery; keep work local in wt/<name>.")
    parser.add_argument("--no-agentics", action="store_true", help="Skip run-agentics.")
    parser.add_argument("--no-loop", action="store_true", help="Skip the full loop-harness (hermetic pre-flight only).")
    parser.add_argument("--push-remote", default="origin", help="Remote name for delivery push (default: origin).")
    args = parser.parse_args()

    name = args.name.strip()

    # --- locate repo root ---
    try:
        repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode().strip()
    except Exception:
        repo_root = os.getcwd()

    branch_name = f"wt/{name}"            # local sandbox during work (B27).
    feat_branch = f"feat/{name}"          # PR branch, created only at delivery.
    wt_path = os.path.join(repo_root, "worktrees", name)
    compose_proj = f"otu-{name}"

    # Override file ensures containers bind-mount the WORKTREE as /project instead of the parent repo.
    override_compose = "-f docker-compose-files/worktree-override.yaml -p otu-" + name if os.path.exists(
        os.path.join(repo_root, "docker-compose-files", "worktree-override.yaml")
    ) else ""

    print(f"=== OPENSPEC-FLOW: {name} ===")
    print(f"REPO_ROOT = {repo_root}")
    print(f"WORKTREE  = {wt_path}")
    print(f"BRANCH    = {branch_name} (local sandbox; promoted to {feat_branch} on delivery)")

    # --- 1. create worktree (idempotent) ---
    if os.path.isdir(wt_path):
        print("WORKTREE already exists at", wt_path, "— reusing.")
    else:
        print(f"=== 1. git worktree add {wt_path} -b {branch_name} ===")
        subprocess.run(["git", "worktree", "add", wt_path, "-b", branch_name], cwd=repo_root, check=True)

    # Symlink node_modules from the main repo if needed (host-side convenience; containers bind-mount absolutely).
    wt_node_modules = os.path.join(wt_path, "node_modules")
    repo_node_modules = os.path.join(repo_root, "node_modules")
    if not os.path.exists(wt_node_modules) and os.path.isdir(repo_node_modules):
        os.symlink("../../node_modules", wt_node_modules)

    # Symlink .env for token-authenticated push (gitignored — never committed/pushed).
    wt_envfile = os.path.join(wt_path, ".env")
    repo_envfile = os.path.join(repo_root, ".env")
    if os.path.isfile(repo_envfile) and not os.path.exists(wt_envfile):
        os.symlink("../../.env", wt_envfile)
        print("    (symlinked .env into worktree for token auth — gitignored, never committed)")

    # Switch all subsequent work INSIDE the worktree directory.
    os.chdir(wt_path)

    # --- 2. scaffold change INSIDE the worktree (B15) ---
    change_dir = os.path.join(wt_path, "openspec", "changes", name)
    if not os.path.isdir(change_dir):
        print(f"=== 2. make openspec-new NAME={name} (inside worktree) ===")
        rc = subprocess.run(["make", "openspec-new", f"NAME={name}"], cwd=wt_path).returncode
        if rc != 0:
            print(f"ERROR: makespec-new failed (rc={rc}).", file=sys.stderr)
            return rc
    else:
        print(f"Change dir openspec/changes/{name} already present in worktree — skipping scaffold.")

    # --- 3a. generate via the agentic pipeline (optional) ---
    if not args.no_agentics:
        print(f"=== 3a. make run-agentics CHANGE={name} (inside worktree) ===")
        rc = subprocess.run(["make", "run-agentics", f"CHANGE={name}"], cwd=wt_path).returncode
        if rc != 0:
            print(f"ERROR: run-agentics failed (rc={rc}).", file=sys.stderr)
            return rc
    else:
        print("=== 3a. SKIPPED run-agentics (--no-agentics) ===")

    # --- 3b. loop gate (B20) ---
    if not args.no_loop:
        print(f"=== 3b. make loop-harness (inside worktree) ===")
        rc = subprocess.run(["make", "loop-harness"], cwd=wt_path).returncode
        if rc != 0:
            print(f"ERROR: loop-harness gate FAILED (rc={rc}).", file=sys.stderr)
            return rc
    else:
        print("=== 3b. running HERMETIC pre-flight only (--no-loop) ===")
        for tgt in ("loop-collect", "loop-ts-floor", "loop-unit"):
            rc = subprocess.run(["make", tgt], cwd=wt_path).returncode
            if rc != 0:
                print(f"ERROR: make {tgt} failed (rc={rc}).", file=sys.stderr)
                return rc

    # --- 4. archive on green (spec only, no git commit/push per B4/B14) ---
    print("LOOP GATE GREEN — continuing to archive.")
    print(f"=== 4. make phase7-archive CHANGE={name} (inside worktree) ===")
    rc = subprocess.run(["make", "phase7-archive", f"CHANGE={name}"], cwd=wt_path).returncode
    if rc != 0:
        print(f"ERROR: phase7-archive failed (rc={rc}).", file=sys.stderr)
        return rc

    # --- 5. finalize INSIDE the worktree (squash confined to worktree) ---
    print("=== 5. finalize in worktree: squash -> changelog -> bump -> format ===")
    for tgt in ("squash-commits", "changelog", "bump-from-changelog", "changelog-format"):
        print(f"     make {tgt} ...")
        rc = subprocess.run(["make", tgt], cwd=wt_path).returncode
        if rc != 0:
            print(f"ERROR make {tgt} failed (rc={rc}).", file=sys.stderr)
            return rc

    # --- 6. deliver as PR push (NO file copy to parent) ---
    if args.push:
        print(f"=== 6. promote {branch_name} -> {feat_branch} and git push {args.push_remote} {feat_branch} ===")

        # Rename or create the feature branch for PR delivery.
        subprocess.run(["git", "-C", wt_path, "branch", "-m", branch_name, feat_branch], check=False)

        # Resolve an authenticated push URL from .env (GH_TOKEN or GITHUB_TOKEN).
        push_url = run_cmd(["git", "-C", wt_path, "remote", "get-url", args.push_remote]).stdout.strip()
        token = None

        for envfile in [wt_envfile, repo_envfile]:
            if os.path.isfile(envfile):
                with open(envfile, "r", encoding="utf-8") as ef:
                    for line in ef:
                        line = line.strip()
                        if "=" in line and re.match(r"^(GH_TOKEN|GITHUB_TOKEN)=", line):
                            token = line.split("=", 1)[1].strip()
                            break
            if token:
                break

        if token:
            # Construct HTTPS token-authenticated URL.
            host = re.sub(r".*[@/:]([^:/]+(:\d+)?).*", r"\1", push_url) or re.sub(r".*[/:](github\.com[^/]+).*", r"\1", push_url)
            repo_path = re.sub(r"^git@", "", push_url).replace(":", "/") if "@" in push_url else re.sub(r"https?://[^/]+/", "", push_url)
            new_url = f"https://x-access-token:{token}@{host}/{repo_path}"
            print(f"     (using token-authenticated HTTPS push)")
            subprocess.run(
                ["git", "-C", wt_path, "remote", "set-url", args.push_remote, new_url], check=True,
            )

        rc = subprocess.run(["git", "-C", wt_path, "push", args.push_remote, feat_branch]).returncode
        if rc != 0:
            print(f"ERROR: git push to {args.push_remote} {feat_branch} failed (rc={rc}).", file=sys.stderr)
            return rc

        print("DONE: PR branch", feat_branch, "pushed. Parent working tree was NOT modified.")
    else:
        print(f"=== 6. NOT delivering (--no-push). Squashed commit + CHANGELOG live ONLY on {branch_name} (wt/<name>).")
        print(f"To deliver later: python3 scripts/openspec_change_flow.py --name {name}")

    print(f"=== OPENSPEC-FLOW COMPLETE for {name} (worktree: {wt_path}) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
