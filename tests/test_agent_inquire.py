import unittest
from unittest.mock import patch

from mylib.Agent import inquire as agent_inquire


class AgentInquireTest(unittest.TestCase):
    def test_inquire_idiom_accepts_json_code_fence(self):
        ai_response = """```json
{
  "explain": "from ai",
  "nature": "neutral",
  "emphasis": "usage",
  "derivation": "none",
  "collocation": "common",
  "example": "example sentence"
}
```"""

        with patch("mylib.Agent.inquire.analyse", return_value=ai_response):
            result = agent_inquire.inquire_idiom("new-term")

        self.assertEqual(result["word"], "new-term")
        self.assertEqual(result["explain"], "from ai")

    def test_compare_entries_returns_structured_json(self):
        ai_response = """```json
{
  "summary": "overall difference",
  "common_points": "both describe careful handling",
  "differences": [
    {"word": "careful", "focus": "action detail", "usage": "daily action", "warning": "not a decision word"},
    {"word": "prudent", "focus": "decision quality", "usage": "important choice", "warning": "too formal for small actions"}
  ],
  "selection_advice": "Use careful for actions and prudent for decisions."
}
```"""
        items = [
            {"word": "careful", "explain": "acting with care", "note": ""},
            {"word": "prudent", "explain": "wise and cautious", "note": ""},
        ]

        with patch("mylib.Agent.inquire.analyse", return_value=ai_response) as mocked:
            result = agent_inquire.compare_entries("words", items)

        self.assertEqual(result["summary"], "overall difference")
        self.assertEqual(result["differences"][0]["word"], "careful")
        self.assertIn("careful", mocked.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
