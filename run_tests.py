#!/usr/bin/env python3
"""Run integration tests with proper environment."""
import os
import subprocess
import sys

# Read token from .env
with open('/home/asimov/repository/git/obsidian-timestamp-utility/.env') as f:
    for line in f:
        if line.startswith('GITHUB_TOKEN='):
            val = line.strip().split('=', 1)[1]
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            os.environ['GITHUB_TOKEN'] = val
            break

os.environ['OLLAMA_HOST'] = 'http://localhost:11434'
os.environ['TEST_ISSUE_URL'] = 'https://github.com/andyholst/obsidian-timestamp-utility'

# Run the tests
result = subprocess.run(
    ['python3', '-m', 'pytest'] + sys.argv[1:] + ['-q', '--tb=short'],
    cwd='/home/asimov/repository/git/obsidian-timestamp-utility'
)
sys.exit(result.returncode)
