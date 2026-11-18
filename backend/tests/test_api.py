from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.helpers import FakeSummarizer, make_diff, ok_response


def client(summarizer=None, dev=True) -> TestClient:
    settings = Settings(database_url="sqlite:///:memory:", enable_dev_tools=dev,
                        anthropic_api_key=None, _env_file=None)  # fmt: skip
    return TestClient(create_app(settings, summarizer=summarizer))


def test_health():
    assert client().get("/api/health").json() == {"ok": True}


def test_dev_routes_are_off_unless_enabled():
    r = client(dev=False).post("/api/dev/summaries", json={"diff": make_diff("a.py")})
    assert r.status_code == 404


def test_summarize_then_save_verdict():
    c = client(FakeSummarizer([ok_response(["src/app.py"])]))
    r = c.post("/api/dev/summaries", json={"diff": make_diff("src/app.py", "yarn.lock")})
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "done"
    assert (body["files_total"], body["files_kept"]) == (2, 1)
    assert body["skipped"] == [{"path": "yarn.lock", "reason": "lockfile"}]
    assert body["comment_markdown"].endswith("Written by AI. It can be wrong.")

    v = c.post(
        f"/api/dev/summaries/{body['summary_id']}/verdict",
        json={"accurate": "partly", "saved_time": True, "note": "CI was the slow part"},
    )
    assert v.json() == {"ok": True}  # fmt: skip


def test_verdict_validation_and_missing_summary():
    c = client()
    assert c.post("/api/dev/summaries/999/verdict", json={"accurate": "yes"}).status_code == 404
    assert c.post("/api/dev/summaries/1/verdict", json={"accurate": "maybe"}).status_code == 422


def test_without_key_run_fails_and_says_nothing_posted():
    body = client(None).post("/api/dev/summaries", json={"diff": make_diff("a.py")}).json()
    assert (body["status"], body["message"]) == ("failed", "Failed, nothing posted.")
    assert body["comment_markdown"] is None


def test_runs_list_and_detail():
    c = client(FakeSummarizer([ok_response(["src/app.py"])]))
    done = c.post(
        "/api/dev/summaries", json={"diff": make_diff("src/app.py"), "title": "Add greeting"}
    ).json()
    c.post("/api/dev/summaries", json={"diff": make_diff("package-lock.json")})

    listing = c.get("/api/dev/runs").json()
    assert [r["status"] for r in listing["runs"]] == ["skipped", "done"]  # newest first
    assert listing["runs"][1]["title"] == "Add greeting"
    assert listing["runs"][1]["summary_id"] == done["summary_id"]
    assert listing["runs_this_month"] == 2
    assert listing["spend_this_month_usd"] == 0.008  # 1000*4 + 200*20 micro-dollars
    assert listing["spend_cap_usd"] == 10.0

    detail = c.get(f"/api/dev/runs/{done['run_id']}").json()
    assert detail["result"]["check_first"][0]["path"] == "src/app.py"
    assert detail["comment_markdown"].endswith("Written by AI. It can be wrong.")
    assert "diff" not in detail  # we never return or store the diff

    skipped = c.get(f"/api/dev/runs/{listing['runs'][0]['id']}").json()
    assert skipped["result"] is None
    assert c.get("/api/dev/runs/999").status_code == 404
