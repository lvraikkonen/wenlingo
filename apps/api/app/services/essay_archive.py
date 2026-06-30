from app.domain.models import EssayVersion


def get_version_label_for_round(round_index: int) -> str:
    if round_index < 1:
        raise ValueError("round_index must be positive")
    if round_index == 1:
        return "first_draft"
    if round_index == 2:
        return "revision"
    return f"revision_round_{round_index}"


def get_round_index(version: EssayVersion) -> int:
    if version.round_index is not None:
        if version.round_index < 1:
            raise ValueError("round_index must be positive")
        return version.round_index
    if version.version_label == "first_draft":
        return 1
    if version.version_label == "revision":
        return 2
    if version.version_label.startswith("revision_round_"):
        round_suffix = version.version_label.removeprefix("revision_round_")
        if not round_suffix.isdecimal():
            raise ValueError(f"unknown essay version label: {version.version_label}")
        round_index = int(round_suffix)
        if round_index < 1:
            raise ValueError("round_index must be positive")
        return round_index
    raise ValueError(f"unknown essay version label: {version.version_label}")
