import json
import unittest

from fastapi.testclient import TestClient

from app import app


class AppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_homepage_serves_upload_interface(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("PO CSV Builder", response.text)

    def test_preview_and_transform_uploaded_csv_files(self):
        source = ("Order ID,Item\nA-1,Widget\n").encode()
        template = b"Item,Vendor token,Price\n"
        files = {
            "source_file": ("orders.csv", source, "text/csv"),
            "template_file": ("template.csv", template, "text/csv"),
        }

        preview = self.client.post("/api/preview", files=files)

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["cache-control"], "no-store")
        self.assertEqual(
            preview.json()["suggested_mappings"],
            ["source:1", "blank", "blank"],
        )

        result = self.client.post(
            "/api/transform",
            files=files,
            data={
                "vendor_token": "token-value",
                "mappings": json.dumps(
                    {"0": "source:1", "1": "vendor_token", "2": "unit_price"}
                ),
            },
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers["cache-control"], "no-store")
        self.assertEqual(result.json()["preview"], [["Widget", "token-value", "10"]])
        self.assertEqual(
            result.json()["output_csv"],
            "Item,Vendor token,Price\nWidget,token-value,10\n",
        )

    def test_transform_reports_missing_required_special_mapping(self):
        response = self.client.post(
            "/api/transform",
            files={
                "source_file": ("orders.csv", b"Item\nWidget\n", "text/csv"),
                "template_file": ("template.csv", b"SKU,Vendor,Price\n", "text/csv"),
            },
            data={
                "vendor_token": "token-value",
                "mappings": json.dumps(
                    {"0": "source:0", "1": "vendor_token", "2": "blank"}
                ),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unit price", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
