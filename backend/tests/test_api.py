from tests.helpers import FakeSummarizer, make_client, make_diff, ok_response, signup


def client(summarizer=None):
    return make_client(summarizer)


def test_health():
    assert client().get("/api/health").json() == {"ok": True}


def test_health_db_reports_state_without_secrets():
    r = client().get("/api/health/db")
    body = r.json()
    assert r.status_code == 200
    assert body["ok"] is True and body["reachable"] is True and body["tables_ok"] is True
    assert body["kind"] == "sqlite"
    assert "sqlite://" not in r.text  # never the database URL


def test_db_error_reason_labels_never_echo_details():
    from app.main import _db_error_reason

    assert _db_error_reason(
        'connection to server at "localhost" (::1), port 5433 failed: Connection refused'
    ) == "points_at_localhost"
    assert _db_error_reason(
        'FATAL: password authentication failed for user "neondb_owner"'
    ) == "wrong_user_or_password"
    assert _db_error_reason(
        'could not translate host name "ep-x.neon.tech" to address'
    ) == "host_not_found"
    assert _db_error_reason("something odd") == "other"


def test_try_a_diff_is_public():
    r = client().post("/api/summaries", json={"diff": make_diff("a.py")})
    assert r.status_code == 200


def test_summarize_then_save_verdict():
    c = client(FakeSummarizer([ok_response(["src/app.py"])]))
    r = c.post("/api/summaries", json={"diff": make_diff("src/app.py", "yarn.lock")})
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "done"
    assert (body["files_total"], body["files_kept"]) == (2, 1)
    assert body["skipped"] == [{"path": "yarn.lock", "reason": "lockfile"}]
    assert body["comment_markdown"].endswith("Written by AI. It can be wrong.")

    v = c.post(
        f"/api/summaries/{body['summary_id']}/verdict",
        json={"accurate": "partly", "saved_time": True, "note": "CI was the slow part"},
    )
    assert v.json() == {"ok": True}  # fmt: skip


def test_verdict_validation_and_missing_summary():
    c = client()
    assert c.post("/api/summaries/999/verdict", json={"accurate": "yes"}).status_code == 404
    assert c.post("/api/summaries/1/verdict", json={"accurate": "maybe"}).status_code == 422


def test_without_key_run_fails_and_says_nothing_posted():
    body = client(None).post("/api/summaries", json={"diff": make_diff("a.py")}).json()
    assert (body["status"], body["message"]) == ("failed", "Failed, nothing posted.")
    assert body["comment_markdown"] is None


def test_runs_list_and_detail():
    c = client(FakeSummarizer([ok_response(["src/app.py"])]))
    signup(c)
    done = c.post(
        "/api/summaries", json={"diff": make_diff("src/app.py"), "title": "Add greeting"}
    ).json()
    c.post("/api/summaries", json={"diff": make_diff("package-lock.json")})

    listing = c.get("/api/runs").json()
    assert [r["status"] for r in listing["runs"]] == ["skipped", "done"]  # newest first
    assert listing["runs"][1]["title"] == "Add greeting"
    assert listing["runs"][1]["summary_id"] == done["summary_id"]
    assert listing["runs_this_month"] == 2
    assert listing["spend_this_month_usd"] == 0.008  # 1000*4 + 200*20 micro-dollars
    assert listing["spend_cap_usd"] == 10.0

    detail = c.get(f"/api/runs/{done['run_id']}").json()
    assert detail["result"]["check_first"][0]["path"] == "src/app.py"
    assert detail["comment_markdown"].endswith("Written by AI. It can be wrong.")
    assert "diff" not in detail  # we never return or store the diff

    skipped = c.get(f"/api/runs/{listing['runs'][0]['id']}").json()
    assert skipped["result"] is None
    assert c.get("/api/runs/999").status_code == 404


def test_module_level_app_exists_for_vercel():
    from fastapi import FastAPI

    import app.main

    assert isinstance(app.main.app, FastAPI)


def test_database_urls_from_neon_use_psycopg3():
    from app.db import normalize_db_url

    assert normalize_db_url("postgresql://u:p@ep-x.neon.tech/db?sslmode=require") == (
        "postgresql+psycopg://u:p@ep-x.neon.tech/db?sslmode=require"
    )
    assert normalize_db_url("postgres://u:p@h/db").startswith("postgresql+psycopg://")
    assert normalize_db_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_db_url("sqlite:///:memory:") == "sqlite:///:memory:"
