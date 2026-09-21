#!/usr/bin/env python3
import os
import sys
import re
import hashlib
import datetime

REQUIRED_FIELDS = ["id", "from", "to", "in_reply_to", "task", "type", "created", "content_sha256"]
ALLOWED_ROLES = ["PM", "ENG"]
ALLOWED_TYPES = ["assign", "report", "review", "question", "decision"]

def parse_frontmatter(content):
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", content, re.DOTALL)
    if not match:
        return None, None
    fm_raw, body = match.group(1), match.group(2)
    meta = {}
    for line in fm_raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if v == "null":
                v = None
            meta[k] = v
    return meta, body

def validate_message(content):
    meta, body = parse_frontmatter(content)
    if meta is None:
        return False, "FRONTMATTER_MISSING_OR_INVALID"
    
    for f in REQUIRED_FIELDS:
        if f not in meta:
            return False, f"MISSING_REQUIRED_FIELD_{f.upper()}"
            
    if meta.get("from") not in ALLOWED_ROLES:
        return False, f"INVALID_FROM_ROLE_{meta.get('from')}"
    if meta.get("to") not in ALLOWED_ROLES:
        return False, f"INVALID_TO_ROLE_{meta.get('to')}"
    if meta.get("type") not in ALLOWED_TYPES:
        return False, f"INVALID_TYPE_{meta.get('type')}"
        
    expected_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    actual_sha = meta.get("content_sha256")
    if actual_sha != expected_sha:
        return False, f"SHA256_MISMATCH (expected={expected_sha}, actual={actual_sha})"
        
    return True, "VALID"

def validate_file(filepath):
    if not os.path.exists(filepath):
        return False, f"FILE_NOT_FOUND: {filepath}"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return validate_message(content)
    except Exception as e:
        return False, f"READ_ERROR: {str(e)}"

def format_message(msg_id, from_role, to_role, in_reply_to, task, msg_type, body):
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    reply_val = in_reply_to if in_reply_to is not None else "null"
    return f"""---
id: {msg_id}
from: {from_role}
to: {to_role}
in_reply_to: {reply_val}
task: {task}
type: {msg_type}
created: {ts}
content_sha256: {sha}
---
{body}"""

def run_test_suite():
    root = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(root, "ledger", "T1_validate.log")
    test_dir = os.path.join(root, "ledger", "t1_cases")
    os.makedirs(test_dir, exist_ok=True)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # 5 Valid Messages
    valid_cases = [
        ("VALID_01", format_message("MSG-20260918-000001", "PM", "ENG", None, "TASK-0001", "assign", "Task 1 assignment body")),
        ("VALID_02", format_message("MSG-20260918-000002", "ENG", "PM", "MSG-20260918-000001", "TASK-0001", "report", "Implementation completed")),
        ("VALID_03", format_message("MSG-20260918-000003", "PM", "ENG", "MSG-20260918-000002", "TASK-0001", "review", "Review notes: please add test")),
        ("VALID_04", format_message("MSG-20260918-000004", "ENG", "PM", "MSG-20260918-000003", "TASK-0001", "question", "Clarification on test requirements")),
        ("VALID_05", format_message("MSG-20260918-000005", "PM", "ENG", "MSG-20260918-000004", "TASK-0001", "decision", "Decision: use unittest standard runner")),
    ]

    # 5 Invalid Messages
    invalid_cases = [
        ("INVALID_01_NO_FM", "This message has completely omitted frontmatter headers."),
        ("INVALID_02_MISSING_FIELD", "---\nid: MSG-01\nfrom: PM\nto: ENG\n---\nBody"),
        ("INVALID_03_HASH_MISMATCH", """---
id: MSG-20260918-000003
from: PM
to: ENG
in_reply_to: null
task: TASK-0001
type: assign
created: 2026-09-18T22:00:00Z
content_sha256: badhash1234567890badhash1234567890badhash1234567890badhash1234567890
---
Tampered body content"""),
        ("INVALID_04_BAD_ROLE", format_message("MSG-20260918-000004", "HACKER", "ENG", None, "TASK-0001", "assign", "Malicious sender")),
        ("INVALID_05_BAD_TYPE", format_message("MSG-20260918-000005", "PM", "ENG", None, "TASK-0001", "unsupported_type", "Bad message type")),
    ]

    results = []
    results.append(f"=== T1_validate.log - RUN AT {datetime.datetime.now().isoformat()} ===")
    
    passed_valid = 0
    passed_invalid = 0

    results.append("\n[TEST: 5 VALID MESSAGES]")
    for name, raw in valid_cases:
        p = os.path.join(test_dir, f"{name}.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(raw)
        ok, reason = validate_file(p)
        status_str = "PASS" if ok else "FAIL"
        if ok:
            passed_valid += 1
        results.append(f"{name}: result={status_str}, reason={reason}")

    results.append("\n[TEST: 5 INVALID MESSAGES]")
    for name, raw in invalid_cases:
        p = os.path.join(test_dir, f"{name}.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(raw)
        ok, reason = validate_file(p)
        status_str = "REJECTED_AS_EXPECTED" if not ok else "UNEXPECTED_PASS"
        if not ok:
            passed_invalid += 1
        results.append(f"{name}: result={status_str}, reason={reason}")

    results.append(f"\n[SUMMARY] VALID_PASSED={passed_valid}/5, INVALID_REJECTED={passed_invalid}/5")
    overall = "SUCCESS" if (passed_valid == 5 and passed_invalid == 5) else "FAILED"
    results.append(f"OVERALL_CRITERIA: {overall}")

    log_content = "\n".join(results) + "\n"
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(log_content)
    
    print(log_content)
    return overall == "SUCCESS"

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "--test":
        ok, reason = validate_file(sys.argv[1])
        print(f"{'VALID' if ok else 'INVALID'}: {reason}")
        sys.exit(0 if ok else 1)
    else:
        success = run_test_suite()
        sys.exit(0 if success else 1)
