"""Exercise the shared demo routes with a real Caddy gateway, without the app/DB.

Run explicitly with Docker available::

    RUN_DEMO_GATEWAY_TESTS=1 python -m pytest tests/deployment --confcutdir=tests/deployment -q

The fixture uses a local CA only; public IP certificate issuance is checked on AWS.
"""

import os
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

IMAGE = "caddy:2.11.7-alpine"
ORIGIN = "https://127.0.0.1"
AUTH = ("admin", "gateway-test-password")
ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DEMO_GATEWAY_TESTS") != "1", reason="Opt-in real Docker gateway checks"
)


def _docker(*args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["docker", *args],
        input=input_text,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return result.stdout.strip()


@pytest.fixture(scope="module")
def gateway(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Start isolated TLS Caddy with the production route file and an echo origin."""
    routes = (ROOT / "deploy" / "Caddyfile.demo-routes").read_text(encoding="utf-8")
    directory = tmp_path_factory.mktemp("demo-gateway")
    (directory / "routes").write_text(routes, encoding="utf-8")
    (directory / "index.html").write_text("demo frontend", encoding="utf-8")
    password_hash = _docker("run", "--rm", IMAGE, "caddy", "hash-password", "--plaintext", AUTH[1])
    # Parse the real public-IP issuer configuration without requesting a certificate.
    _docker(
        "run",
        "--rm",
        "--mount",
        f"type=bind,source={ROOT / 'deploy' / 'Caddyfile.demo'},target=/etc/caddy/Caddyfile,readonly",
        "--mount",
        f"type=bind,source={ROOT / 'deploy' / 'Caddyfile.demo-routes'},target=/etc/caddy/demo-routes,readonly",
        "-e",
        "DEMO_PUBLIC_IP=203.0.113.10",
        "-e",
        "ACME_EMAIL=demo@example.com",
        "-e",
        f"DEMO_PASSWORD_HASH={password_hash}",
        "-e",
        f"DEMO_USERNAME={AUTH[0]}",
        IMAGE,
        "caddy",
        "adapt",
        "--config",
        "/etc/caddy/Caddyfile",
        "--adapter",
        "caddyfile",
    )
    config = """{
    admin off
    default_sni 127.0.0.1
}
https://127.0.0.1 {
    tls internal
    import /fixtures/routes
}
http://:8010 {
    respond "{http.request.method}|{http.request.header.Authorization}" 200
}
"""
    (directory / "Caddyfile").write_text(config, encoding="utf-8")
    name = f"unisensory-gateway-test-{uuid.uuid4().hex[:10]}"
    try:
        _docker(
            "run",
            "-d",
            "--name",
            name,
            "-p",
            "127.0.0.1::443",
            "--add-host",
            "api:127.0.0.1",
            "--mount",
            f"type=bind,source={directory},target=/fixtures,readonly",
            "-e",
            "DEMO_PUBLIC_IP=127.0.0.1",
            "-e",
            f"DEMO_PASSWORD_HASH={password_hash}",
            "-e",
            f"DEMO_USERNAME={AUTH[0]}",
            "-e",
            "DEMO_STATIC_ROOT=/fixtures",
            IMAGE,
            "caddy",
            "run",
            "--config",
            "/fixtures/Caddyfile",
            "--adapter",
            "caddyfile",
        )
        port = _docker("port", name, "443/tcp").rsplit(":", 1)[1]
        url = f"https://127.0.0.1:{port}"
        with httpx.Client(verify=False, trust_env=False, timeout=2) as client:
            for _ in range(60):
                try:
                    if client.get(url).status_code == 401:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.25)
            else:
                pytest.fail("Local demo gateway did not become ready")
        yield url
    finally:
        subprocess.run(["docker", "rm", "-fv", name], check=False, capture_output=True, timeout=30)


@pytest.mark.parametrize("path", ["/", "/paper", "/v1/auth/me", "/v1/jobs", "/health"])
def test_all_surfaces_require_password(gateway: str, path: str) -> None:
    with httpx.Client(verify=False, trust_env=False) as client:
        response = client.get(gateway + path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic")


def test_wrong_password_is_rejected(gateway: str) -> None:
    with httpx.Client(verify=False, trust_env=False) as client:
        response = client.get(gateway, auth=("admin", "wrong"))
    assert response.status_code == 401


def test_spa_deep_link_and_api_are_separate(gateway: str) -> None:
    with httpx.Client(verify=False, trust_env=False, auth=AUTH) as client:
        page = client.get(gateway + "/paper")
        api = client.get(gateway + "/v1/auth/me")
    assert page.status_code == 200
    assert page.text == "demo frontend"
    assert api.text == "GET|", "The API must not receive the shared Basic credential"
    assert page.headers["cache-control"] == "no-store"
    assert api.headers["content-security-policy"] == "frame-ancestors 'self'"


@pytest.mark.parametrize("origin", [None, "https://unrelated.example", "null"])
def test_mutations_require_exact_origin(gateway: str, origin: str | None) -> None:
    headers = {"Origin": origin} if origin is not None else {}
    with httpx.Client(verify=False, trust_env=False, auth=AUTH) as client:
        response = client.post(gateway + "/v1/echo", headers=headers, content=b"test")
    assert response.status_code == 403


def test_same_origin_upload_reaches_api_without_basic_header(gateway: str) -> None:
    with httpx.Client(verify=False, trust_env=False, auth=AUTH) as client:
        response = client.post(
            gateway + "/v1/echo",
            headers={"Origin": ORIGIN},
            files={"file": ("demo.pdf", b"%PDF-demo", "application/pdf")},
        )
    assert response.status_code == 200
    assert response.text == "POST|"


def test_oauth_routes_are_disabled_for_shared_demo(gateway: str) -> None:
    with httpx.Client(verify=False, trust_env=False, auth=AUTH) as client:
        response = client.get(gateway + "/v1/auth/login/google")
    assert response.status_code == 404


def test_reviewer_seed_is_repeatable_and_refuses_conflicting_identity() -> None:
    """Execute the role seed in disposable PostgreSQL, never the app database."""
    name = f"unisensory-reviewer-test-{uuid.uuid4().hex[:10]}"
    script = (ROOT / "deploy" / "demo-reviewer.sql").read_text(encoding="utf-8")
    try:
        _docker(
            "run", "-d", "--name", name, "-e", "POSTGRES_PASSWORD=test-only", "postgres:17-alpine"
        )
        for _ in range(60):
            try:
                _docker("exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres")
                break
            except subprocess.CalledProcessError:
                time.sleep(0.25)
        else:
            pytest.fail("Disposable PostgreSQL did not become ready")
        command = ("exec", "-i", name, "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-At")
        _docker(
            *command,
            input_text="""
            CREATE TABLE tenants (id text PRIMARY KEY);
            INSERT INTO tenants VALUES ('default');
            CREATE TABLE users (
                id text PRIMARY KEY, tenant_id text REFERENCES tenants(id),
                email text UNIQUE NOT NULL, name text,
                oauth_provider text NOT NULL, oauth_subject text NOT NULL,
                role text NOT NULL, created_at timestamptz NOT NULL,
                UNIQUE(oauth_provider, oauth_subject)
            );
        """,
        )
        _docker(*command, input_text=script)
        _docker(*command, input_text=script)
        assert _docker(*command, input_text="SELECT id||'|'||tenant_id||'|'||role FROM users;") == (
            "dev-user|default|accountant"
        )
        _docker(*command, input_text="UPDATE users SET oauth_provider='existing-owner';")
        with pytest.raises(subprocess.CalledProcessError):
            _docker(*command, input_text=script)
        assert _docker(*command, input_text="SELECT oauth_provider FROM users;") == "existing-owner"
    finally:
        subprocess.run(["docker", "rm", "-fv", name], check=False, capture_output=True, timeout=30)
