from fastapi import FastAPI
from pydantic import BaseModel, Field
from review import review_diff
from retrieval import retrieve
app = FastAPI(title="PaymentRuleGuard AI")
class ReviewRequest(BaseModel):
    diff: str = Field(min_length=1, max_length=25000)
    changed_paths: list[str] = Field(min_length=1, max_length=100)
@app.post("/review")
def review(req: ReviewRequest):
    return review_diff(req.diff, req.changed_paths)
@app.get("/rules")
def rules():
    return retrieve(["src/Payments/PaymentService.cs","src/Refunds/RefundService.cs","src/Transactions/TransactionService.cs"])
@app.get("/health")
def health():
    return {"status": "ok"}
