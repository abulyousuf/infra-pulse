# Infra Pulse — Data Dictionary

**Database:** SQLite (`infra_pulse.db`) · **Journal mode:** WAL · **Foreign keys:** `PRAGMA foreign_keys=ON` (per connection)

This document describes every table and column in the Infra Pulse database.
It must be updated in the same commit as any schema change.

---

## targets

One row per monitored target (a website, host, port, or DNS name that Infra Pulse checks).

| Column | Type | Constraints | Default | Description | Example |
|--------|------|-------------|---------|-------------|---------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | — | Stable identity for the target. Referenced by `checks.target_id`; survives renames, which is why checks reference this and not `name`. | `1` |
| `name` | TEXT | NOT NULL, UNIQUE | — | Human-readable handle used by all CLI commands (`--name`). UNIQUE so commands like `remove --name` are unambiguous. | `GitHub API` |
| `type` | TEXT | NOT NULL, CHECK(type IN ('http','ping','tcp','dns')) | — | Which probe to run. The CHECK constraint enforces the four legal values at the database level, even if application code has a bug. | `http` |
| `target` | TEXT | NOT NULL | — | What to probe. Format depends on `type`: a full URL (http), a hostname/IP (ping, dns), or `host:port` (tcp). | `https://api.github.com` |
| `interval_seconds` | INTEGER | NOT NULL | `60` | How often the scheduler checks this target, in seconds. Each target has its own schedule. | `30` |
| `active` | INTEGER | NOT NULL | `1` | Boolean flag using the SQLite 0/1 convention. `1` = monitored, `0` = paused (via `disable`) without deleting history. New targets default to active. | `1` |
| `created_at` | TEXT | NOT NULL | — | Creation timestamp as an ISO 8601 UTC string. ISO strings sort chronologically as plain text, which is why TEXT works despite SQLite having no DATETIME type. | `2026-07-08T14:30:00+00:00` |

---

## checks

One row per check result. This table grows continuously while monitoring runs
(e.g. one target on a 60-second interval adds ~1,440 rows/day).

| Column | Type | Constraints | Default | Description | Example |
|--------|------|-------------|---------|-------------|---------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | — | Row identity. | `4821` |
| `target_id` | INTEGER | NOT NULL, REFERENCES targets(id) ON DELETE CASCADE | — | Which target this result belongs to. CASCADE means deleting a target automatically purges its history — no orphan rows. Requires foreign keys to be enabled on the connection. | `1` |
| `checked_at` | TEXT | NOT NULL | — | When the check ran, as an ISO 8601 UTC string (same pattern as `targets.created_at`). | `2026-07-08T14:31:02+00:00` |
| `status` | TEXT | NOT NULL, CHECK(status IN ('up','down','error')) | — | Outcome of the check. `up` = healthy; `down` = probe completed and the target is unhealthy/unreachable; `error` = the probe itself could not run meaningfully (e.g. bad input, missing ping binary). | `up` |
| `response_time_ms` | REAL | *(nullable)* | — | Response time in milliseconds. **Deliberately nullable:** NULL means "no measurement was possible", which is semantically different from `0` ("instantaneous"). | `122.32` |
| `detail` | TEXT | *(nullable)* | — | Human-readable context for the result, shown in reports and alerts. | `HTTP 200` |

---

## Relationships

```
targets (1) ────< (many) checks
```

- `checks.target_id → targets.id`, **ON DELETE CASCADE** — a target's entire
  check history is removed automatically when the target is deleted.

## Indexes

| Index | On | Why |
|-------|----|----|
| `idx_checks_target_id` | `checks(target_id)` | Report and history queries always filter by target; without this, every report scans the whole (large, ever-growing) table. |
| `idx_checks_checked_at` | `checks(checked_at)` | Uptime statistics filter by time window ("last 24 hours"). |

## Conventions

- **Timestamps:** always UTC, always ISO 8601 TEXT. Never store local time.
- **Booleans:** INTEGER `0`/`1` (SQLite has no BOOLEAN type).
- **Enumerations** (`type`, `status`): enforced with CHECK constraints at the
  database level *and* validated in application code — defence in depth.
