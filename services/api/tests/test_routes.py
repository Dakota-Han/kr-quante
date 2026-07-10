import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packages" / "kr_core" / "src"))
sys.path.insert(0, str(ROOT / "services" / "api"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_and_strategy(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        response = self.client.get("/strategy/today")
        self.assertEqual(response.status_code, 200)
        self.assertIn("decisions", response.json())
        quote_response = self.client.get("/market/quote/091160")
        self.assertEqual(quote_response.status_code, 200)
        self.assertIn("spread_bps", quote_response.json())

    def test_preview_and_guarded_submit(self):
        preview_response = self.client.post("/orders/preview", json={"account_equity": 10000000})
        self.assertEqual(preview_response.status_code, 200)
        payload = preview_response.json()
        self.assertIn(payload["status"], {"preview", "no_trade"})
        if payload["status"] == "preview":
            submit = self.client.post(
                "/orders/submit",
                json={"preview": payload["preview"], "approved_by": "", "order_type": "LMT"},
            )
            self.assertEqual(submit.status_code, 403)

    def test_manual_sell_is_guarded(self):
        submit = self.client.post(
            "/orders/sell-limit",
            json={"code": "091160", "quantity": 1, "limit_price": 150000, "approved_by": "tester"},
        )
        self.assertEqual(submit.status_code, 403)


if __name__ == "__main__":
    unittest.main()
