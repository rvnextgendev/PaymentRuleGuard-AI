import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import github_review


@pytest.mark.parametrize("files, reason", [
    ([], "no changed files"),
    ([{"filename": f"file{i}.cs", "patch": "+ change"} for i in range(101)], "100 changed paths"),
    ([{"filename": "Payment.cs"}], "missing/truncated"),
    ([{"filename": "Payment.cs", "patch": "+" * 25000}], "context limit"),
])
def test_unreviewable_files_require_manual_review(monkeypatch, files, reason):
    def unexpected_review(*args):
        pytest.fail("Unreviewable input must not reach the model")

    monkeypatch.setattr(github_review, "review_diff", unexpected_review)
    result = github_review.review_files(files)
    assert result.startswith("MANUAL REVIEW REQUIRED:")
    assert reason in result


def test_valid_files_are_reviewed(monkeypatch):
    calls = []

    def review(diff, paths):
        calls.append((diff, paths))
        return {"review": "PR-001: finding"}

    monkeypatch.setattr(github_review, "review_diff", review)
    assert github_review.review_files([
        {"filename": "Payment.cs", "patch": "+ change"},
    ]) == "PR-001: finding"
    assert calls == [("FILE: Payment.cs\n+ change", ["Payment.cs"])]


def test_empty_github_response_posts_manual_review_comment(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("PR_NUMBER", "1")
    calls = []

    def request(url, method="GET", payload=None):
        calls.append((url, method, payload))
        return json.dumps([] if method == "GET" else {})

    monkeypatch.setattr(github_review, "request", request)
    github_review.main()
    assert len(calls) == 2
    assert calls[1][0].endswith("/issues/1/comments")
    assert calls[1][1] == "POST"
    assert "MANUAL REVIEW REQUIRED" in calls[1][2]["body"]
    assert "no changed files" in calls[1][2]["body"]
