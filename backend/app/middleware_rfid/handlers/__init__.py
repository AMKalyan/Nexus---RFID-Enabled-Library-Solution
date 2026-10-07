"""Event handlers. Importing this package registers every handler with the dispatcher."""

from app.middleware_rfid.handlers import card, gate, inventory, tags_read  # noqa: F401
