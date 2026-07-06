BASELINE_CASES = [
    ("person_portrait", "case-1"),
    ("person_portrait", "case-2"),
    ("event_narrative", "case-1"),
    ("event_narrative", "case-2"),
    ("place_scenery", "case-1"),
    ("place_scenery", "case-2"),
    ("object_description", "case-1"),
    ("object_description", "case-2"),
    ("practical_writing", "case-1"),
    ("practical_writing", "case-2"),
    ("imagination", "case-1"),
    ("imagination", "case-2"),
    ("reading_response", "case-1"),
    ("reading_response", "case-2"),
    ("generic_narrative", "case-1"),
    ("generic_narrative", "case-2"),
]


def test_material_card_reliability_baseline_has_required_shape():
    assert len(BASELINE_CASES) == 16
    assert len({family for family, _ in BASELINE_CASES}) == 8
