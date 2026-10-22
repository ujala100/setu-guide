"""Day 4: timeout, graceful shutdown and recovery. Docker required.

Owner: DevOps 1. See docs/recovery_test_notes.md for the scenario table.

These prove, on a real Linux container (a TestClient cannot):
- the image is configured for graceful shutdown and a bounded keep-alive
- an in-flight request completes on `docker stop` instead of being cut off
- an idle keep-alive connection is released by the server, not held forever

They skip themselves when the daemon is down or the image is missing:
    docker build -t setu-guide-api:day4 -f docker/Dockerfile .
Override with SETU_TEST_IMAGE / SETU_TEST_PORT / DOCKER_EXE.
"""
import functools
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request

import pytest

IMAGE = os.environ.get("SETU_TEST_IMAGE", "setu-guide-api:day3")
PORT = int(os.environ.get("SETU_TEST_PORT", "8011"))
CONTAINER = "setu-day4-recovery"
BASE_URL = f"http://127.0.0.1:{PORT}"
CHAT = "/v1/guide/chat"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LAUNCHER_DIR = os.path.join(REPO, "tests", "recovery")

CHAT_BODY = {"user_id": "recovery_user", "match_id": "recovery_m1",
             "stage": "connect", "intent": "next_steps"}


@functools.lru_cache(maxsize=1)
def _docker_exe():
    """Docker Desktop's own binary first: a stray shim can shadow PATH."""
    candidates = [os.environ.get("DOCKER_EXE"),
                  r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
                  shutil.which("docker")]
    for cand in dict.fromkeys(c for c in candidates if c):
        try:
            p = subprocess.run([cand, "version", "--format", "{{.Server.Version}}"],
                               capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if p.returncode == 0:
            return cand
    return None


@functools.lru_cache(maxsize=1)
def _image_exists():
    exe = _docker_exe()
    if not exe:
        return False
    try:
        return subprocess.run([exe, "image", "inspect", IMAGE],
                              capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(
    not _image_exists(),
    reason=f"docker unavailable or image {IMAGE!r} not built (see tests/README.md)",
)


def _docker(*args, timeout=180):
    exe = _docker_exe()
    assert exe, "docker executable not found"
    return subprocess.run([exe, *args], capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")


def _read(relpath):
    with open(os.path.join(REPO, relpath), encoding="utf-8") as fh:
        return fh.read()


def _shipped_shutdown_config():
    """(graceful_shutdown_seconds, keep_alive_seconds) from the image CMD."""
    dockerfile = _read(os.path.join("docker", "Dockerfile"))
    graceful = re.search(r"--timeout-graceful-shutdown\",\s*\"(\d+)\"", dockerfile)
    keepalive = re.search(r"--timeout-keep-alive\",\s*\"(\d+)\"", dockerfile)
    assert graceful and keepalive, (
        "docker/Dockerfile CMD must set --timeout-graceful-shutdown and "
        "--timeout-keep-alive")
    return int(graceful.group(1)), int(keepalive.group(1))


def _shipped_stop_grace():
    """The stop grace period in seconds, taken from docker-compose.yml."""
    match = re.search(r"stop_grace_period:\s*(\d+)s", _read("docker-compose.yml"))
    assert match, "docker-compose.yml must set stop_grace_period"
    return int(match.group(1))


def _wait_http(path, timeout=60):
    deadline = time.monotonic() + timeout
    last = "never attempted"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(BASE_URL + path, timeout=3) as resp:
                if resp.status == 200:
                    return 200
                last = f"HTTP {resp.status}"
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            last = type(exc).__name__
        time.sleep(0.3)
    raise AssertionError(f"{path} not answering 200 after {timeout}s (last: {last})")


def _post_chat(timeout=120, headers=None):
    """One chat call. Returns (status_or_label, body, seconds)."""
    data = json.dumps(CHAT_BODY).encode("utf-8")
    req = urllib.request.Request(BASE_URL + CHAT, data=data, method="POST",
                                 headers={"content-type": "application/json",
                                          **(headers or {})})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
            return resp.status, body, round(time.perf_counter() - started, 2)
    except urllib.error.HTTPError as exc:
        # keep the error body - the contract checks need the envelope
        raw = exc.read()
        try:
            body = json.loads(raw) if raw else {}
        except (ValueError, UnicodeDecodeError):
            body = {"raw": raw.decode("utf-8", "replace")[:200]}
        return exc.code, body, round(time.perf_counter() - started, 2)
    except (urllib.error.URLError, ConnectionError, OSError) as exc:
        return f"DROPPED({type(exc).__name__})", {}, round(time.perf_counter() - started, 2)


def _start_container(sleep):
    """Start the image with the slow-orchestrator launcher mounted read-only.

    The launcher's graceful/keep-alive values come from the *shipped* config
    (Dockerfile CMD / compose), so a regression in those files fails the
    behaviour tests too - not just the text guards.
    """
    graceful, keepalive = _shipped_shutdown_config()
    _docker("rm", "-f", CONTAINER)
    cmd = ["run", "-d", "--name", CONTAINER, "-p", f"{PORT}:8000",
           "--entrypoint", "python",
           "-e", "USE_MOCK=false",
           "-e", "LLM_API_KEY=recovery-dummy-key",
           "-e", "LLM_TIMEOUT_SECONDS=90",
           "-e", "CACHE_ENABLED=false",
           "-e", "LOG_LEVEL=warning",
           "-e", "RATE_LIMIT_PER_USER=100000/minute",
           "-e", "RATE_LIMIT_PER_IP=100000/minute",
           "-e", f"PROBE_SLEEP={sleep}",
           "-e", f"GRACEFUL={graceful}",
           "-e", f"KEEPALIVE={keepalive}",
           "-e", "PYTHONPATH=/opt/patch:/app",
           "-v", f"{LAUNCHER_DIR}:/opt/patch:ro",
           IMAGE, "/opt/patch/slow_orchestrator.py"]
    p = _docker(*cmd)
    assert p.returncode == 0, f"could not start container: {p.stderr}"
    _wait_http("/health", 90)


def _graceful_stop():
    """`docker stop` with the stop grace period the compose file ships."""
    return _docker("stop", "-t", str(_shipped_stop_grace()), CONTAINER, timeout=180)


@pytest.fixture
def cleanup_container():
    yield
    _docker("rm", "-f", CONTAINER)


# --------------------------------------------------------------- config guards

def test_image_cmd_enables_graceful_shutdown_and_keepalive():
    """The shipped CMD must set both flags; without them SIGTERM cuts requests."""
    dockerfile = _read(os.path.join("docker", "Dockerfile"))
    assert "--timeout-graceful-shutdown" in dockerfile
    assert "--timeout-keep-alive" in dockerfile
    graceful, keepalive = _shipped_shutdown_config()
    assert graceful >= 15, "graceful shutdown must cover the whole request budget"
    assert 0 < keepalive <= 30, "keep-alive should release idle connections quickly"


def test_compose_stop_grace_period_covers_graceful_shutdown():
    """`stop_grace_period` must be >= the uvicorn graceful window, or Docker
    SIGKILLs the container before uvicorn finishes draining."""
    stop_grace = _shipped_stop_grace()
    graceful, _ = _shipped_shutdown_config()
    assert stop_grace > graceful, (
        f"stop_grace_period ({stop_grace}s) must exceed uvicorn graceful "
        f"shutdown ({graceful}s)")


# ----------------------------------------------------------- behaviour probes

def test_inflight_request_survives_graceful_stop(cleanup_container):
    """A request whose work outlasts a naive stop window must still get its
    reply (200), and the container must exit cleanly (0), not via SIGKILL (137)."""
    _start_container(sleep=8)
    result = {}

    def hit():
        result["r"] = _post_chat()

    t = threading.Thread(target=hit)
    t.start()
    time.sleep(1.5)  # request is in-flight
    stop = _graceful_stop()
    assert stop.returncode == 0, stop.stderr
    t.join(timeout=90)

    status, body, seconds = result["r"]
    assert status == 200, f"in-flight request was not answered cleanly: {status}"
    assert body.get("fallback_used") is False, "reply should be the real one, not a fallback"
    assert seconds >= 6, f"request finished too early to be the in-flight one: {seconds}s"
    code = _docker("inspect", "-f", "{{.State.ExitCode}}", CONTAINER, timeout=30)
    assert code.stdout.strip() == "0", f"container exit code {code.stdout.strip()} (137 = SIGKILL)"


def test_concurrent_inflight_requests_survive_graceful_stop(cleanup_container):
    """Several in-flight requests at once all complete on a graceful stop."""
    _start_container(sleep=6)
    results = {}
    threads = [threading.Thread(target=lambda i=i: results.__setitem__(i, _post_chat()))
               for i in range(3)]
    for t in threads:
        t.start()
    time.sleep(1.5)
    p = _graceful_stop()
    assert p.returncode == 0, p.stderr
    for t in threads:
        t.join(timeout=90)

    assert sorted(results) == [0, 1, 2], "not every request returned"
    for i, (status, _body, _seconds) in results.items():
        assert status == 200, f"request {i} not answered cleanly: {status}"
    code = _docker("inspect", "-f", "{{.State.ExitCode}}", CONTAINER, timeout=30)
    assert code.stdout.strip() == "0", f"container exit code {code.stdout.strip()}, expected 0"


def test_idle_keepalive_connection_is_released(cleanup_container):
    """The server closes an idle keep-alive connection near --timeout-keep-alive
    (5s) so clients cannot pin worker slots open indefinitely."""
    _start_container(sleep=0)
    sock = socket.create_connection(("127.0.0.1", PORT), timeout=15)
    try:
        payload = json.dumps(CHAT_BODY).encode()
        raw = (f"POST {CHAT} HTTP/1.1\r\nHost: 127.0.0.1:{PORT}\r\n"
               f"content-type: application/json\r\nContent-Length: {len(payload)}\r\n"
               f"Connection: keep-alive\r\n\r\n").encode() + payload
        sock.sendall(raw)
        sock.settimeout(15)
        first = sock.recv(65536)
        assert b"HTTP/1.1 200" in first, "first response missing"

        # Now go idle: the server should close the socket within the keep-alive
        # window plus a small margin. A read of b"" means the peer closed it.
        deadline = time.monotonic() + 12
        closed = False
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            if chunk == b"":
                closed = True
                break
        assert closed, "idle keep-alive connection was not released by the server"
    finally:
        sock.close()


def test_restart_mid_load_recovers_without_manual_step(cleanup_container):
    """`docker restart` under continuous traffic: the service comes back on its
    own and the client recovers; no request needs a manual retry."""
    _start_container(sleep=0)
    stop_flag = threading.Event()
    log = []

    def load():
        while not stop_flag.is_set():
            log.append(_post_chat(timeout=5)[0])
            time.sleep(0.05)

    threads = [threading.Thread(target=load, daemon=True) for _ in range(3)]
    for t in threads:
        t.start()
    try:
        time.sleep(2)
        assert _docker("restart", CONTAINER, timeout=120).returncode == 0
        _wait_http("/health", 90)
        time.sleep(2)
    finally:
        stop_flag.set()
        for t in threads:
            t.join(timeout=10)

    tail = log[-40:]
    assert tail.count(200) > 10, f"client did not recover after restart: {tail[-10:]}"


def test_slow_request_within_budget_returns_real_reply(cleanup_container):
    """Sanity: a request inside the budget returns the real reply, not a
    fallback - so the timeout tests above are not just observing the fallback."""
    _start_container(sleep=3)
    status, body, seconds = _post_chat()
    assert status == 200
    assert body.get("fallback_used") is False
    assert 2.5 <= seconds <= 6, f"unexpected latency for a 3s request: {seconds}s"


def test_container_requires_the_api_key_when_auth_is_on(cleanup_container):
    """The key check has to work in the real container, not only through the
    TestClient: the header is read from the environment, the key never
    reaches a response or a log line, and /health stays reachable without
    one (the HEALTHCHECK needs it)."""
    key = "day4-container-key-9f2c"
    _docker("rm", "-f", CONTAINER)
    p = _docker("run", "-d", "--name", CONTAINER, "-p", f"{PORT}:8000",
                "-e", "USE_MOCK=true",
                "-e", "AUTH_METHOD=api_key",
                "-e", f"API_KEY={key}",
                "-e", "RATE_LIMIT_PER_USER=100000/minute",
                "-e", "RATE_LIMIT_PER_IP=100000/minute", IMAGE)
    assert p.returncode == 0, p.stderr
    _wait_http("/health", 90)

    # no key -> 401 in the standard envelope
    r = _post_chat()
    assert r[0] == 401, f"expected 401 without the key, got {r[0]}"
    assert r[1].get("error", {}).get("code") == "unauthorized", r[1]
    assert key not in json.dumps(r[1]), "the key leaked into the response"

    # wrong key -> 401 as well
    r = _post_chat(headers={"X-API-Key": "wrong-key"})
    assert r[0] == 401, f"expected 401 with a wrong key, got {r[0]}"

    # the right key -> a normal answer
    r = _post_chat(headers={"X-API-Key": key})
    assert r[0] == 200, f"expected 200 with the right key, got {r[0]}: {r[1]}"

    # /health needs no credential (the container HEALTHCHECK calls it that way)
    assert _wait_http("/health", 10) == 200

    logs = _docker("logs", CONTAINER, timeout=60)
    text = (logs.stdout or "") + (logs.stderr or "")
    assert key not in text, "the API key leaked into the container logs"
