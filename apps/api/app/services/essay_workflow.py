ASSESSMENT_ESSAY_STATUS = "assessment_completed"
REVISION_REQUESTED_STATUS = "revision_requested"
SETTLED_ESSAY_STATUS = "settled"


def draft_ability_deltas(improvement_count: int) -> dict[str, int]:
    delta = 3 if improvement_count == 3 else 5
    return {"expression": delta, "structure": delta}


def revision_ability_deltas(evidence_count: int) -> dict[str, int]:
    return {"revision": 5 if evidence_count >= 2 else 4}
