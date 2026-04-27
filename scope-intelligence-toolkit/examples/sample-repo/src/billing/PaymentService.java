package src.billing;

public class PaymentService {
    public boolean charge(String userId, double amount) {
        // pretend network call
        return amount < 1000.0;
    }

    public boolean refund(String orderId) {
        return true;
    }
}
