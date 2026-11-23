#!/usr/bin/env python3
"""Classify each voicebot call into exactly one outcome label.

Usage: python3 classify.py data/transcripts.jsonl > predictions_night1.csv

Rule: what the caller left with. We replay events in time order up to the
hangup and keep the *last* outcome reached. Only structured events are used
(tool results, transfer, route), never bot wording, so a reworded flow still
classifies. Unknown statuses / fields degrade to the safest reading
(non-"ok" = failure) and are reported on stderr so drift is visible.
"""
import csv
import json
import re
import sys
from collections import Counter

OK = {"ok", "success", "found", "created", "completed"}
TRANSFER_OK = {"connected", "answered", "accepted", "ok", "success"}
# resolve_address statuses meaning "didn't understand the address" (vs. technical failure)
ADDRESS_MISS = {"no_match", "ambiguous", "not_found", "no_candidates", "low_confidence"}
SUCCESS = {"KNOWN_OUTAGE_INFORMED", "TICKET_CREATED", "TRANSFERRED"}

# what night 1 looked like; anything else is reported as DRIFT (never changes a label)
SEEN = {
    "status": {"ok", "no_match", "ambiguous", "timeout", "connected", "queue_full"},
    "tool": {"resolve_address", "get_outage", "create_ticket"},
    "type": {"bot", "caller", "tool_call", "tool_result", "transfer", "route", "hangup"},
    "hangup_by": {"caller", "bot", "system"},
    "target": {"dispatch", "customer_line"},
    "outage_key": {"outage_id", "eta"},
}
drift = Counter()


def seen(kind, value):
    if value not in SEEN[kind]:
        drift[f"new {kind}: {value}"] += 1


def tool_kind(e):
    """Map a tool event to address/outage/ticket by name, falling back to result shape."""
    name = str(e.get("name") or "").lower()
    if name:
        seen("tool", name)
    for kind in ("address", "outage", "ticket"):
        if kind in name:
            return kind
    r = e.get("result") if isinstance(e.get("result"), dict) else {}
    for kind in ("address", "outage", "ticket"):
        if f"{kind}_id" in r:
            return kind
    return None


def outage_known(result):
    if not isinstance(result, dict):
        return False
    for k in result:
        seen("outage_key", k)
    return bool(result.get("outage_id") or result.get("outages") or result.get("eta"))


def is_ok(e):
    s = str(e.get("status") or "").lower()
    seen("status", s)
    r = e.get("result") if isinstance(e.get("result"), dict) else {}
    return s in OK or bool(r.get("ticket_id"))  # a ticket id means the ticket exists, whatever the status says


def t_of(e):
    try:
        return float(e.get("t", 0))
    except (TypeError, ValueError):
        drift["non-numeric t"] += 1
        return 0.0


def classify(events):
    events = [e for e in events if isinstance(e, dict)]
    if not events:
        drift["empty events"] += 1
    ts = [t_of(e) for e in events]
    if ts != sorted(ts):
        drift["events out of order"] += 1
    events = sorted(events, key=t_of)  # stable: keeps file order on ties
    hang = next((i for i, e in enumerate(events) if e.get("type") == "hangup"), len(events))
    if hang == len(events) and events:
        drift["missing hangup"] += 1
    else:
        for e in events[hang:hang + 1]:
            seen("hangup_by", str(e.get("by")))
    live, after = events[:hang], events[hang:]
    has_bot_text = any(e.get("type") == "bot" for e in events)

    label = "ENDED_EARLY"
    addr_trouble = False  # a failed or rejected address attempt with no later recovery
    pending = {}  # kind -> unanswered tool_call at hangup
    last_addr_ok = False

    for e in live:
        typ = e.get("type")
        seen("type", str(typ))
        if typ == "tool_call":
            kind = tool_kind(e)
            if kind == "address" and last_addr_ok:
                addr_trouble = True  # resolved, but bot asks again -> caller rejected it
            pending[kind] = e
        elif typ == "tool_result":
            kind = tool_kind(e)
            pending.pop(kind, None)
            ok = is_ok(e)
            status = str(e.get("status") or "").lower()
            if kind == "address":
                last_addr_ok = ok
                if ok:
                    continue
                if status in ADDRESS_MISS:
                    addr_trouble = True
                elif label not in SUCCESS:  # technical failure of our resolver
                    label = "API_ERROR"
            elif kind == "outage":
                last_addr_ok, addr_trouble = False, False
                if not ok:
                    if label not in SUCCESS:  # a failed refresh can't take back what the caller heard
                        label = "API_ERROR"
                elif outage_known(e.get("result")):
                    # the caller must actually hear it: a bot line at/after the result, before hangup
                    told = not has_bot_text or any(
                        x.get("type") == "bot" and t_of(x) >= t_of(e) for x in live)
                    if told:
                        label = "KNOWN_OUTAGE_INFORMED"
                # ok + unknown outage: flow continues (ticket / danger transfer)
            elif kind == "ticket":
                if ok:
                    label = "TICKET_CREATED"
                elif label not in SUCCESS:  # e.g. failing update_ticket after a created ticket
                    label = "API_ERROR"
        elif typ == "transfer":
            st = str(e.get("status") or "").lower()
            target = str(e.get("target") or "").lower()
            seen("status", st)
            seen("target", target)
            if "customer" in target:  # sent elsewhere, not to dispatch
                label = "OUT_OF_SCOPE"
            else:
                label = "TRANSFERRED" if st in TRANSFER_OK else "TRANSFER_FAILED"
            addr_trouble = False
        elif typ == "route":
            label = "OUT_OF_SCOPE"
            addr_trouble = False

    # Caller hung up while a tool was still running: judge by what the tool did next.
    for kind, call in pending.items():
        late = next((e for e in after if e.get("type") == "tool_result" and tool_kind(e) == kind), None)
        late_ok = late is not None and is_ok(late)
        if kind == "ticket" and late_ok:
            label = "TICKET_CREATED"  # ponytail: ticket exists even if caller missed the number
        elif kind in ("outage", "ticket") and not late_ok:
            label = "API_ERROR"  # tool never answered / failed: the caller gave up on us
        # late ok outage / address -> caller left before hearing it: ENDED_EARLY stays

    # Caller hung up while being transferred and the transfer then failed.
    late_xfer = next((e for e in after if e.get("type") == "transfer"), None)
    if label == "ENDED_EARLY" and late_xfer and str(late_xfer.get("status") or "").lower() not in TRANSFER_OK:
        label = "TRANSFER_FAILED"

    if label == "ENDED_EARLY" and addr_trouble:
        # never got past the address: bot gave up, or caller quit after a miss/rejection
        label = "ADDRESS_NOT_UNDERSTOOD"
    return label


def salvage(line):
    """Broken JSON line: recover call_id and every complete event before the damage."""
    cid = re.search(r'"call_id"\s*:\s*"([^"]+)"', line).group(1)
    events, dec = [], json.JSONDecoder()
    m = re.search(r'"events"\s*:\s*\[', line)
    i = m.end() if m else len(line)
    while True:
        while i < len(line) and line[i] in " ,\n\r\t":
            i += 1
        try:
            e, i = dec.raw_decode(line, i)
        except ValueError:
            return cid, events
        events.append(e)


def main(path):
    out = csv.writer(sys.stdout, lineterminator="\n")
    out.writerow(["call_id", "label"])
    seen_ids, counts = set(), Counter()
    with open(path, encoding="utf-8-sig") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                cid, events = d["call_id"], d.get("events") or []
            except Exception as ex:
                try:
                    cid, events = salvage(line)
                    drift["salvaged malformed line"] += 1
                except Exception:  # not even a call_id: nothing to write a row for
                    print(f"line {n}: skipped ({ex!r})", file=sys.stderr)
                    continue
            if cid in seen_ids:
                drift["duplicate call_id"] += 1
                continue
            seen_ids.add(cid)
            label = classify(events)
            counts[label] += 1
            out.writerow([cid, label])
    print(f"{len(seen_ids)} calls: " + ", ".join(f"{k}={v}" for k, v in counts.most_common()), file=sys.stderr)
    for k, v in drift.most_common():
        print(f"DRIFT {k}: {v}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/transcripts.jsonl")
