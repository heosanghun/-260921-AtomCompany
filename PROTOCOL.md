# Atom Company Folder Communication Protocol (PROTOCOL.md)

- Protocol Version: 1.0.0
- Directive Reference: AG-D-260918-AC-01
- Scope: File-based asynchronous inter-agent communication between PM and ENG

---

## 1. Directory Structure

```text
$ROOT/
  ROLES/
    PM.md                      # PM System Prompt & Guidelines
    ENG.md                     # ENG System Prompt & Guidelines
  inbox/
    PM/                        # Unprocessed incoming messages for PM
    ENG/                       # Unprocessed incoming messages for ENG
  done/                        # Processed messages moved here atomically
  tasks/
    TASK-XXXX.md               # Task cards (todo | doing | review | done | blocked)
  workspace/                   # Target software deliverables and automated tests
  HUMAN_GATE/                  # Approval requests for human review
  ledger/                      # Operational ledgers, execution logs, and metrics
```

---

## 2. Message Format

Every message exchanged between agents must be a UTF-8 Markdown file with a YAML-style frontmatter header:

```markdown
---
id: MSG-20260918-000001
from: PM | ENG
to: PM | ENG
in_reply_to: MSG-20260918-000000 | null
task: TASK-0001
type: assign | report | review | question | decision
created: 2026-09-18T22:45:00.000000+09:00
content_sha256: 7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069
---

## Message Body
Actual content, instructions, execution reports, or queries.
```

### Frontmatter Fields:
1. `id`: Format `MSG-YYYYMMDD-XXXXXX`.
2. `from`: Originating agent role (`PM` or `ENG`).
3. `to`: Recipient agent role (`PM` or `ENG`).
4. `in_reply_to`: Previous message ID or `null`.
5. `task`: Associated task card ID (e.g. `TASK-0001`).
6. `type`: One of `assign`, `report`, `review`, `question`, `decision`.
7. `created`: ISO 8601 timestamp with timezone.
8. `content_sha256`: Hex-encoded SHA256 hash of the trimmed message body (excluding frontmatter).

---

## 3. Atomic Write Rule

To prevent partial reads or race conditions during polling:
1. The sender writes the message file to a temporary file in the destination folder with suffix `.tmp` (e.g., `inbox/ENG/MSG-20260918-000001.tmp`).
2. The sender flushes and syncs the file descriptor (`f.flush()`, `os.fsync()`).
3. The sender performs an atomic rename via `os.replace(tmp_path, target_path)`.
4. File name must strictly match `<id>.md`.

---

## 4. Message Lifecycle

1. **Generation**: Sender formats message, calculates SHA256 of body, and writes atomically to recipient's `inbox/<ROLE>/<id>.md`.
2. **Polling**: Recipient periodically polls its `inbox/<ROLE>/` for `.md` files.
3. **Validation**: Recipient validates frontmatter and SHA256. Invalid messages are rejected and logged.
4. **Execution**: Recipient executes reasoning, invokes workspace tools if necessary, and drafts response.
5. **Completion**: Recipient moves the processed message to `done/<id>.md` via `os.replace()`, then writes 1 line to `ledger/agent_<ROLE>.log`.

---

## 5. Task Card Specification

Task cards reside in `tasks/TASK-XXXX.md` with frontmatter:
```markdown
---
id: TASK-0001
title: Task Title
status: todo | doing | review | done | blocked
assigned_to: ENG
created: <ISO8601>
updated: <ISO8601>
---
```
