"""Message templates. Values are supplied by the service; templates hold no personal data themselves."""

TEMPLATES: dict[str, tuple[str, str]] = {
    "gate_alert": (
        "Security gate alarm at {gate}",
        "An item left through {gate} at {time} without being issued.\n"
        "Accession number: {accession_no}\nTitle: {title}\n"
        "A camera snapshot is attached to the gate event in Nexus.",
    ),
    "overdue_notice": (
        "Overdue item returned: {title}",
        'Your loan of "{title}" ({accession_no}) was returned {days} day(s) late.\n'
        "A fine of {amount} has been added to your account.",
    ),
    "due_reminder": (
        "Reminder: {title} is due on {due}",
        'Please return or renew "{title}" by {due}.',
    ),
}


def render(template: str, context: dict) -> tuple[str, str]:
    subject, body = TEMPLATES[template]
    safe = {k: str(v) for k, v in context.items()}
    return subject.format_map(_Default(safe)), body.format_map(_Default(safe))


class _Default(dict):
    def __missing__(self, key: str) -> str:
        return "—"
