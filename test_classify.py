"""python3 test_classify.py — labeled sample must stay 60/60 under "next night" drift."""
import copy
import json
import random

from classify import classify

sample = [json.loads(l) for l in open("data/labeled_sample.jsonl", encoding="utf-8")]


def score(mutate):
    bad = [(d["call_id"], d["label"], classify(mutate(copy.deepcopy(d["events"])))) for d in sample]
    bad = [b for b in bad if b[1] != b[2]]
    assert not bad, (mutate.__name__, bad)


def identity(ev): return ev
def no_text(ev): return [e for e in ev if e["type"] not in ("bot", "caller")]
def shuffled(ev): random.Random(1).shuffle(ev); return ev
def renamed_tools(ev):
    for e in ev:
        if "name" in e: e["name"] += "_v2"
    return ev
def new_errors(ev):
    for e in ev:
        if e.get("status") == "timeout": e["status"] = "http_503"
        if e.get("status") == "queue_full": e["status"] = "rejected"
    return ev


for m in (identity, no_text, shuffled, renamed_tools, new_errors):
    score(m)

# a fallback appearing on night 2: last outcome wins
R = lambda n, s, r=None, t=0: {"t": t, "type": "tool_result", "name": n, "status": s, "result": r}
C = lambda n, t=0: {"t": t, "type": "tool_call", "name": n}
H = lambda t: {"t": t, "type": "hangup", "by": "bot"}
addr = [C("resolve_address", 1), R("resolve_address", "ok", {"address_id": "A"}, 2)]
assert classify(addr + [C("get_outage", 3), R("get_outage", "timeout", None, 4),
                        C("get_outage", 5), R("get_outage", "ok", {"outage_id": "O"}, 6), H(7)]) == "KNOWN_OUTAGE_INFORMED"
assert classify(addr + [C("get_outage", 3), R("get_outage", "timeout", None, 4),
                        C("create_ticket", 5), R("create_ticket", "ok", {"ticket_id": "T"}, 6), H(7)]) == "TICKET_CREATED"
assert classify(addr + [C("get_outage", 3), R("get_outage", "error", None, 4),
                        {"t": 5, "type": "transfer", "target": "dispatch", "status": "connected"}, H(6)]) == "TRANSFERRED"
assert classify([]) == "ENDED_EARLY"
# from the night-2 red team
X = lambda st, target="dispatch", t=0: {"t": t, "type": "transfer", "target": target, "status": st}
assert classify([{"t": 1, "type": "hangup", "by": "caller"}, X("timeout", t=9)]) == "TRANSFER_FAILED"
assert classify([X("connected", "customer_line", 1), H(2)]) == "OUT_OF_SCOPE"
assert classify(addr + [C("create_ticket", 3), R("create_ticket", "created", {"ticket_id": "T"}, 4),
                        C("update_ticket", 5), R("update_ticket", "timeout", None, 6), H(7)]) == "TICKET_CREATED"
assert classify(addr + [C("get_outage", 3), R("get_outage", "ok", {"outage_id": "O"}, 4),
                        {"t": 2, "type": "bot", "text": "x"}, H(4)]) == "ENDED_EARLY"  # bot never said it
print("ok")
