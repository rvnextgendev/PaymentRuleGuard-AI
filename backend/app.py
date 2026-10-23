from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from review import review_diff, ModelUnavailableError
from retrieval import retrieve
app = FastAPI(title="PaymentRuleGuard AI")
class ReviewRequest(BaseModel):
    diff: str = Field(min_length=1, max_length=25000)
    changed_paths: list[str] = Field(min_length=1, max_length=100)
@app.post("/review")
def review(req: ReviewRequest):
    try:
        return review_diff(req.diff, req.changed_paths)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
@app.get("/rules")
def rules():
    return retrieve(["src/Payments/PaymentService.cs","src/Refunds/RefundService.cs","src/Transactions/TransactionService.cs"])
@app.get("/health")
def health():
    return {"status": "ok"}
