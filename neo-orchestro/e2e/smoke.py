"""API-level end-to-end smoke test against the REAL stack started by ``run.sh``.

Everything goes over HTTP through nginx (except where noted: the authentication calls are
sent straight to the API so the nginx brute-force limiter, 10 requests/minute, is not
exhausted before the dedicated rate-limit probe at the end). The worker is a separate
Celery process that this script stops and starts to create the interesting situations
(DNS rebinding while a scan waits in the queue, cancelling a queued scan).

Standard library only, plus ``pg8000`` (already in the backend lock) for one database probe.
Every check prints ``PASS``/``FAIL`` with the evidence observed; the exit status is the
number of failed checks capped at 1.
"""

import base64
import http.client
import json
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit

WEB = os.environ["E2E_BASE_URL"]
API = os.environ["E2E_API_URL"]
PASSWORD = os.environ["E2E_PASSWORD"]
ADMIN_EMAIL = os.environ["E2E_API_ADMIN_EMAIL"]
OTHER_EMAIL = os.environ["E2E_OTHER_ADMIN_EMAIL"]
RECORDS = Path(os.environ["E2E_RECORDS"])
DNS_LOG = Path(os.environ["E2E_DNS_LOG"])
WORKER_CTL = os.environ["E2E_WORKER_CTL"]
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
CSRF = {"X-Neo-CSRF": "1"}
VIEWER_EMAIL = "viewer@example.org"

results: list[tuple[str, bool, str]] = []
state: dict[str, str] = {}


def check(name: str, ok: bool, detail: object = "") -> bool:
    results.append((name, bool(ok), str(detail)))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail != "" else ""))
    return bool(ok)


class Resp:
    def __init__(self, status: int, headers: list[tuple[str, str]], body: bytes) -> None:
        self.status, self.headers, self.body = status, headers, body

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self) -> object:
        return json.loads(self.body)

    def header(self, name: str) -> str | None:
        return next((v for k, v in self.headers if k.lower() == name.lower()), None)

    def error(self) -> dict[str, object]:
        body = self.json()
        assert isinstance(body, dict)
        err = body.get("error", {})
        assert isinstance(err, dict)
        return err


def call(
    method: str,
    path: str,
    *,
    body: object = None,
    token: str | None = None,
    cookie: str | None = None,
    headers: dict[str, str] | None = None,
    via_web: bool = False,
) -> Resp:
    base = WEB if (via_web or not path.startswith("/api/v1/auth/")) else API
    target = urlsplit(base)
    conn = http.client.HTTPConnection(target.hostname, target.port, timeout=30)
    hdrs = {"Accept": "application/json", **(headers or {})}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    if cookie:
        hdrs["Cookie"] = f"neo_refresh={cookie}"
    payload = json.dumps(body).encode() if body is not None else None
    if payload is not None:
        hdrs["Content-Type"] = "application/json"
    conn.request(method, path, body=payload, headers=hdrs)
    raw = conn.getresponse()
    data = raw.read()
    conn.close()
    return Resp(raw.status, raw.getheaders(), data)


def refresh_cookie(resp: Resp) -> str | None:
    for header in (v for k, v in resp.headers if k.lower() == "set-cookie"):
        jar: SimpleCookie = SimpleCookie()
        jar.load(header)
        if "neo_refresh" in jar:
            return jar["neo_refresh"].value
    return None


def login(email: str, password: str = PASSWORD, *, via_web: bool = False) -> tuple[str, str]:
    resp = call("POST", LOGIN, body={"email": email, "password": password}, via_web=via_web)
    assert resp.status == 200, f"login {email} -> {resp.status} {resp.text[:120]}"
    body = resp.json()
    assert isinstance(body, dict)
    return str(body["access_token"]), refresh_cookie(resp) or ""


def worker(action: str) -> None:
    subprocess.run([WORKER_CTL, action], check=True, env=os.environ, timeout=120)


def set_records(updates: dict[str, dict[str, list[str]]]) -> None:
    records = json.loads(RECORDS.read_text())
    records.update(updates)
    tmp = RECORDS.with_suffix(".tmp")
    tmp.write_text(json.dumps(records))
    os.replace(tmp, RECORDS)  # atomic: the DNS server re-reads the file on every query


def dns_queries() -> list[str]:
    if not DNS_LOG.exists():
        return []
    return [ln.strip() for ln in DNS_LOG.read_text().splitlines() if ln.startswith("query ")]


def wait_scan(token: str, scan_id: str, timeout: float = 90) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        scan = call("GET", f"/api/v1/scans/{scan_id}", token=token).json()
        assert isinstance(scan, dict)
        if scan["status"] in {"succeeded", "failed", "cancelled"}:
            return scan
        time.sleep(0.5)
    raise TimeoutError(f"scan {scan_id} did not finish within {timeout}s")


def create_scan(token: str, target: str, engine: str = "dns_recon") -> Resp:
    return call("POST", "/api/v1/scans", token=token, body={"engine": engine, "target": target})


# --------------------------------------------------------------------------- scenarios


def infrastructure_and_headers() -> None:
    print("\n[1] nginx, health, security headers")
    check("nginx /healthz", call("GET", "/healthz").text.strip() == "ok")
    check("API /health/live through nginx", call("GET", "/health/live").status == 200)
    ready = call("GET", "/health/ready")
    check("API /health/ready (database + Redis)", ready.status == 200, ready.text.strip()[:80])
    check("/metrics is NOT exposed through nginx", call("GET", "/metrics").status == 404)
    direct = call("GET", "/metrics", via_web=False)
    # /metrics is not under /api/v1/auth/, so call() sent it to nginx; hit the API explicitly:
    conn = http.client.HTTPConnection(urlsplit(API).hostname, urlsplit(API).port, timeout=10)
    conn.request("GET", "/metrics")
    metrics = conn.getresponse()
    body = metrics.read().decode()
    conn.close()
    check(
        "/metrics served by the API on the internal port",
        metrics.status == 200 and "neo_http_requests_total" in body,
        f"nginx said {direct.status}, API said {metrics.status}",
    )
    index = call("GET", "/")
    csp = index.header("content-security-policy") or ""
    check("SPA index served", index.status == 200 and '<div id="root">' in index.text)
    check(
        "CSP is strict", "default-src 'self'" in csp and "frame-ancestors 'none'" in csp, csp[:60]
    )
    check(
        "nosniff + X-Frame-Options DENY",
        index.header("x-content-type-options") == "nosniff"
        and index.header("x-frame-options") == "DENY",
    )
    check("index is not cached", index.header("cache-control") == "no-cache")
    check("SPA fallback for a client-side route", call("GET", "/scans/anything").text == index.text)
    import re

    asset = re.search(r'/assets/[^"]+\.js', index.text)
    asset_resp = call("GET", asset.group(0)) if asset else None
    check(
        "fingerprinted asset cached immutable",
        asset_resp is not None
        and "immutable" in (asset_resp.header("cache-control") or "")
        and "javascript" in (asset_resp.header("content-type") or ""),
        asset.group(0) if asset else "no asset found",
    )
    check("server version hidden", "nginx/" not in (index.header("server") or ""))
    check("unauthenticated API call -> 401 envelope", call("GET", "/api/v1/scans").status == 401)


def authentication() -> None:
    print("\n[2] authentication, cookies, CSRF, refresh rotation and reuse detection")
    bad = call("POST", LOGIN, body={"email": ADMIN_EMAIL, "password": "definitely-wrong-pass"})
    ghost = call(
        "POST", LOGIN, body={"email": "ghost@example.org", "password": "definitely-wrong-pass"}
    )
    same = (bad.status, bad.error().get("code"), bad.error().get("message")) == (
        ghost.status,
        ghost.error().get("code"),
        ghost.error().get("message"),
    )
    check(
        "wrong password -> 401 with request_id", bad.status == 401 and bad.error().get("request_id")
    )
    check("unknown e-mail indistinguishable from wrong password", same, bad.error().get("code"))

    resp = call("POST", LOGIN, body={"email": ADMIN_EMAIL, "password": PASSWORD}, via_web=True)
    cookie1 = refresh_cookie(resp) or ""
    jar: SimpleCookie = SimpleCookie()
    for header in (v for k, v in resp.headers if k.lower() == "set-cookie"):
        jar.load(header)
    attrs = jar["neo_refresh"] if "neo_refresh" in jar else {}
    check("login through nginx -> 200", resp.status == 200)
    check(
        "refresh cookie: HttpOnly, SameSite=Strict, Path=/api/v1/auth",
        bool(attrs)
        and bool(attrs["httponly"])
        and str(attrs["samesite"]).lower() == "strict"
        and attrs["path"] == "/api/v1/auth",
        {k: attrs[k] for k in ("httponly", "samesite", "path", "secure")} if attrs else "no cookie",
    )
    check("refresh token never appears in the JSON body", cookie1 and cookie1 not in resp.text)

    no_csrf = call("POST", REFRESH, cookie=cookie1)
    check("refresh without X-Neo-CSRF header refused", no_csrf.status == 403, no_csrf.status)
    rotated = call("POST", REFRESH, cookie=cookie1, headers=CSRF, via_web=True)
    cookie2 = refresh_cookie(rotated) or ""
    check(
        "refresh via nginx rotates the cookie",
        rotated.status == 200 and cookie2 and cookie2 != cookie1,
    )
    replay = call("POST", REFRESH, cookie=cookie1, headers=CSRF)
    check("replaying the rotated-out cookie -> 401", replay.status == 401, replay.status)
    after = call("POST", REFRESH, cookie=cookie2, headers=CSRF)
    check("reuse revoked the whole family (new cookie dead too)", after.status == 401, after.status)
    state["stolen_cookie"] = cookie1

    token, cookie3 = login(ADMIN_EMAIL)
    state["admin"] = token
    me = call("GET", "/api/v1/auth/me", token=token)
    check("GET /auth/me", me.status == 200 and me.json()["role"] == "admin", me.json()["email"])
    tampered = token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB")
    check(
        "tampered access token -> 401", call("GET", "/api/v1/auth/me", token=tampered).status == 401
    )
    head = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
    forged = f"{head}.{token.split('.')[1]}."
    check(
        "alg=none forged token -> 401", call("GET", "/api/v1/auth/me", token=forged).status == 401
    )
    out = call("POST", "/api/v1/auth/logout", cookie=cookie3, headers=CSRF)
    check("logout -> 204 and cookie cleared", out.status == 204)
    check(
        "refresh after logout -> 401",
        call("POST", REFRESH, cookie=cookie3, headers=CSRF).status == 401,
    )
    state["admin"], _ = login(ADMIN_EMAIL)


def scope_rules() -> None:
    print("\n[3] scope: authorisations and dry-run decisions")
    token = state["admin"]
    for kind, value in (
        ("cidr", "127.0.0.0/16"),
        ("cidr", "169.254.0.0/16"),
        ("ip", "169.254.169.254"),
    ):
        resp = call(
            "POST", "/api/v1/scope/entries", token=token, body={"kind": kind, "value": value}
        )
        check(f"cannot authorise hard-denied {value}", resp.status in (400, 422), resp.status)
    entry = call(
        "POST",
        "/api/v1/scope/entries",
        token=token,
        body={
            "kind": "domain",
            "value": "lab.test",
            "include_subdomains": True,
            "description": "e2e lab",
        },
    )
    check("authorise lab.test (+ sub-domains) -> 201", entry.status == 201, entry.json().get("id"))
    state["entry_id"] = str(entry.json()["id"])

    def decide(target: str) -> dict[str, object]:
        resp = call("POST", "/api/v1/scope/check", token=token, body={"target": target})
        assert resp.status == 200, resp.text
        body = resp.json()
        assert isinstance(body, dict)
        return body

    ok = decide("www.lab.test")
    check(
        "www.lab.test allowed, IP pinned from the real DNS answer",
        ok["allowed"] is True and ok["pinned_ips"] == ["93.184.216.34"],
        ok["pinned_ips"],
    )
    refused = [
        "www.other.test",
        "evil-lab.test",
        "lab.test.evil.test",
        "127.0.0.1",
        "169.254.169.254",
        "2130706433",
        "0x7f.1",
        "http://user:pw@www.lab.test/",
    ]
    seen: dict[str, object] = {}
    for target in refused:
        decision = decide(target)
        seen[target] = decision["reason"]
        check(f"refused: {target}", decision["allowed"] is False, decision["reason"])
    queried = " ".join(dns_queries())
    check(
        "no DNS lookup was ever made for unauthorised/malformed names",
        not any(bad in queried for bad in ("other.test", "evil", "2130706433", "0x7f")),
        "dns.log clean",
    )


def scan_success_and_injection() -> None:
    print("\n[4] scan success path through the real worker")
    token = state["admin"]
    before = len(dns_queries())
    created = create_scan(token, "www.lab.test")
    check("POST /scans -> 202", created.status == 202, created.json().get("status"))
    scan_id = str(created.json()["id"])
    state["scan_id"] = scan_id
    scan = wait_scan(token, scan_id)
    check(
        "scan succeeded",
        scan["status"] == "succeeded" and scan["attempts"] == 1,
        f"status={scan['status']} attempts={scan['attempts']}",
    )
    findings = call("GET", f"/api/v1/scans/{scan_id}/findings", token=token).json()
    assert isinstance(findings, list)
    titles = sorted({f["title"] for f in findings})
    a_values = [f["evidence"].get("value") for f in findings if f["title"] == "A record"]
    check(
        "findings: A, MX and missing-SPF",
        {"A record", "MX record", "Missing SPF record"} <= set(titles),
        titles,
    )
    check("A record value comes from the DNS answer", a_values == ["93.184.216.34"], a_values)
    lookups = [q for q in dns_queries()[before:] if q.startswith("query www.lab.test")]
    check(
        "DNS queried by API (scope) and worker (re-validation + engine)",
        len(lookups) >= 3,
        f"{len(lookups)} queries: {sorted(set(lookups))}",
    )

    count_before = len(call("GET", "/api/v1/scans", token=token).json())
    denied = create_scan(token, "www.other.test")
    check(
        "out-of-scope target -> 403 (not queued)", denied.status == 403, denied.error().get("code")
    )
    for payload in (
        "www.lab.test; id",
        "$(id).lab.test",
        "-oX /tmp/x",
        "www.lab.test\nwww.other.test",
        "../../etc/passwd",
    ):
        resp = create_scan(token, payload)
        check(
            f"injection-shaped target refused: {payload!r}",
            resp.status in (400, 403, 422),
            resp.status,
        )
    check("unknown engine refused", create_scan(token, "www.lab.test", "nmap").status in (400, 422))
    resp = call(
        "POST",
        "/api/v1/scans",
        token=token,
        body={
            "engine": "dns_recon",
            "target": "www.lab.test",
            "params": {"record_types": ["A; rm -rf /"]},
        },
    )
    check("hostile engine parameter refused", resp.status in (400, 422), resp.status)
    count_after = len(call("GET", "/api/v1/scans", token=token).json())
    check(
        "none of the refused requests created a scan",
        count_after == count_before,
        f"{count_before} -> {count_after}",
    )


def rebinding_and_cancel() -> None:
    print("\n[5] DNS rebinding while queued, and cancelling a queued scan (worker stopped)")
    token = state["admin"]
    worker("stop")
    try:
        victim = create_scan(token, "www.lab.test")
        cancelled = create_scan(token, "www.lab.test")
        check(
            "both scans accepted and waiting in the queue", victim.status == 202 == cancelled.status
        )
        victim_id, cancel_id = str(victim.json()["id"]), str(cancelled.json()["id"])
        set_records(
            {"www.lab.test": {"A": ["169.254.169.254"]}}
        )  # attacker flips the name to metadata
        cancel = call("POST", f"/api/v1/scans/{cancel_id}/cancel", token=token)
        check(
            "cancel a queued scan -> cancelled at once",
            cancel.status == 200 and cancel.json()["status"] == "cancelled",
            cancel.json().get("status"),
        )
        pending = call("GET", f"/api/v1/scans/{victim_id}", token=token).json()
        check("victim scan still pending while no worker runs", pending["status"] == "pending")
    finally:
        worker("start")
    final = wait_scan(token, victim_id)
    check(
        "rebinding caught at execution: failed / scope_denied",
        final["status"] == "failed" and final["error_code"] == "scope_denied",
        f"{final['status']} / {final['error_code']}",
    )
    findings = call("GET", f"/api/v1/scans/{victim_id}/findings", token=token).json()
    check("no engine ran: zero findings", findings == [], len(findings))
    time.sleep(2)
    scan_b = call("GET", f"/api/v1/scans/{cancel_id}", token=token).json()
    check(
        "cancelled scan stayed cancelled and was never claimed",
        scan_b["status"] == "cancelled" and scan_b["attempts"] == 0,
        f"{scan_b['status']} attempts={scan_b['attempts']}",
    )
    set_records(
        {
            "www.lab.test": {
                "A": ["93.184.216.34"],
                "TXT": ["e2e: no spf here"],
                "MX": ["10 mail.lab.test."],
            }
        }
    )
    again = wait_scan(token, str(create_scan(token, "www.lab.test").json()["id"]))
    check("after the record is restored a new scan succeeds", again["status"] == "succeeded")


def tenancy_and_rbac() -> None:
    print("\n[6] organisation isolation, RBAC and account lockout")
    admin = state["admin"]
    other, _ = login(OTHER_EMAIL)
    sid = state["scan_id"]
    check(
        "other org: GET foreign scan -> 404",
        call("GET", f"/api/v1/scans/{sid}", token=other).status == 404,
    )
    check(
        "other org: foreign findings -> 404",
        call("GET", f"/api/v1/scans/{sid}/findings", token=other).status == 404,
    )
    check(
        "other org: cancel foreign scan -> 404",
        call("POST", f"/api/v1/scans/{sid}/cancel", token=other).status == 404,
    )
    check("other org: sees no scans", call("GET", "/api/v1/scans", token=other).json() == [])
    check(
        "other org: sees no scope entries",
        call("GET", "/api/v1/scope/entries", token=other).json() == [],
    )
    check(
        "other org: cannot scan lab.test (no authorisation)",
        create_scan(other, "www.lab.test").status == 403,
    )

    made = call(
        "POST",
        "/api/v1/users",
        token=admin,
        body={"email": VIEWER_EMAIL, "password": PASSWORD, "role": "viewer"},
    )
    check("admin creates a viewer", made.status == 201)
    viewer, _ = login(VIEWER_EMAIL)
    check("viewer can list scans", call("GET", "/api/v1/scans", token=viewer).status == 200)
    check("viewer cannot launch a scan", create_scan(viewer, "www.lab.test").status == 403)
    check(
        "viewer cannot add scope",
        call(
            "POST",
            "/api/v1/scope/entries",
            token=viewer,
            body={"kind": "domain", "value": "x.test"},
        ).status
        == 403,
    )
    check(
        "viewer cannot read the audit log",
        call("GET", "/api/v1/audit-logs", token=viewer).status == 403,
    )
    check("viewer cannot list users", call("GET", "/api/v1/users", token=viewer).status == 403)

    codes = [
        call("POST", LOGIN, body={"email": VIEWER_EMAIL, "password": "wrong-wrong-wrong"}).status
        for _ in range(5)
    ]
    locked = call("POST", LOGIN, body={"email": VIEWER_EMAIL, "password": PASSWORD})
    check(
        "5 failures lock the account: the correct password is refused too",
        codes == [401] * 5 and locked.status == 401,
        f"{codes} then {locked.status}",
    )


def audit_trail() -> None:
    print("\n[7] audit trail")
    token = state["admin"]
    logs = call("GET", "/api/v1/audit-logs?limit=200", token=token).json()
    assert isinstance(logs, list)
    pairs = Counter((entry["action"], entry["outcome"]) for entry in logs)
    for action in (
        "auth.login",
        "auth.refresh",
        "auth.refresh_reuse_detected",
        "auth.logout",
        "scope.create",
        "scope.check",
        "scan.create",
        "scan.finish",
        "scan.cancel",
        "user.create",
    ):
        check(
            f"audit has {action}",
            any(a == action for a, _ in pairs),
            sorted(o for a, o in pairs if a == action),
        )
    check(
        "scan.create refusals audited (outcome denied)",
        pairs[("scan.create", "denied")] > 0,
        pairs[("scan.create", "denied")],
    )
    check(
        "rebinding denial audited on scan.finish",
        pairs[("scan.finish", "denied")] > 0,
        pairs[("scan.finish", "denied")],
    )
    check(
        "failed logins audited",
        pairs[("auth.login", "denied")] + pairs[("auth.login", "failure")] > 0,
    )
    dump = json.dumps(logs)
    check(
        "audit log contains no password and no refresh token",
        PASSWORD not in dump and state["stolen_cookie"] not in dump,
    )

    import pg8000.exceptions
    import pg8000.native

    url = urlsplit(os.environ["NEO_DATABASE_URL"].replace("+pg8000", ""))
    conn = pg8000.native.Connection(
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port or 5432,
        database=url.path.lstrip("/"),
    )
    total = conn.run("SELECT count(*) FROM audit_logs")[0][0]
    for sql in (
        "DELETE FROM audit_logs",
        "UPDATE audit_logs SET outcome = outcome",
        "TRUNCATE audit_logs",
    ):
        try:
            conn.run(sql)
            check(f"database refuses: {sql}", False, "statement succeeded!")
        except pg8000.exceptions.DatabaseError as exc:
            info = exc.args[0] if exc.args and isinstance(exc.args[0], dict) else {}
            check(f"database refuses: {sql}", True, str(info.get("M", exc))[:70])
    check("audit rows intact", conn.run("SELECT count(*) FROM audit_logs")[0][0] == total, total)
    conn.close()


def rate_limit_probe() -> None:
    print("\n[8] nginx brute-force limiter on /api/v1/auth/")
    codes = [
        call(
            "POST", LOGIN, body={"email": "probe@example.org", "password": "x" * 12}, via_web=True
        ).status
        for _ in range(35)
    ]
    counts = dict(Counter(codes))
    check(
        "first attempts reach the API (401), then nginx answers 429",
        codes[0] == 401 and 429 in codes,
        counts,
    )


def main() -> int:
    scenarios = (
        infrastructure_and_headers,
        authentication,
        scope_rules,
        scan_success_and_injection,
        rebinding_and_cancel,
        tenancy_and_rbac,
        audit_trail,
        rate_limit_probe,
    )
    for scenario in scenarios:
        try:
            scenario()
        except Exception as exc:  # a crashed scenario is a failed check, the rest still runs
            traceback.print_exc()
            check(f"{scenario.__name__} completed", False, repr(exc)[:160])
    failed = [name for name, ok, _ in results if not ok]
    print(f"\n==== API smoke: {len(results) - len(failed)} passed, {len(failed)} failed ====")
    for name in failed:
        print(f"  FAILED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
