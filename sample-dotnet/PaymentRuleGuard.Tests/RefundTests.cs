using PaymentRuleGuard;
using Xunit;
namespace PaymentRuleGuard.Tests;
public class RefundTests
{
    // RF-001
    [Theory]
    [InlineData(0,100)]
    [InlineData(-1,100)]
    [InlineData(101,100)]
    public void RejectsInvalidRefunds(decimal amount, decimal captured)
        => Assert.Throws<ArgumentOutOfRangeException>(() => new RefundService().Refund(amount,captured,"key"));
    // RF-002
    [Fact]
    public void DuplicateRefundKeyDoesNotRefundAgain()
    {
        var service = new RefundService();
        Assert.True(service.Refund(10,100,"key"));
        Assert.False(service.Refund(10,100,"key"));
    }
}
