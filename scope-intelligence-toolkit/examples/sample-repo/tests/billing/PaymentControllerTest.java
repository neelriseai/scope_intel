package tests.billing;

import org.junit.jupiter.api.Test;
import src.billing.PaymentController;
import src.billing.PaymentService;

public class PaymentControllerTest {

    @Test
    public void chargeReturnsOkForSmallAmounts() {
        PaymentController c = new PaymentController(new PaymentService());
        String result = c.handleCharge("u1", 42.0);
        assert result.equals("OK");
    }

    @Test
    public void chargeRejectsNegativeAmounts() {
        PaymentController c = new PaymentController(new PaymentService());
        String result = c.handleCharge("u1", -1.0);
        assert result.equals("INVALID_AMOUNT");
    }
}
