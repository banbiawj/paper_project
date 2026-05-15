from pathlib import Path
import unittest


class IndexCompareUITest(unittest.TestCase):
    def setUp(self):
        self.template = Path("templates/index.html").read_text(encoding="utf-8")
        self.script = Path("static/JavaScript/request.js").read_text(encoding="utf-8")

    def test_template_has_compare_selection_binding(self):
        self.assertIn('@change="toggleCompareSelection(item)"', self.template)
        self.assertIn(':checked="isCompareSelected(item)"', self.template)
        self.assertIn("selectedCompareCount", self.template)
        self.assertIn("compareModal", self.template)

    def test_script_has_compare_state_and_api_call(self):
        self.assertIn("selectedCompareItems", self.script)
        self.assertIn("compareResult", self.script)
        self.assertIn("async sendCompare()", self.script)
        self.assertIn("/inquire/compare", self.script)


if __name__ == "__main__":
    unittest.main()
