import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import review


def test_graph_runs_langchain_with_mapped_evidence(monkeypatch):
    prompts = []

    def respond(prompt):
        prompts.append(prompt.to_messages())
        return AIMessage(content="PR-001: rules/global.md — reject zero amounts.")

    monkeypatch.setattr(review, "create_model", lambda: RunnableLambda(respond))
    result = review.review_diff("+ allow_zero = true", ["src/Payments/PaymentService.cs"])
    assert result["review"].startswith("PR-001:")
    assert result["evidence"]["sources"]
    assert len(prompts) == 1
    assert "untrusted data" in prompts[0][0].content
    assert "SOURCE rules/global.md" in prompts[0][1].content
    assert "+ allow_zero = true" in prompts[0][1].content
    assert "PaymentRuleGuard.Tests.PaymentTests" in prompts[0][1].content


@pytest.mark.parametrize("evidence", [
    {"unmapped": ["Unknown.cs"], "sources": []},
    {"unmapped": [], "sources": []},
])
def test_manual_branch_never_calls_model(monkeypatch, evidence):
    monkeypatch.setattr(review, "retrieve", lambda paths: evidence)

    def unexpected_model():
        pytest.fail("Manual review must not call an LLM")

    monkeypatch.setattr(review, "create_model", unexpected_model)
    assert "review required" in review.review_diff("diff", ["Unknown.cs"])["review"].lower()


def test_groq_requires_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        review.create_model()


def test_groq_adapter_configuration(monkeypatch):
    from langchain_groq import ChatGroq
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-a-real-credential")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    model = review.create_model()
    assert isinstance(model, ChatGroq)
    assert model.model_name == "llama-3.3-70b-versatile"


def test_ollama_adapter_configuration(monkeypatch):
    from langchain_ollama import ChatOllama
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    assert isinstance(review.create_model(), ChatOllama)


def test_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unknown")
    with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
        review.create_model()


def test_oversized_diff_rejected_before_graph(monkeypatch):
    with pytest.raises(ValueError, match="25000"):
        review.review_diff("x" * 25001, ["PaymentService.cs"])
