"""Adapter contracts for everything outside Nexus (interface design §4).

Each external device or service is reached only through one of these protocols. The concrete class is
chosen from configuration by app.integrations.registry, so a vendor adapter can replace a mock without
touching the services that use it.
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from app.db.models import LegacyAccession, LegacyBorrower, LegacyCatalogue


@dataclass(frozen=True)
class OutboundMessage:
    channel: str
    recipient: str
    subject: str | None
    body: str


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    error: str | None = None


@dataclass(frozen=True)
class StaffIdentity:
    user_id: uuid.UUID
    role: str


class NotificationChannel(Protocol):
    def send(self, message: OutboundMessage) -> DeliveryResult: ...


class CameraProvider(Protocol):
    def snapshot(self, camera_code: str, context: dict) -> bytes: ...


class CredentialProvider(Protocol):
    def resolve(self, card_uid: str) -> StaffIdentity | None: ...


class LegacyIlmsConnector(Protocol):
    def iter_catalogue(self) -> Iterator[LegacyCatalogue]: ...
    def iter_accessions(self) -> Iterator[LegacyAccession]: ...
    def iter_borrowers(self) -> Iterator[LegacyBorrower]: ...
    def get_accession(self, acc_no: str) -> LegacyAccession | None: ...
