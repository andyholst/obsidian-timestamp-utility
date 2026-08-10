#!/usr/bin/env python3
"""Fix the docker_run definition in Makefile to skip setsid (broken on macOS)."""

with open("Makefile", "r") as f:
    content = f.read()

lines = content.split('\n')

# Build the new line piece by piece to avoid escaping issues
parts = []
parts.append('\t@if [ -t 1 ]; then $(if $(COMPOSE_OVERRIDE),$(COMPOSE_OVERRIDE) )$(1); else _drf=$$(mktemp); _dout=$$(mktemp); printf \'%s\\n\' \'$(subst \',\'\\\'\',' )
parts.append('$(if $(COMPOSE_OVERRIDE),$(COMPOSE_OVERRIDE) )$(1))')
parts.append("\' > \"$$_drf\"; python3 scripts/pty_runner.py \"$$_drf\" \"$$_dout\" \"$$_drf.rc\" < /dev/null 2>&1; _rc=$$(cat $$_drf.rc 2>/dev/null || echo 0); cat \"$$_dout\"; rm -f \"$$_drf\" \"$$_drf.rc\" \"$$_dout\"; if [ $$_rc -ne 0 ]; then exit $$_rc; fi; fi")

new_line = ''.join(parts)
lines[70] = new_line

with open("Makefile", "w") as f:
    f.write('\n'.join(lines))

print(f"Replaced line 71 with:")
print(new_line)
