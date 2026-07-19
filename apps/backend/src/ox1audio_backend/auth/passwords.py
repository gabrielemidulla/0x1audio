from __future__ import annotations

from pwdlib import PasswordHash

from ox1audio_backend.shared_constants import (
    PASSWORD_MIN_LENGTH,
    PASSWORD_RULES,
    PasswordRuleKind,
)

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def _rule_passes(kind: PasswordRuleKind, password: str) -> bool:
    if kind == "min_length":
        return len(password) >= PASSWORD_MIN_LENGTH
    if kind == "has_upper":
        return any(ch.isupper() for ch in password)
    if kind == "has_lower":
        return any(ch.islower() for ch in password)
    if kind == "has_digit":
        return any(ch.isdigit() for ch in password)
    if kind == "has_special":
        return any(not ch.isalnum() for ch in password)
    raise ValueError(f"Unknown password rule kind: {kind}")


def validate_password_strength(password: str) -> str | None:
    """Return an error message if weak, otherwise None."""
    for rule in PASSWORD_RULES:
        if not _rule_passes(rule["kind"], password):
            # Keep API error copy imperative ("must …") while UI labels stay short.
            if rule["kind"] == "min_length":
                return f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
            if rule["kind"] == "has_upper":
                return "Password must include an uppercase letter"
            if rule["kind"] == "has_lower":
                return "Password must include a lowercase letter"
            if rule["kind"] == "has_digit":
                return "Password must include a number"
            if rule["kind"] == "has_special":
                return "Password must include a special character"
    return None
