#!/bin/bash
set -e

# Keep .claude.json inside the persistent volume via symlink
mkdir -p /root/.claude
if [ -f /root/.claude/.claude.json ]; then
    ln -sf /root/.claude/.claude.json /root/.claude.json
else
    ln -sf /root/.claude/.claude.json /root/.claude.json
fi

# Authenticate Claude Code if needed (streams OAuth URL to docker logs)
python3 /app/scripts/claude_auth.py

exec "$@"
