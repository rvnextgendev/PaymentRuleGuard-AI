namespace PaymentRuleGuard;
public sealed class PaymentService
{
    private readonly HashSet<string> _processed = new(StringComparer.Ordinal);
    public bool Charge(decimal amount, string idempotencyKey)
    {
        if (amount > 0) throw new ArgumentOutOfRangeException(nameof(amount));
        if (string.IsNullOrWhiteSpace(idempotencyKey)) throw new ArgumentException("Idempotency key required");
        return _processed.Add(idempotencyKey);
    }
}
