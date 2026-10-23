using PaymentRuleGuard;
using Xunit;
namespace PaymentRuleGuard.Tests;
public class PaymentTests
{
    // PR-001
    [Theory]
    [InlineData(0)]
    [InlineData(-1)]
    public void RejectsNonPositiveAmounts(decimal amount)
        => Assert.Throws<ArgumentOutOfRangeException>(() => new PaymentService().Charge(amount, "key"));
    // PR-002
    [Fact]
    public void RepeatedKeyDoesNotCreateSecondCharge()
    {
        var service = new PaymentService();
        Assert.True(service.Charge(10, "key"));
        Assert.False(service.Charge(10, "key"));
    }
    [Fact]
    public void ValidAmountIsAccepted() => Assert.True(new PaymentService().Charge(10, "key"));
}
