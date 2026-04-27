package src.billing;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.beans.factory.annotation.Value;
import src.billing.PaymentService;

@RequestMapping("/api/billing")
public class PaymentController {

    private final PaymentService service;

    @Value("${payment.timeout.ms:5000}")
    private int timeoutMs;

    @Value("${payment.max.amount:10000}")
    private double maxAmount;

    public PaymentController(PaymentService service) {
        this.service = service;
    }

    @PostMapping("/charge")
    public String handleCharge(String userId, double amount) {
        if (amount <= 0 || amount > maxAmount) {
            return "INVALID_AMOUNT";
        }
        boolean ok = service.charge(userId, amount);
        return ok ? "OK" : "DECLINED";
    }

    @PostMapping("/refund")
    public String handleRefund(String orderId) {
        boolean ok = service.refund(orderId);
        return ok ? "REFUNDED" : "FAILED";
    }
}
