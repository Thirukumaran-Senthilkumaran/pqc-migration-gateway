"""In-process smoke test of the full API flow (no network needed)."""

from fastapi.testclient import TestClient

from api.database import init_db
from api.main import app

init_db()
c = TestClient(app)


def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    assert cond, name


# health
h = c.get("/api/health").json()
check("health ok", h["status"] == "ok")
print("    backend:", h["pqc_backend"], "quantum_safe:", h["quantum_safe"])

# create token
tok = c.post("/api/tokens", json={"name": "Smoke", "org_name": "Test"}).json()
check("token created", tok["token"].startswith("pqcg_"))
raw = tok["token"]

# ingest unauthorized
check("ingest needs auth", c.post("/api/ingest", json={"type": "heartbeat"}).status_code == 401)

# ingest inventory with bearer
hdr = {"Authorization": f"Bearer {raw}"}
payload = {
    "type": "inventory",
    "subnet": "192.168.1.0/24",
    "devices": [
        {"ip": "192.168.1.10", "port": 23, "service": "telnet", "tls_version": "TLSv1"},
        {"ip": "192.168.1.20", "port": 443, "service": "https", "tls_version": "TLSv1.3"},
        {"ip": "192.168.1.30", "port": 502, "service": "modbus"},
    ],
}
ing = c.post("/api/ingest", json=payload, headers=hdr).json()
check("ingest upserted 3", ing["upserted"] == 3)

# devices + tiering
devs = c.get("/api/devices").json()
check("devices listed", len(devs) == 3)
telnet = next(d for d in devs if d["ip"] == "192.168.1.10")
check("telnet is tier-1", telnet["priority_tier"] == "tier-1")
check("weak protocol flagged", telnet["weak_protocol"] is not None)

# dashboard
dash = c.get("/api/dashboard").json()
check("dashboard total 3", dash["total_devices"] == 3)
check("dashboard tier1>=1", dash["tier1_devices"] >= 1)

# wrap
ids = [d["id"] for d in devs[:2]]
wr = c.post("/api/wrapper", json={"device_ids": ids, "action": "apply"}).json()
check("wrapped 2", wr["updated"] == 2)
check("coverage updated", c.get("/api/dashboard").json()["wrapped_devices"] == 2)

# advisor
adv = c.get("/api/advisor").json()
check("advisor returns advice", "advice" in adv and len(adv["advice"]) > 20)

# reports
for fmt in ["csv", "json", "pdf", "migration", "hld", "change-plan", "risk"]:
    r = c.get(f"/api/reports/{fmt}")
    check(f"report {fmt} ok", r.status_code == 200 and len(r.content) > 0)

# pqc demos
mem = c.post("/api/pqc/wrap-demo", json={"message": "secret", "mode": "memory"}).json()
check("memory wrap verified", mem["verified"] is True)
sock = c.post("/api/pqc/wrap-demo", json={"message": "secret", "mode": "socket"}).json()
check("socket tunnel ok", sock["ok"] is True)

# remote gateway
rg = c.post("/api/remote-gateway", json={}).json()
check("remote gateway active", rg["status"] == "active")

# token revoke -> ingest fails
tid = c.get("/api/tokens").json()[0]["id"]
c.delete(f"/api/tokens/{tid}")
check("revoked token rejected", c.post("/api/ingest", json={"type": "heartbeat"}, headers=hdr).status_code == 401)

print("\nALL SMOKE TESTS PASSED")
