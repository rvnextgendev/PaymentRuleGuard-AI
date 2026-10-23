import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from retrieval import retrieve

def test_payment_rules_and_test_mapping():
    result = retrieve(["src/Payments/PaymentService.cs"])
    ids = {rid for s in result["sources"] for rid in s["rule_ids"]}
    assert {"PR-001","PR-002","PR-003"} <= ids
    assert "PaymentRuleGuard.Tests.PaymentTests" in result["tests"]

def test_refund_includes_global_and_refund_rules():
    result = retrieve(["src/Refunds/RefundService.cs"])
    ids = {rid for s in result["sources"] for rid in s["rule_ids"]}
    assert {"PR-001","RF-001","RF-002"} <= ids

def test_unmapped_csharp_requires_manual_review():
    assert retrieve(["src/Unknown/Unknown.cs"])["unmapped"]
