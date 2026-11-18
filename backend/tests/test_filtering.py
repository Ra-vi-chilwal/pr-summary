from app.diff import FileDiff, parse_diff
from app.filtering import MAX_PATCH_CHARS, plan_files, skip_reason
from tests.helpers import make_diff


def test_skip_reasons():
    assert skip_reason(FileDiff("package-lock.json")) == "lockfile"
    assert skip_reason(FileDiff("web/yarn.lock")) == "lockfile"
    assert skip_reason(FileDiff("go.sum")) == "lockfile"
    assert skip_reason(FileDiff("dist/app.js")) == "generated"
    assert skip_reason(FileDiff("static/app.min.js")) == "generated"
    assert skip_reason(FileDiff("api/user_pb2.py")) == "generated"
    assert skip_reason(FileDiff("assets/logo.PNG")) == "image or binary"
    assert skip_reason(FileDiff("data.bin", is_binary=True)) == "image or binary"
    assert skip_reason(FileDiff("src/build.py")) is None
    assert skip_reason(FileDiff("src/payments/refund.py")) is None


def test_only_lockfiles_means_nothing_to_summarize():
    plan = plan_files(parse_diff(make_diff("package-lock.json", "yarn.lock")))
    assert plan.skip_kind == "nothing_to_summarize"
    assert plan.message.startswith("Nothing to summarize")
    assert plan.kept == []


def test_more_than_100_files_is_skipped():
    plan = plan_files(parse_diff(make_diff(*[f"src/f{i}.py" for i in range(101)])))
    assert plan.skip_kind == "too_many_files"
    assert "101 files" in plan.message


def test_exactly_100_files_is_allowed():
    plan = plan_files(parse_diff(make_diff(*[f"src/f{i}.py" for i in range(100)])))
    assert plan.skip_kind is None
    assert len(plan.kept) == 100


def test_mixed_pr_keeps_only_code():
    plan = plan_files(parse_diff(make_diff("src/app.py", "package-lock.json", "img/a.png")))
    assert plan.skip_kind is None
    assert [f.path for f in plan.kept] == ["src/app.py"]
    assert {s.path: s.reason for s in plan.skipped} == {
        "package-lock.json": "lockfile",
        "img/a.png": "image or binary",
    }


def test_huge_diff_is_skipped():
    plan = plan_files([FileDiff("big.py", patch="x" * (MAX_PATCH_CHARS + 1))])
    assert plan.skip_kind == "too_big"


def test_empty_diff():
    assert plan_files([]).skip_kind == "empty"
