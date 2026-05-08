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


if __name__ == "__main__":
    unittest.main()
