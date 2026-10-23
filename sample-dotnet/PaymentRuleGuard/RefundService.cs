namespace PaymentRuleGuard;
public sealed class RefundService
{
    private readonly HashSet<string> _refunded = new(StringComparer.Ordinal);
    public bool Refund(decimal amount, decimal capturedAmount, string requestKey)
    {
        if (amount <= 0 || amount > capturedAmount) throw new ArgumentOutOfRangeException(nameof(amount));
        if (string.IsNullOrWhiteSpace(requestKey)) throw new ArgumentException("Refund key required");
        return _refunded.Add(requestKey);
    }
}
