#!/usr/bin/env python3
"""Bump the Obsidian plugin version from the changelog + git tags — IDEMPOTENT / RE-RUNNABLE.

Design for safe re-run on the SAME branch (B24):
- The target `<next>` is STABLE across re-runs: it is derived from the *released* state only --
  the highest git tag that is MERGED INTO `origin/main` (the actually-published versions). The
  committed working files (package.json / versions.json / CHANGELOG.md) may already hold the
  *unreleased* bump from a prior run of this command (because `loop-finish` commits it), so they
  MUST NOT feed the calculation -- otherwise re-running would climb (0.4.11 -> 0.4.12 -> 0.4.13)
  and pile up `v0.4.x` tags. `origin/main` is a local ref (fetched), so this works without a live
  network call.
    <next> = max(tag merged into origin/main) + 1 patch.
- The top CHANGELOG working section (`## Unreleased` or a prior run's `## <next>`) is re-labelled
  to `## <next>` idempotently. Released `## <version>` sections committed in git HEAD are never
  touched by the changelog step, so they are never matched/duplicated here.
- package.json / manifest.json version fields: surgical one-line replace (idempotent).
- versions.json: every needed semver <= <next> that is missing gets the plugin's OBSIDIAN MIN-APP
  VERSION (read from `manifest.json` `minAppVersion`, never a hardcoded constant), and the map is
  kept contiguous + semver-sorted. Idempotent (only adds missing keys).
- Local `v<next>` tag: re-pointed with `git tag -f` (idempotent; moves to current HEAD, never
  refuses on a local-only tag).
- REFUSES (exit 2) ONLY if `v<next>` is already released on the REMOTE (genuinely published). A
  network failure is treated as "not released" (do not block on SSH/auth prompts).

No push (B14). Safe to run locally and to RE-RUN.
"""
import sys
import os
import re
import json
import subprocess

SSH_ENV = None


def _env():
    global SSH_ENV
    if SSH_ENV is None:
        SSH_ENV = dict(os.environ)
        SSH_ENV['GIT_SSH_COMMAND'] = 'ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=5'
        SSH_ENV['GIT_TERMINAL_PROMPT'] = '0'
    return SSH_ENV


def semver(v):
    m = re.match(r'^v?(\d+)\.(\d+)\.(\d+)', v or '')
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def bump_patch(vt):
    a, b, c = vt
    return (a, b, c + 1)


def released_max(repo):
    """Highest version that is actually RELEASED = highest git tag merged into `origin/main`.

    `origin/main` is a local ref (fetched), so no live network needed. Tags created by a prior
    bump (ahead of origin/main) are NOT merged in, so they are excluded -- this is what keeps the
    target stable across re-runs. Returns (0,0,0) if none / ref missing.
    """
    try:
        out = subprocess.check_output(
            ['git', '-C', repo, 'tag', '--merged', 'origin/main'],
            stderr=subprocess.DEVNULL,
        ).decode().split()
        vers = [semver(t) for t in out]
        return max(vers) if vers else (0, 0, 0)
    except Exception:
        return (0, 0, 0)


def released_keys(repo):
    """Set of version keys present in the COMMITTED (git HEAD) CHANGELOG.md -- released/curated
    sections that must never be overwritten/duplicated by the changelog step."""
    try:
        raw = subprocess.check_output(
            ['git', '-C', repo, 'show', 'HEAD:CHANGELOG.md'], stderr=subprocess.DEVNULL,
        ).decode()
    except Exception:
        raw = ''
    return {re.sub(r'\s*Latest$', '', re.sub(r'^v', '', h)).strip()
            for h in re.findall(r'(?m)^## (.*)$', raw)}


def min_app_version(repo):
    """The Obsidian minimum-app version this plugin supports, from `manifest.json` `minAppVersion`
    (e.g. '0.15.0'). Falls back to '0.15.0' only if the manifest is missing/unreadable."""
    manifest = os.path.join(repo, 'manifest.json')
    try:
        return json.load(open(manifest))['minAppVersion']
    except Exception:
        return '0.15.0'


def remote_tag_exists(repo, tag):
    try:
        out = subprocess.check_output(
            ['git', '-C', repo, 'ls-remote', '--tags', 'origin', tag],
            stderr=subprocess.DEVNULL, env=_env(), timeout=15,
        ).decode().strip()
        return bool(out)
    except Exception:
        return False  # network failure -> assume not released (do not block)


def main():
    repo = os.path.abspath(os.path.dirname(__file__) + '/..')
    changelog = os.path.join(repo, 'CHANGELOG.md')
    pkg = os.path.join(repo, 'package.json')
    manifest = os.path.join(repo, 'manifest.json')
    versions = os.path.join(repo, 'versions.json')

    # STABLE target: released state only (tags merged into origin/main). This never climbs on
    # re-run because the bump's own local tag is ahead of origin/main and excluded.
    anchor = released_max(repo)
    candidate = bump_patch(anchor)
    nxt = '.'.join(str(x) for x in candidate)

    # Refuse ONLY if <next> is already RELEASED on the remote (genuinely published).
    if remote_tag_exists(repo, f'v{nxt}') or remote_tag_exists(repo, nxt):
        print(f"bump_from_changelog: v{nxt} is already released on origin -> REFUSING (exit 2)")
        sys.exit(2)

    # Re-label the top WORKING section to `## <next>`. Idempotent.
    text = open(changelog, encoding='utf-8').read()
    m = re.search(r'(?m)^(## .*)$', text)
    if not m:
        print("bump_from_changelog: no '## ' section found in CHANGELOG.md")
        sys.exit(1)
    top_key = re.sub(r'^v', '', m.group(1).replace('## ', '', 1).strip())
    top_key = re.sub(r'\s*Latest$', '', top_key).strip()
    released = released_keys(repo)
    if top_key not in released:
        new_heading = f"## {nxt}"
        text = text[:m.start()] + new_heading + text[m.end():]
        open(changelog, 'w', encoding='utf-8').write(text)
        print(f"bump_from_changelog: labelled top working section -> {new_heading}")
    else:
        print(f"bump_from_changelog: top section '## {top_key}' is released/curated -> not relabelled")

    # Bump package.json / manifest.json version fields -- surgical replace (idempotent, preserves indent).
    for f in (pkg, manifest):
        raw = open(f, encoding='utf-8').read()
        raw2 = re.sub(r'("version"\s*:\s*")[^"]+(")', rf'\g<1>{nxt}\g<2>', raw, count=1)
        open(f, 'w', encoding='utf-8').write(raw2)
    print(f"bump_from_changelog: bumped package.json + manifest.json -> {nxt}")

    # Bump the TS test file(s) mock-manifest version (e.g. src/__tests__/main.test.ts line 7
    # `version: '0.4.10'`) and src/main.ts if it carries a version constant. Idempotent surgical
    # replace of the `version: '<semver>'` literal inside TS source.
    ts_targets = [os.path.join(repo, 'src/__tests__/main.test.ts'), os.path.join(repo, 'src/main.ts')]
    ts_bumped = []
    for tf in ts_targets:
        if not os.path.exists(tf):
            continue
        raw = open(tf, encoding='utf-8').read()
        if re.search(r"version:\s*'[^']+'", raw) or re.search(r'version:\s*"[^"]+"', raw):
            raw2 = re.sub(r"(version:\s*'[^']+')", rf"version: '{nxt}'", raw)
            raw2 = re.sub(r'(version:\s*"[^"]+")', rf'version: "{nxt}"', raw2)
            open(tf, 'w', encoding='utf-8').write(raw2)
            ts_bumped.append(os.path.relpath(tf, repo))
    if ts_bumped:
        print(f"bump_from_changelog: bumped TS version literal in: {', '.join(ts_bumped)} -> {nxt}")

    # Fill gap versions in versions.json (idempotent: only adds missing keys <= next).
    # Value = the plugin's Obsidian min-app version (manifest.json minAppVersion) for ALL keys,
    # keeping the map contiguous + semver-sorted.
    vd = json.load(open(versions)) if os.path.exists(versions) else {}
    app = min_app_version(repo)
    try:
        tags = subprocess.check_output(['git', '-C', repo, 'tag'], stderr=subprocess.DEVNULL).decode().split()
    except Exception:
        tags = []
    for t in tags:
        vt = semver(t)
        key = '.'.join(str(x) for x in vt)
        if vt != (0, 0, 0) and key not in vd and vt <= candidate:
            vd[key] = app
    vd[nxt] = app
    ordered = {k: vd[k] for k in sorted(vd, key=semver)}
    json.dump(ordered, open(versions, 'w'), indent=2)
    open(versions, 'a').write('\n')
    print(f"bump_from_changelog: versions.json now contiguous up to {nxt} (minAppVersion={app})")

    # Local tag: re-point (idempotent). NEVER push (B14).
    subprocess.run(['git', '-C', repo, 'tag', '-f', f'v{nxt}'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    print(f"bump_from_changelog: (re)pointed local tag v{nxt} (no push)")


if __name__ == '__main__':
    main()
