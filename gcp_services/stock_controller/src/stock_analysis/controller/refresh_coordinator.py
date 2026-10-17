from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from google.cloud import firestore

from stock_analysis.market_worker.schedule import ScheduleBucket, schedule_bucket


@dataclass(frozen=True)
class RefreshClaim:
    token: str
    bucket: ScheduleBucket


class FirestoreRefreshCoordinator:
    def __init__(
        self,
        *,
        client: firestore.Client | None = None,
        document_path: str = "stock_analysis_runtime/market_refresh",
        lease_seconds: int = 180,
    ) -> None:
        self._client = client or firestore.Client()
        self._document = self._client.document(document_path)
        self._lease_seconds = lease_seconds

    def claim(self, now: datetime | None = None) -> RefreshClaim | None:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        bucket = schedule_bucket(current)
        token = uuid4().hex
        transaction = self._client.transaction()

        @firestore.transactional
        def claim_in_transaction(transaction: Any) -> bool:
            snapshot = self._document.get(transaction=transaction)
            state = snapshot.to_dict() if snapshot.exists else {}
            if state.get("last_successful_bucket") == bucket.key:
                return False

            lease_expires_at = state.get("lease_expires_at")
            if lease_expires_at is not None:
                lease_expires_at = lease_expires_at.astimezone(timezone.utc)
            if lease_expires_at is not None and lease_expires_at > current:
                return False

            transaction.set(
                self._document,
                {
                    "schema_version": 1,
                    "claim_token": token,
                    "claimed_bucket": bucket.key,
                    "claimed_at": current,
                    "lease_expires_at": current + timedelta(seconds=self._lease_seconds),
                    "session": bucket.session.name,
                    "interval_minutes": bucket.session.target_interval_minutes,
                },
                merge=True,
            )
            return True

        if not claim_in_transaction(transaction):
            return None
        return RefreshClaim(token=token, bucket=bucket)

    def complete(
        self,
        claim: RefreshClaim,
        *,
        completed_at: datetime,
        duration_seconds: float,
        ticker_count: int,
    ) -> None:
        transaction = self._client.transaction()

        @firestore.transactional
        def complete_in_transaction(transaction: Any) -> None:
            snapshot = self._document.get(transaction=transaction)
            state = snapshot.to_dict() if snapshot.exists else {}
            if state.get("claim_token") != claim.token:
                raise RuntimeError("Refresh lease is no longer owned by this request")
            transaction.update(
                self._document,
                {
                    "last_successful_bucket": claim.bucket.key,
                    "last_successful_at": completed_at.astimezone(timezone.utc),
                    "last_duration_seconds": round(duration_seconds, 3),
                    "last_ticker_count": ticker_count,
                    "last_error": None,
                    "claim_token": firestore.DELETE_FIELD,
                    "claimed_bucket": firestore.DELETE_FIELD,
                    "claimed_at": firestore.DELETE_FIELD,
                    "lease_expires_at": firestore.DELETE_FIELD,
                },
            )

        complete_in_transaction(transaction)

    def fail(
        self,
        claim: RefreshClaim,
        *,
        failed_at: datetime,
        error: BaseException,
    ) -> None:
        transaction = self._client.transaction()

        @firestore.transactional
        def fail_in_transaction(transaction: Any) -> None:
            snapshot = self._document.get(transaction=transaction)
            state = snapshot.to_dict() if snapshot.exists else {}
            if state.get("claim_token") != claim.token:
                return
            transaction.update(
                self._document,
                {
                    "last_failed_bucket": claim.bucket.key,
                    "last_failed_at": failed_at.astimezone(timezone.utc),
                    "last_error": f"{type(error).__name__}: {error}",
                    "claim_token": firestore.DELETE_FIELD,
                    "claimed_bucket": firestore.DELETE_FIELD,
                    "claimed_at": firestore.DELETE_FIELD,
                    "lease_expires_at": firestore.DELETE_FIELD,
                },
            )

        fail_in_transaction(transaction)
