from collections import deque

import yaml
from django.conf import settings


def load_state_machine():
    yaml_path = settings.BASE_DIR / "docs" / "state_machine.yaml"
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_states_referenced_in_transitions_exist():
    sm = load_state_machine()
    states = sm["states"]
    for t in sm["transitions"]:
        from_st = t["from"]
        to_st = t["to"]
        assert from_st in states, f"Transition 'from' state {from_st} does not exist in states"
        assert to_st in states, f"Transition 'to' state {to_st} does not exist in states"


def test_every_state_reachable_from_submitted():
    sm = load_state_machine()
    states = set(sm["states"].keys())

    adj = {s: set() for s in states}
    for t in sm["transitions"]:
        adj[t["from"]].add(t["to"])

    visited = set()
    queue = deque(["SUBMITTED"])
    while queue:
        curr = queue.popleft()
        if curr not in visited:
            visited.add(curr)
            for neighbor in adj[curr]:
                if neighbor not in visited:
                    queue.append(neighbor)

    unreachable = states - visited
    assert not unreachable, f"States unreachable from SUBMITTED: {unreachable}"


def test_non_terminal_states_have_outgoing_transitions():
    sm = load_state_machine()
    states = sm["states"]
    outgoing = {s: 0 for s in states}
    for t in sm["transitions"]:
        outgoing[t["from"]] += 1

    for state_name, state_meta in states.items():
        if not state_meta.get("terminal", False):
            assert outgoing[state_name] > 0, (
                f"Non-terminal state {state_name} has no outgoing transitions"
            )


def test_terminal_states_transitions_guarded():
    sm = load_state_machine()
    states = sm["states"]
    for t in sm["transitions"]:
        from_st = t["from"]
        if states[from_st].get("terminal", False):
            assert states[from_st].get("reopenable", False) is True, (
                f"Terminal state {from_st} has outgoing transition but is not marked reopenable"
            )
            assert t["to"] == "REOPENED", (
                f"Terminal state {from_st} can only transition to REOPENED, found: {t['to']}"
            )


def test_transition_roles():
    valid_roles = {"requester", "technician", "admin", "system"}
    sm = load_state_machine()
    for t in sm["transitions"]:
        roles = t.get("roles", [])
        assert len(roles) >= 1, f"Transition {t['from']} -> {t['to']} has no roles defined"
        for r in roles:
            assert r in valid_roles, (
                f"Invalid role '{r}' in transition {t['from']} -> {t['to']}"
            )


def test_path_submitted_to_verified_fixed_exists():
    sm = load_state_machine()
    adj = {s: set() for s in sm["states"]}
    for t in sm["transitions"]:
        adj[t["from"]].add(t["to"])

    visited = set()
    queue = deque([("SUBMITTED", ["SUBMITTED"])])
    found_path = None
    while queue:
        curr, path = queue.popleft()
        if curr == "VERIFIED_FIXED":
            found_path = path
            break
        if curr not in visited:
            visited.add(curr)
            for nxt in adj[curr]:
                queue.append((nxt, path + [nxt]))

    assert found_path is not None, "No path exists from SUBMITTED to VERIFIED_FIXED"


def test_color_rules_for_verified_fixed_and_reported_fixed():
    sm = load_state_machine()
    states = sm["states"]

    assert states["VERIFIED_FIXED"]["color"] == "green", (
        "VERIFIED_FIXED state must have color 'green'"
    )
    assert states["REPORTED_FIXED"]["color"] == "amber", (
        "REPORTED_FIXED state must have color 'amber' (technician report is not proof of repair)"
    )

    for state_name, state_meta in states.items():
        if state_name != "VERIFIED_FIXED":
            assert state_meta.get("color") != "green", (
                f"State {state_name} has color 'green'; VERIFIED_FIXED must be the ONLY green state."
            )
