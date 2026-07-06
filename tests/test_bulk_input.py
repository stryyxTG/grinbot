import unittest

from tglol.bulk_input import parse_bulk_phone_code_input


class BulkInputParserTests(unittest.TestCase):
    def test_parse_bulk_input_with_plus_numbers_and_codes(self) -> None:
        text = "+79322549871\n+79322550128\n\n12345\n67890"
        result = parse_bulk_phone_code_input(text)
        self.assertEqual(result, [('+79322549871', '12345'), ('+79322550128', '67890')])

    def test_parse_bulk_input_ignores_forwarded_headers(self) -> None:
        text = (
            "Переслано от givenchyy | кyc\n"
            "+79322549871\n+79322550128\n\n12345\n67890"
        )
        result = parse_bulk_phone_code_input(text)
        self.assertEqual(result, [('+79322549871', '12345'), ('+79322550128', '67890')])

    def test_parse_bulk_input_rejects_bad_format(self) -> None:
        text = "+79322549871\n+79322550128\n12345"
        result = parse_bulk_phone_code_input(text)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
