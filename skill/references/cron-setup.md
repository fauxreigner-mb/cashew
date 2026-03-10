# Cashew Cron Jobs — Install Guide

When the user says "install cashew crons" or on first setup, create these cron jobs via the OpenClaw `cron` tool. Adjust paths to match the user's workspace.

## Required: Memory Extract (every 2 hours)

Checks if new conversation content exists since last extraction, extracts to brain only if there's a diff.

```json
{
  "name": "cashew-memory-extract",
  "schedule": {"kind": "cron", "expr": "0 */2 * * *", "tz": "USER_TIMEZONE"},
  "sessionTarget": "isolated",
  "delivery": {"mode": "none"},
  "payload": {
    "kind": "agentTurn",
    "model": "SONNET_MODEL_ID",
    "timeoutSeconds": 180,
    "message": "Check if there's new content to extract to the cashew brain.\n\n1. Check last extraction timestamp:\n```bash\ncashew stats | grep -i recent\nsqlite3 $CASHEW_DB \"SELECT MAX(timestamp) FROM thought_nodes WHERE source_file LIKE '%extraction%'\"\n```\n\n2. Check today's memory/daily log file for content newer than that timestamp.\n\n3. If new substantive content exists (decisions, insights, project updates — not just 'checked email'), extract it:\n```bash\ncat <daily_log_path> > /tmp/cashew-extract-input.md\ncashew extract --input /tmp/cashew-extract-input.md\n```\n\nIf nothing to extract, reply: MEMORY_CHECK_OK"
  }
}
```

## Required: Sleep Cycle (every 6 hours)

Consolidates knowledge, runs clustering, evolves hierarchy.

```json
{
  "name": "cashew-sleep-cycle",
  "schedule": {"kind": "every", "everyMs": 21600000},
  "sessionTarget": "isolated",
  "delivery": {"mode": "none"},
  "payload": {
    "kind": "agentTurn",
    "model": "SONNET_MODEL_ID",
    "timeoutSeconds": 180,
    "message": "Run the cashew sleep cycle:\n```bash\ncashew sleep --debug\n```\nReport output briefly. Note anything interesting (new cross-links, tensions). Otherwise confirm: SLEEP_OK"
  }
}
```

## Required: DB Backup (every 6 hours)

Safety net — never lose the brain.

```json
{
  "name": "cashew-db-backup",
  "schedule": {"kind": "cron", "expr": "0 */6 * * *", "tz": "USER_TIMEZONE"},
  "sessionTarget": "isolated",
  "delivery": {"mode": "none"},
  "payload": {
    "kind": "agentTurn",
    "model": "SONNET_MODEL_ID",
    "timeoutSeconds": 30,
    "message": "Backup the cashew database:\n```bash\nDB=\"${CASHEW_DB:-./data/graph.db}\"\nBACKUP_DIR=\"$(dirname $DB)/backups\"\nmkdir -p $BACKUP_DIR\nsqlite3 $DB \".backup '$BACKUP_DIR/graph-$(date +%Y%m%d-%H%M%S).db'\"\nls -1t $BACKUP_DIR/graph-*.db | tail -n +5 | xargs rm -f 2>/dev/null\necho \"Backup done. $(ls -1 $BACKUP_DIR/graph-*.db | wc -l) backups retained.\"\n```\nReport result briefly. If it fails, alert the user."
  }
}
```

## Optional: Health Check (daily)

Monitors graph stats and detects regressions.

```json
{
  "name": "cashew-health-check",
  "schedule": {"kind": "cron", "expr": "0 8 * * *", "tz": "USER_TIMEZONE"},
  "sessionTarget": "isolated",
  "delivery": {"mode": "none"},
  "payload": {
    "kind": "agentTurn",
    "model": "SONNET_MODEL_ID",
    "timeoutSeconds": 60,
    "message": "Run cashew health check:\n```bash\ncashew stats\n```\nVerify node count hasn't dropped, embedding coverage is 100%. If anything looks wrong, alert the user. Otherwise: HEALTH_OK"
  }
}
```

## Optional: Dashboard Deploy (daily)

If using the web dashboard.

```json
{
  "name": "cashew-dashboard-deploy",
  "schedule": {"kind": "cron", "expr": "30 7 * * *", "tz": "USER_TIMEZONE"},
  "sessionTarget": "isolated",
  "delivery": {"mode": "none"},
  "payload": {
    "kind": "agentTurn",
    "model": "SONNET_MODEL_ID",
    "timeoutSeconds": 120,
    "message": "Export and deploy the cashew dashboard:\n```bash\nbash scripts/deploy-dashboard.sh\n```\nReport success/failure."
  }
}
```

## Setup Notes

- Replace `USER_TIMEZONE` with the user's timezone (e.g., `America/Los_Angeles`)
- Replace `SONNET_MODEL_ID` with the available Sonnet model (e.g., `anthropic/claude-sonnet-4-20250514`)
- Replace `$CASHEW_DB` with the actual database path if not using env var
- The memory extract job needs to know where daily logs are stored — adapt the path
