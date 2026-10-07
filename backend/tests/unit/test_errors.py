from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import AppError, install_error_handlers


def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("SELECT * FROM secret_table at /srv/app.py")

    @app.get("/apperr")
    def apperr():
        raise AppError("MEMBER_BLOCKED", "Member is blocked", 409)

    return app


def test_nfr02_unhandled_error_is_sanitised():
    r = TestClient(_app(), raise_server_exceptions=False).get("/boom")
    assert r.status_code == 500
    assert r.json() == {"error": "Internal Server Error", "code": "ERR_INTERNAL"}
    assert "secret_table" not in r.text


def test_app_error_shape():
    r = TestClient(_app()).get("/apperr")
    assert r.status_code == 409
    assert r.json() == {"error": "Member is blocked", "code": "MEMBER_BLOCKED"}


def test_validation_error_does_not_echo_input():
    app = _app()

    @app.get("/n")
    def n(x: int):
        return x

    r = TestClient(app).get("/n", params={"x": "<script>"})
    assert r.status_code == 422
    assert r.json()["code"] == "ERR_VALIDATION"
    assert "<script>" not in r.text
