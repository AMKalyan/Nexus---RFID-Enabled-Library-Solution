"""Event handlers. Importing this package registers every handler with the dispatcher."""

from app.middleware_rfid.handlers import inventory, tags_read  # noqa: F401
