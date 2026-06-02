from app.services.auth_security import (
    generate_magic_code,
    generate_session_token,
    hash_secret,
    mask_email,
    mask_phone,
    normalize_email,
    normalize_phone,
)


def test_normalize_email_trims_and_lowercases():
    assert normalize_email(" Parent@Example.COM ") == "parent@example.com"


def test_normalize_phone_converts_china_mobile_short_form_to_e164():
    assert normalize_phone("138 0000 1234") == "+8613800001234"


def test_hash_secret_uses_pepper_and_purpose_without_returning_raw_value():
    raw_value = "123456"

    parent_login_hash = hash_secret(raw_value, purpose="magic-code", pepper="pepper-a")
    changed_purpose_hash = hash_secret(raw_value, purpose="request-ip", pepper="pepper-a")
    changed_pepper_hash = hash_secret(raw_value, purpose="magic-code", pepper="pepper-b")

    assert parent_login_hash != raw_value
    assert raw_value not in parent_login_hash
    assert parent_login_hash != changed_purpose_hash
    assert parent_login_hash != changed_pepper_hash


def test_generate_magic_code_returns_six_digit_string():
    code = generate_magic_code()

    assert len(code) == 6
    assert code.isdigit()


def test_generate_session_token_returns_non_trivial_string():
    token = generate_session_token()

    assert isinstance(token, str)
    assert len(token) >= 32


def test_mask_email_keeps_first_two_letters_and_domain():
    assert mask_email("lixing@example.com") == "li***@example.com"


def test_mask_phone_masks_china_mobile_number():
    assert mask_phone("+8613800001234") == "138****1234"
