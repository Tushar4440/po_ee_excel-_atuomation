import csv
import io
import unittest

from openpyxl import Workbook

from csv_transform import (
    CsvFormatError,
    read_csv,
    read_source_file,
    suggest_source_column,
    transform_csv,
)


class CsvTransformTests(unittest.TestCase):
    def test_maps_source_and_fixed_values_in_template_order(self):
        source = read_csv(b"Order ID,Item\nA-1,Widget\nA-2,Gadget\n", "orders.csv")
        template = read_csv(b"SKU,Vendor token,Price,Order\n", "template.csv")

        output, rows = transform_csv(
            source,
            template,
            {
                0: "source:1",
                1: "vendor_token",
                2: "unit_price",
                3: "source:0",
            },
            "token-value",
        )

        self.assertEqual(
            rows,
            [
                ["Widget", "token-value", "10", "A-1"],
                ["Gadget", "token-value", "10", "A-2"],
            ],
        )
        self.assertEqual(
            list(csv.reader(io.StringIO(output.decode("utf-8"), newline=""))),
            [
                ["SKU", "Vendor token", "Price", "Order"],
                ["Widget", "token-value", "10", "A-1"],
                ["Gadget", "token-value", "10", "A-2"],
            ],
        )

    def test_preserves_template_delimiter_and_bom(self):
        source = read_csv(b"Item\nWidget\n", "orders.csv")
        template = read_csv(
            b"\xef\xbb\xbfSKU;Vendor;Price\r\n",
            "template.csv",
        )

        output, _ = transform_csv(
            source,
            template,
            {0: "source:0", 1: "vendor_token", 2: "unit_price"},
            "token",
        )

        self.assertTrue(output.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"SKU;Vendor;Price\r\n", output)

    def test_rejects_ragged_rows(self):
        with self.assertRaisesRegex(CsvFormatError, "expected 2"):
            read_csv(b"Order,Item\nA-1\n", "orders.csv")

    def test_requires_exactly_one_price_mapping(self):
        source = read_csv(b"Item\nWidget\n", "orders.csv")
        template = read_csv(b"SKU,Vendor,Price\n", "template.csv")

        with self.assertRaisesRegex(CsvFormatError, "Unit price"):
            transform_csv(
                source,
                template,
                {0: "source:0", 1: "vendor_token", 2: "blank"},
                "token",
            )

    def test_suggests_ean_mapping_across_common_header_names(self):
        self.assertEqual(suggest_source_column("EAN Number", ["Order", "EAN"]), 1)
        self.assertIsNone(suggest_source_column("EAN", ["Order", "Item"]))
        self.assertIsNone(suggest_source_column("EAN", ["EAN", "EAN Code"]))

    def test_ean_values_are_copied_and_empty_values_stay_blank(self):
        source = read_csv(
            b"EAN,Item\n1234567890123,Widget\nAB12-CD34,Gadget\n,Other\n",
            "orders.csv",
        )
        template = read_csv(b"EAN Number,SKU,Vendor,Price\n", "template.csv")
        ean_source_index = suggest_source_column(
            template.headers[0],
            source.headers,
        )
        self.assertEqual(ean_source_index, 0)

        _, rows = transform_csv(
            source,
            template,
            {
                0: f"source:{ean_source_index}",
                1: "source:1",
                2: "vendor_token",
                3: "unit_price",
            },
            "token",
        )

        self.assertEqual(rows[0][0], "1234567890123")
        self.assertEqual(rows[1][0], "AB12-CD34")
        self.assertEqual(rows[2][0], "")

    def test_reads_xlsx_source_and_preserves_zero_padded_values(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["EAN", "Item"])
        worksheet.append([123, "Widget"])
        worksheet["A2"].number_format = "000000"
        worksheet.append([456, "Gadget"])
        worksheet["A3"].number_format = "000000"
        data = io.BytesIO()
        workbook.save(data)

        source = read_source_file(data.getvalue(), "orders.xlsx")

        self.assertEqual(source.headers, ["EAN", "Item"])
        self.assertEqual(
            source.rows,
            [["000123", "Widget"], ["000456", "Gadget"]],
        )
        _, rows = transform_csv(
            source,
            read_csv(b"EAN,SKU,Vendor,Price\n", "template.csv"),
            {0: "source:0", 1: "source:1", 2: "vendor_token", 3: "unit_price"},
            "token",
        )
        self.assertEqual(
            rows,
            [
                ["000123", "Widget", "token", "10"],
                ["000456", "Gadget", "token", "10"],
            ],
        )

    def test_rejects_unsupported_source_file_extension(self):
        with self.assertRaisesRegex(CsvFormatError, "CSV or XLSX"):
            read_source_file(b"not used", "orders.xls")


if __name__ == "__main__":
    unittest.main()
