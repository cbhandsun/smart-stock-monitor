"""Durable notification idempotency and delivery history."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.exc import IntegrityError

from database.models import DatabaseManager, NotificationDelivery, get_db


class DeliveryLedger:
    """Claim one delivery event and record only non-sensitive delivery metadata."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or get_db()

    def claim(self, event_key: str, alert_id: str, user_id: str) -> bool:
        if not all(
            isinstance(value, str) and value for value in (event_key, alert_id, user_id)
        ):
            raise ValueError("delivery identifiers are required")
        if len(event_key) > 120 or len(alert_id) > 50 or len(user_id) > 50:
            raise ValueError("delivery identifier is too long")

        session = self.db.get_session()
        try:
            delivery = session.get(NotificationDelivery, event_key)
            now = datetime.now()
            if delivery is None:
                session.add(
                    NotificationDelivery(
                        event_key=event_key,
                        alert_id=alert_id,
                        user_id=user_id,
                        status="pending",
                        attempts=1,
                        created_at=now,
                        updated_at=now,
                    )
                )
                session.commit()
                return True
            if delivery.user_id != user_id or delivery.alert_id != alert_id:
                raise PermissionError("delivery ownership mismatch")
            if delivery.status == "sent":
                return False
            if delivery.status == "pending" and delivery.updated_at > now - timedelta(
                minutes=5
            ):
                return False
            delivery.status = "pending"
            delivery.attempts = (delivery.attempts or 0) + 1
            delivery.updated_at = now
            delivery.error_code = None
            session.commit()
            return True
        except IntegrityError:
            session.rollback()
            return False
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def mark_sent(self, event_key: str, channel: str) -> None:
        self._finish(event_key, "sent", channel=channel)

    def mark_failed(self, event_key: str, error_code: str = "delivery_failed") -> None:
        self._finish(event_key, "failed", error_code=error_code)

    def _finish(
        self,
        event_key: str,
        status: str,
        *,
        channel: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> None:
        session = self.db.get_session()
        try:
            delivery = session.get(NotificationDelivery, event_key)
            if delivery is None:
                raise LookupError("delivery claim not found")
            now = datetime.now()
            delivery.status = status
            delivery.channel = channel
            delivery.error_code = error_code
            delivery.updated_at = now
            delivery.sent_at = now if status == "sent" else None
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_for_user(self, user_id: str, limit: int = 50) -> list[dict[str, object]]:
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("user_id is required")
        limit = max(1, min(int(limit), 200))
        session = self.db.get_session()
        try:
            rows = (
                session.query(NotificationDelivery)
                .filter_by(user_id=user_id)
                .order_by(NotificationDelivery.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "alert_id": row.alert_id,
                    "status": row.status,
                    "channel": row.channel or "-",
                    "attempts": row.attempts,
                    "created_at": row.created_at,
                    "sent_at": row.sent_at,
                }
                for row in rows
            ]
        finally:
            session.close()
