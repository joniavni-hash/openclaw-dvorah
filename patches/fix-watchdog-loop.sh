#!/usr/bin/env bash
# Patch: fix WhatsApp 499 reconnect loop
#
# Bug: createActiveConnectionRun() inherits lastInboundAt from the previous
# session's status object. After the watchdog fires for "30 min no messages",
# every reconnect immediately has a stale lastInboundAt, so the watchdog fires
# again within 60 seconds — creating a perpetual disconnect/reconnect loop.
#
# Fix: always pass null so each connection starts fresh. The watchdog then
# only fires if THIS connection has been silent for 30 minutes.
#
# Applied as ExecStartPre in openclaw-gateway systemd drop-in so it survives
# openclaw updates.

TARGET="/home/jonia/.npm-global/lib/node_modules/openclaw/dist/login-B2LDBtxK.js"
MARKER="fix: always start fresh so watchdog loop"

if [ ! -f "$TARGET" ]; then
  echo "[patch] WARNING: target file not found: $TARGET" >&2
  exit 0
fi

if grep -q "$MARKER" "$TARGET"; then
  echo "[patch] watchdog-loop fix already applied, skipping."
else
  # Verify the original line is present before patching
  if ! grep -q 'createActiveConnectionRun(status\.lastInboundAt' "$TARGET"; then
    echo "[patch] WARNING: expected line not found — openclaw may have been updated." >&2
    echo "[patch] Check if the fix still applies to the new version." >&2
  else
    # Back up then patch
    cp "$TARGET" "${TARGET}.bak"
    sed -i 's/createActiveConnectionRun(status\.lastInboundAt ?? status\.lastMessageAt ?? null)/createActiveConnectionRun(null) \/\/ fix: always start fresh so watchdog loop does not fire immediately on reconnect/g' "$TARGET"

    if grep -q "$MARKER" "$TARGET"; then
      echo "[patch] watchdog-loop fix applied successfully."
    else
      echo "[patch] ERROR: patch failed to apply." >&2
    fi
  fi
fi

# Patch 2: fix 408 Opening Handshake Timeout
# Bug: Baileys default connectTimeoutMs is 20s — too short for slow WhatsApp
# WS servers, causing "Opening handshake has timed out" errors and reconnects.
# Fix: increase to 45s.

SESSION_TARGET="/home/jonia/.npm-global/lib/node_modules/openclaw/dist/session-0W-jAnhj.js"
SESSION_MARKER="fix: increase from 20s default to avoid 408 handshake timeouts"

if [ ! -f "$SESSION_TARGET" ]; then
  echo "[patch] WARNING: session target file not found: $SESSION_TARGET" >&2
elif grep -q "$SESSION_MARKER" "$SESSION_TARGET"; then
  echo "[patch] connectTimeoutMs fix already applied, skipping."
else
  if ! grep -q 'markOnlineOnConnect: false$' "$SESSION_TARGET"; then
    echo "[patch] WARNING: connectTimeoutMs patch anchor not found — openclaw may have been updated." >&2
    echo "[patch] Check if the fix still applies to the new version." >&2
  else
    cp "$SESSION_TARGET" "${SESSION_TARGET}.bak"
    sed -i 's/markOnlineOnConnect: false$/markOnlineOnConnect: false,\n\t\tconnectTimeoutMs: 45000 \/\/ fix: increase from 20s default to avoid 408 handshake timeouts/g' "$SESSION_TARGET"

    if grep -q "$SESSION_MARKER" "$SESSION_TARGET"; then
      echo "[patch] connectTimeoutMs fix applied successfully."
    else
      echo "[patch] ERROR: connectTimeoutMs patch failed to apply." >&2
    fi
  fi
fi
