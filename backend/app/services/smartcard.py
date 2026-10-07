"""Smart-card login handshake (interface design §2.4).

1. The login page opens a challenge for a reader and waits.
2. The reader reports a CardTapped event; the credential provider resolves the card and the result is bound
   to the newest open challenge for that reader.
3. The page completes the challenge and receives tokens. Challenges are single-use and expire after 60 s.
"""

import secrets
import threading
import time
from dataclasses import dataclass, field

from app.core.errors import AppError
from app.integrations.base import StaffIdentity

TTL_S = 60.0


@dataclass
class Challenge:
    reader_code: str
    created: float = field(default_factory=time.monotonic)
    tapped: bool = False
    identity: StaffIdentity | None = None


class SmartcardChallenges:
    def __init__(self) -> None:
        self._challenges: dict[str, Challenge] = {}
        self._lock = threading.Lock()

    def _expire(self) -> None:
        now = time.monotonic()
        for cid in [c for c, ch in self._challenges.items() if now - ch.created > TTL_S]:
            del self._challenges[cid]

    def open(self, reader_code: str) -> str:
        with self._lock:
            self._expire()
            cid = secrets.token_urlsafe(16)
            self._challenges[cid] = Challenge(reader_code)
            return cid

    def bind(self, reader_code: str, identity: StaffIdentity | None) -> str | None:
        """Attach a tap result to the newest untapped challenge for this reader."""
        with self._lock:
            self._expire()
            waiting = [
                (cid, ch)
                for cid, ch in self._challenges.items()
                if ch.reader_code == reader_code and not ch.tapped
            ]
            if not waiting:
                return None
            cid, challenge = max(waiting, key=lambda pair: pair[1].created)
            challenge.tapped, challenge.identity = True, identity
            return cid

    def exists(self, reader_code: str, challenge_id: str) -> bool:
        with self._lock:
            self._expire()
            ch = self._challenges.get(challenge_id)
            return ch is not None and ch.reader_code == reader_code

    def consume(self, reader_code: str, challenge_id: str) -> StaffIdentity:
        with self._lock:
            self._expire()
            challenge = self._challenges.get(challenge_id)
            if challenge is None or challenge.reader_code != reader_code:
                raise AppError("CARD_CHALLENGE_INVALID", "Card sign-in expired; please try again", 401)
            if not challenge.tapped:
                raise AppError("CARD_NOT_TAPPED", "Waiting for a card tap", 409)
            del self._challenges[challenge_id]
            if challenge.identity is None:
                raise AppError("CARD_UNKNOWN", "This card is not registered to an active staff member", 401)
            return challenge.identity


challenges = SmartcardChallenges()
