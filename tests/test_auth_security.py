"""Regression tests for authentication validation and token safety."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from auth.user_auth import AuthManager
from auth.validation import normalize_email, normalize_username, validate_password
from database.models import DatabaseManager, LoginThrottleState


TEST_SECRET = "test-only-secret-key-that-is-longer-than-32-characters"
VALID_PASSWORD = "correct-horse-42"


@pytest.fixture
def db_manager(tmp_path: Path):
    manager = DatabaseManager(
        f"sqlite:///{(tmp_path / 'auth.db').as_posix()}", create_schema=True
    )
    yield manager
    manager.close()


def test_auth_manager_rejects_missing_or_short_secret(db_manager):
    with pytest.raises(ValueError, match="32 characters"):
        AuthManager("short", db_manager=db_manager)


@pytest.mark.parametrize("username", [None, "ab", "a" * 21, "bad name", "<script>"])
def test_username_validation_rejects_invalid_values(username):
    with pytest.raises(ValueError):
        normalize_username(username)


@pytest.mark.parametrize("email", [None, "missing-at.example.com", "a@b", "x" * 255])
def test_email_validation_rejects_invalid_values(email):
    with pytest.raises(ValueError):
        normalize_email(email)


@pytest.mark.parametrize(
    "password", [None, "short1", "onlyletterslong", "123456789012", "safePassword1\n"]
)
def test_password_validation_rejects_weak_or_unsafe_values(password):
    with pytest.raises(ValueError):
        validate_password(password)


def test_password_validation_accepts_eight_character_boundary():
    assert validate_password("abc12345") == "abc12345"


@pytest.mark.parametrize("password", ["abc1234", "abcdefgh", "12345678"])
def test_password_validation_rejects_short_or_single_class_boundary(password):
    with pytest.raises(ValueError):
        validate_password(password)


def test_user_ids_are_collision_resistant_and_email_is_normalized(db_manager):
    auth = AuthManager(TEST_SECRET, db_manager=db_manager)
    first = auth.create_user("audit_one", "One@Example.COM", VALID_PASSWORD)
    second = auth.create_user("audit_two", "two@example.com", VALID_PASSWORD)

    assert first.id != second.id
    assert first.id.startswith("user_")
    assert first.email == "one@example.com"


def test_token_has_required_claims_and_invalid_token_fails_closed(db_manager):
    auth = AuthManager(TEST_SECRET, db_manager=db_manager)
    user = auth.create_user("audit_user", "audit@example.com", VALID_PASSWORD)

    token = auth.authenticate(user.username, VALID_PASSWORD)
    payload = auth.verify_token(token)

    assert payload is not None
    assert payload["user_id"] == user.id
    assert payload["iss"] == "ssm-quant"
    assert payload["aud"] == "ssm-web"
    assert auth.verify_token("not-a-token") is None


def test_login_rejects_oversized_untrusted_identity(db_manager):
    auth = AuthManager(TEST_SECRET, db_manager=db_manager)
    assert auth.authenticate("x" * 300, VALID_PASSWORD) is None


def test_login_is_blocked_after_repeated_failures_and_raw_identity_is_not_stored(
    db_manager,
):
    auth = AuthManager(TEST_SECRET, db_manager=db_manager)
    auth.create_user("rate_limited", "rate@example.com", VALID_PASSWORD)

    for _ in range(5):
        assert auth.authenticate("rate_limited", "wrong-password-1") is None
    assert auth.authenticate("rate_limited", VALID_PASSWORD) is None

    session = db_manager.get_session()
    try:
        states = session.query(LoginThrottleState).all()
        assert len(states) == 1
        assert states[0].identity_hash != "rate_limited"
        assert len(states[0].identity_hash) == 64
    finally:
        session.close()


def test_concurrent_login_failures_are_counted_atomically(db_manager):
    throttle = AuthManager(TEST_SECRET, db_manager=db_manager).login_throttle

    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda _: throttle.record_failure("parallel_user"), range(20)))

    session = db_manager.get_session()
    try:
        state = session.get(LoginThrottleState, throttle._key("parallel_user"))
        assert state is not None
        assert state.failure_count == 20
        assert state.blocked_until is not None
        assert state.blocked_until > datetime.now()
    finally:
        session.close()


def test_expired_login_block_restarts_the_failure_window(db_manager):
    throttle = AuthManager(TEST_SECRET, db_manager=db_manager).login_throttle
    for _ in range(throttle.MAX_FAILURES):
        throttle.record_failure("expired_user")

    session = db_manager.get_session()
    try:
        state = session.get(LoginThrottleState, throttle._key("expired_user"))
        state.blocked_until = datetime.now() - timedelta(seconds=1)
        session.commit()
    finally:
        session.close()

    throttle.record_failure("expired_user")

    session = db_manager.get_session()
    try:
        state = session.get(LoginThrottleState, throttle._key("expired_user"))
        assert state.failure_count == 1
        assert state.blocked_until is None
    finally:
        session.close()
