import uuid

import pytest

from app.core.errors import AppError
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_nfr02_password_hash_is_argon2_and_verifies():
    h = hash_password("Correct-Horse-1")
    assert h.startswith("$argon2id$") and "Correct-Horse-1" not in h
    assert verify_password(h, "Correct-Horse-1")
    assert not verify_password(h, "wrong")


def test_nfr02_tampered_token_rejected():
    tok = create_access_token(uuid.uuid4(), "staff", "Admin")
    head, body, sig = tok.split(".")
    forged = ".".join([head, body, sig[::-1]])
    with pytest.raises(AppError) as e:
        decode_access_token(forged)
    assert e.value.code == "ERR_TOKEN_INVALID"
