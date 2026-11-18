from app.diff import parse_diff
from tests.helpers import file_diff

RENAME_AND_DELETE = """\
diff --git a/old/name.py b/new/name.py
similarity index 90%
rename from old/name.py
rename to new/name.py
index 1..2 100644
--- a/old/name.py
+++ b/new/name.py
@@ -1,2 +1,2 @@
 keep
-old line
+new line
diff --git a/gone.txt b/gone.txt
deleted file mode 100644
index 3..0
--- a/gone.txt
+++ /dev/null
@@ -1,2 +0,0 @@
-a
-b
diff --git a/logo.png b/logo.png
index 4..5 100644
Binary files a/logo.png and b/logo.png differ
"""


def test_parses_multiple_files_with_counts():
    text = file_diff("a.py", added=["x", "y"], removed=["z"]) + "\n" + file_diff("b.py", new=True)
    files = parse_diff(text)
    assert [f.path for f in files] == ["a.py", "b.py"]
    assert (files[0].additions, files[0].deletions, files[0].status) == (2, 1, "modified")
    assert files[1].status == "added"
    assert files[0].patch.startswith("diff --git a/a.py b/a.py")
    assert "+y" in files[0].patch and "b.py" not in files[0].patch


def test_rename_delete_and_binary():
    renamed, deleted, image = parse_diff(RENAME_AND_DELETE)
    assert (renamed.path, renamed.old_path, renamed.status) == (
        "new/name.py",
        "old/name.py",
        "renamed",
    )
    assert (renamed.additions, renamed.deletions) == (1, 1)
    assert (deleted.path, deleted.status, deleted.deletions) == ("gone.txt", "deleted", 2)
    assert image.is_binary


def test_content_lines_that_look_like_headers_are_counted_as_content():
    text = file_diff("a.md", added=["++ not a header", "+++ also content"], removed=["-- x"])
    (f,) = parse_diff(text)
    assert f.path == "a.md"
    assert (f.additions, f.deletions) == (2, 1)


def test_empty_or_non_diff_input_gives_no_files():
    assert parse_diff("") == []
    assert parse_diff("just some text\nnot a diff") == []
