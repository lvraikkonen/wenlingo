from app.domain.models import EssayVersion
from app.services.essay_archive import get_round_index, get_version_label_for_round


def test_version_label_for_round_is_stable_and_legacy_compatible():
    assert get_version_label_for_round(1) == "first_draft"
    assert get_version_label_for_round(2) == "revision"
    assert get_version_label_for_round(3) == "revision_round_3"
    assert get_version_label_for_round(4) == "revision_round_4"


def test_get_round_index_reads_new_field_and_legacy_labels():
    assert (
        get_round_index(
            EssayVersion(
                essay_id="e",
                version_label="first_draft",
                content="x",
                round_index=1,
            )
        )
        == 1
    )
    assert (
        get_round_index(
            EssayVersion(
                essay_id="e",
                version_label="revision",
                content="x",
                round_index=2,
            )
        )
        == 2
    )
    assert get_round_index(EssayVersion(essay_id="e", version_label="revision", content="x")) == 2
