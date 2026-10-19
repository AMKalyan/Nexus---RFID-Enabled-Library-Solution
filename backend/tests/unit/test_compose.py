"""NFR 07: the shipped stack comes back by itself after a host or Docker restart (DEF-018)."""

from pathlib import Path

import yaml

COMPOSE = Path(__file__).resolve().parents[3] / "docker-compose.yml"


def test_nfr07_services_restart_after_a_host_restart():
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    for name in ("db", "api", "web"):
        assert services[name].get("restart") == "unless-stopped", name
