"""Database-backed login throttling without storing raw login identities."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Optional, cast

from sqlalchemy import and_, case
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database.models import DatabaseManager, LoginThrottleState


class LoginThrottle:
    MAX_FAILURES = 5
    BLOCK_MINUTES = 5

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    @staticmethod
    def _key(identity: str) -> str:
        return hashlib.sha256(identity.casefold().encode("utf-8")).hexdigest()

    def is_allowed(self, identity: str) -> bool:
        session = self.db.get_session()
        try:
            state = session.get(LoginThrottleState, self._key(identity))
            if state is None:
                return True
            blocked_until = cast(Optional[datetime], state.blocked_until)
            return blocked_until is None or blocked_until <= datetime.now()
        finally:
            session.close()

    def record_failure(self, identity: str) -> None:
        session = self.db.get_session()
        try:
            key = self._key(identity)
            now = datetime.now()
            dialect = session.get_bind().dialect.name
            insert_factory = {
                "postgresql": postgresql_insert,
                "sqlite": sqlite_insert,
            }.get(dialect)
            if insert_factory is None:
                raise RuntimeError(f"unsupported login throttle database: {dialect}")

            table = LoginThrottleState.__table__
            current_count = table.c.failure_count
            current_block = table.c.blocked_until
            expired = and_(current_block.is_not(None), current_block <= now)
            still_blocked = and_(current_block.is_not(None), current_block > now)
            next_count = case((expired, 1), else_=current_count + 1)
            next_block = case(
                (expired, None),
                (still_blocked, current_block),
                (
                    current_count + 1 >= self.MAX_FAILURES,
                    now + timedelta(minutes=self.BLOCK_MINUTES),
                ),
                else_=None,
            )
            statement = insert_factory(table).values(
                identity_hash=key,
                failure_count=1,
                blocked_until=None,
                updated_at=now,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[table.c.identity_hash],
                set_={
                    "failure_count": next_count,
                    "blocked_until": next_block,
                    "updated_at": now,
                },
            )
            session.execute(statement)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def reset(self, identity: str) -> None:
        session = self.db.get_session()
        try:
            state = session.get(LoginThrottleState, self._key(identity))
            if state is not None:
                session.delete(state)
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
