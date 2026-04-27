# Schema Design

## Feature Map Schema
```json
{
  "feature_id": "checkout",
  "aliases": ["place order", "payment flow"],
  "description": "Handles cart finalization, payment authorization, and order creation.",
  "entry_points": ["CheckoutController.placeOrder"],
  "owned_packages": ["com.app.checkout"],
  "key_classes": ["CheckoutService", "PaymentGatewayClient"],
  "depends_on_features": ["pricing", "auth"],
  "related_tests": ["CheckoutServiceTest", "CheckoutFlowE2E"]
}
