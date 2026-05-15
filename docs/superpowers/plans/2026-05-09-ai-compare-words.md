# AI Compare Words Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users select two or more visible entries on the main page and request an AI comparison of their existing details.

**Architecture:** Add a focused `/api/v1/inquire/compare` endpoint beside the existing AI search endpoint. The endpoint validates selected entry objects and delegates model interaction to `mylib.Agent.inquire.compare_entries()`. The Vue page keeps selected entries in local state, sends only currently loaded entry objects, and renders the structured comparison result in a Bootstrap modal.

**Tech Stack:** FastAPI, Pydantic v2, Vue 2, Bootstrap 5, Python `unittest`, FastAPI `TestClient`.

---

## File Structure

- Modify `mylib/Agent/inquire.py`: add `compare_entries(type_name, items)` and a small prompt builder that reuses `analyse()` and `_parse_json_object()`.
- Modify `app/api/v1/endpoints/inquire.py`: add request model, validation helpers, and `POST /compare`.
- Modify `static/JavaScript/request.js`: add compare selection state, API call, and render helpers.
- Modify `templates/index.html`: bind card checkboxes, add compare button, and add compare modal.
- Modify `tests/test_agent_inquire.py`: cover agent JSON parsing for comparison.
- Modify `tests/test_auth.py`: cover compare endpoint validation and success response.
- Create `tests/test_index_compare_ui.py`: assert required Vue bindings and modal hooks exist in the rendered template/static JS.

---

### Task 1: Agent Comparison Helper

**Files:**
- Modify: `tests/test_agent_inquire.py`
- Modify: `mylib/Agent/inquire.py`

- [ ] **Step 1: Write the failing agent test**

Add this test to `tests/test_agent_inquire.py`:

```python
    def test_compare_entries_returns_structured_json(self):
        ai_response = """```json
{
  "summary": "总体区别",
  "common_points": "都有接近含义",
  "differences": [
    {"word": "谨慎", "focus": "做事小心", "usage": "用于行动", "warning": "不要泛指速度"},
    {"word": "慎重", "focus": "决策认真", "usage": "用于选择", "warning": "不要用于轻微动作"}
  ],
  "selection_advice": "写决策用慎重，写动作细致用谨慎"
}
```"""
        items = [
            {"word": "谨慎", "explain": "小心", "note": ""},
            {"word": "慎重", "explain": "认真", "note": ""},
        ]

        with patch("mylib.Agent.inquire.analyse", return_value=ai_response) as mocked:
            result = agent_inquire.compare_entries("words", items)

        self.assertEqual(result["summary"], "总体区别")
        self.assertEqual(result["differences"][0]["word"], "谨慎")
        self.assertIn("谨慎", mocked.call_args.args[1])
```

- [ ] **Step 2: Run the failing agent test**

Run:

```powershell
python -m unittest tests.test_agent_inquire.AgentInquireTest.test_compare_entries_returns_structured_json -v
```

Expected: fail because `compare_entries` does not exist.

- [ ] **Step 3: Implement the helper**

In `mylib/Agent/inquire.py`, add imports and functions:

```python
def _compare_prompt(type_name):
    label = "chengyu" if type_name == "idiom" else "word"
    return (
        "You are a Chinese language teacher. Compare the selected "
        f"{label} entries using only the JSON details provided by the user. "
        "Return Simplified Chinese in one JSON object with keys: "
        "summary, common_points, differences, selection_advice. "
        "differences must be a list of objects with keys: word, focus, usage, warning. "
        "Do not wrap the answer in prose."
    )


def compare_entries(type_name, items):
    payload = json.dumps(items, ensure_ascii=False, sort_keys=True)
    data = analyse(_compare_prompt(type_name), payload)
    result = _parse_json_object(data)
    if not isinstance(result.get("differences"), list):
        raise ValueError("AI comparison must include differences")
    return result
```

- [ ] **Step 4: Run the agent tests**

Run:

```powershell
python -m unittest tests.test_agent_inquire -v
```

Expected: both agent tests pass.

---

### Task 2: Compare API Endpoint

**Files:**
- Modify: `tests/test_auth.py`
- Modify: `app/api/v1/endpoints/inquire.py`

- [ ] **Step 1: Write failing endpoint tests**

Add these tests to `AuthRoutesTest` in `tests/test_auth.py`:

```python
    def test_compare_requires_at_least_two_entries(self):
        response = self.client.post(
            "/api/v1/inquire/compare",
            json={"TypeName": "words", "items": [{"word": "谨慎", "explain": "小心"}]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("at least two", response.json()["message"])

    def test_compare_rejects_entry_without_word(self):
        response = self.client.post(
            "/api/v1/inquire/compare",
            json={
                "TypeName": "words",
                "items": [
                    {"word": "谨慎", "explain": "小心"},
                    {"explain": "认真"},
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("word", response.json()["message"])

    def test_compare_returns_ai_result_for_selected_entries(self):
        ai_result = {
            "summary": "总体区别",
            "common_points": "都表示认真",
            "differences": [
                {"word": "谨慎", "focus": "行动小心", "usage": "行动", "warning": "不要泛指决定"},
                {"word": "慎重", "focus": "决定认真", "usage": "决策", "warning": "不要泛指动作"},
            ],
            "selection_advice": "根据语境选择",
        }

        with patch(
            "app.api.v1.endpoints.inquire.agent_inquire.compare_entries",
            return_value=ai_result,
        ) as mocked:
            response = self.client.post(
                "/api/v1/inquire/compare",
                json={
                    "TypeName": "words",
                    "items": [
                        {"word": "谨慎", "explain": "小心", "note": ""},
                        {"word": "慎重", "explain": "认真", "note": ""},
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["summary"], "总体区别")
        mocked.assert_called_once()
```

- [ ] **Step 2: Run failing endpoint tests**

Run:

```powershell
python -m unittest tests.test_auth.AuthRoutesTest.test_compare_requires_at_least_two_entries tests.test_auth.AuthRoutesTest.test_compare_rejects_entry_without_word tests.test_auth.AuthRoutesTest.test_compare_returns_ai_result_for_selected_entries -v
```

Expected: fail because `/api/v1/inquire/compare` does not exist.

- [ ] **Step 3: Implement request model and endpoint**

In `app/api/v1/endpoints/inquire.py`, add:

```python
from typing import Any
```

Add the request model:

```python
class CompareRequest(BaseModel):
    TypeName: limit = Field(default=limit.idiom)
    items: list[dict[str, Any]]
```

Add helpers and route:

```python
def _compare_error(message: str, status_code: int = 400) -> JSONResponse:
    error = ErrorResponse(code=status_code, message=message)
    return JSONResponse(status_code=status_code, content=error.model_dump())


def _validated_compare_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(items) < 2:
        raise ValueError("compare requires at least two entries")
    validated = []
    for item in items:
        word = str(item.get("word", "")).strip()
        if not word:
            raise ValueError("each compare entry requires word")
        validated.append(dict(item, word=word))
    return validated


@router.post("/compare", response_model=REST_API_standard)
async def compare_entries(payload: CompareRequest):
    try:
        type_name = _type_value(payload.TypeName)
        items = _validated_compare_items(payload.items)
    except ValueError as exc:
        return _compare_error(str(exc))

    try:
        result = agent_inquire.compare_entries(type_name, items)
        if not isinstance(result, dict):
            raise ValueError("AI returned no comparison")
        return REST_API_standard(code=200, message="succeed", data=result)
    except Exception as exc:
        error = ErrorResponse(code=500, message=f"compare failed: {exc}")
        return JSONResponse(status_code=500, content=error.model_dump())
```

- [ ] **Step 4: Run endpoint tests**

Run:

```powershell
python -m unittest tests.test_auth.AuthRoutesTest.test_compare_requires_at_least_two_entries tests.test_auth.AuthRoutesTest.test_compare_rejects_entry_without_word tests.test_auth.AuthRoutesTest.test_compare_returns_ai_result_for_selected_entries -v
```

Expected: all three endpoint tests pass.

---

### Task 3: Frontend Compare Controls

**Files:**
- Create: `tests/test_index_compare_ui.py`
- Modify: `templates/index.html`
- Modify: `static/JavaScript/request.js`

- [ ] **Step 1: Write failing UI assertions**

Create `tests/test_index_compare_ui.py`:

```python
from pathlib import Path
import unittest


class IndexCompareUITest(unittest.TestCase):
    def setUp(self):
        self.template = Path("templates/index.html").read_text(encoding="utf-8")
        self.script = Path("static/JavaScript/request.js").read_text(encoding="utf-8")

    def test_template_has_compare_selection_binding(self):
        self.assertIn("@change=\"toggleCompareSelection(item)\"", self.template)
        self.assertIn(":checked=\"isCompareSelected(item)\"", self.template)
        self.assertIn("selectedCompareCount", self.template)
        self.assertIn("compareModal", self.template)

    def test_script_has_compare_state_and_api_call(self):
        self.assertIn("selectedCompareItems", self.script)
        self.assertIn("compareResult", self.script)
        self.assertIn("async sendCompare()", self.script)
        self.assertIn("/inquire/compare", self.script)
```

- [ ] **Step 2: Run failing UI assertions**

Run:

```powershell
python -m unittest tests.test_index_compare_ui -v
```

Expected: fail because compare bindings do not exist.

- [ ] **Step 3: Add Vue state and methods**

In `static/JavaScript/request.js`, add data fields:

```javascript
        selectedCompareItems: {},
        compareResult: null,
        compareErrorMessage: "",
        compareLoading: false,
```

Add computed field:

```javascript
    selectedCompareCount() {
        return Object.keys(this.selectedCompareItems).length
    },
```

Add methods:

```javascript
        compareKey(item) {
            return item && item.word ? item.word : "";
        },
        isCompareSelected(item) {
            const key = this.compareKey(item);
            return Boolean(key && this.selectedCompareItems[key]);
        },
        toggleCompareSelection(item) {
            const key = this.compareKey(item);
            if (!key) {
                return;
            }
            if (this.selectedCompareItems[key]) {
                this.$delete(this.selectedCompareItems, key);
            } else {
                this.$set(this.selectedCompareItems, key, item);
            }
        },
        clearCompareSelection() {
            this.selectedCompareItems = {};
        },
        compareDifferences() {
            if (this.compareResult && Array.isArray(this.compareResult.differences)) {
                return this.compareResult.differences;
            }
            return [];
        },
        async sendCompare() {
            this.compareResult = null;
            this.compareErrorMessage = "";
            const items = Object.values(this.selectedCompareItems);
            if (items.length < 2) {
                this.compareErrorMessage = "请至少选择两个词条进行辨析";
                this.showModal("compareModal");
                return;
            }
            this.compareLoading = true;
            this.showModal("compareModal");
            try {
                const response = await fetch(`${this.API_BASE}/inquire/compare`, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({TypeName: this.TypeName, items: items})
                });
                const data = await response.json();
                if (!response.ok || data.code !== 200) {
                    throw new Error(data.message || `服务端错误 ${response.status}`);
                }
                this.compareResult = data.data;
            } catch (err) {
                this.compareErrorMessage = "辨析失败: " + err.message;
            } finally {
                this.compareLoading = false;
            }
        },
```

- [ ] **Step 4: Add template controls and modal**

In `templates/index.html`, update the card checkbox:

```html
<input type="checkbox"
       class="form-check-input me-2"
       :checked="isCompareSelected(item)"
       @change="toggleCompareSelection(item)">
```

Add a toolbar button:

```html
<button class="toolbar-btn"
        type="button"
        :class="{'active-btn': selectedCompareCount >= 2}"
        @click="sendCompare">
  <i class="bi bi-columns-gap"></i>
  <span>AI辨析</span>
  <span class="badge text-bg-secondary ms-1" style="border-radius:8px">{{selectedCompareCount}}</span>
</button>
```

Add a modal with id `compareModal` that renders loading, error, and result states.

- [ ] **Step 5: Run UI assertions**

Run:

```powershell
python -m unittest tests.test_index_compare_ui -v
```

Expected: both UI tests pass.

---

### Task 4: Regression Verification

**Files:**
- Test only.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m unittest tests.test_agent_inquire tests.test_index_compare_ui tests.test_auth.AuthRoutesTest.test_compare_requires_at_least_two_entries tests.test_auth.AuthRoutesTest.test_compare_rejects_entry_without_word tests.test_auth.AuthRoutesTest.test_compare_returns_ai_result_for_selected_entries tests.test_auth.AuthRoutesTest.test_inquire_uses_sqlite_local_lookup_after_json_source_removed -v
```

Expected: all listed tests pass.

- [ ] **Step 2: Run the full current test suite**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: pass, or report unrelated pre-existing failures with exact output.

- [ ] **Step 3: Review local diff**

Run:

```powershell
git diff -- app/api/v1/endpoints/inquire.py mylib/Agent/inquire.py static/JavaScript/request.js templates/index.html tests/test_agent_inquire.py tests/test_auth.py tests/test_index_compare_ui.py
```

Expected: diff only contains the AI compare feature.

