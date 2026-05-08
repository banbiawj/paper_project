# User Word Data Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the normal vocabulary UI read and write data for the currently logged-in ordinary user instead of a shared static directory.

**Architecture:** Keep admin content-management APIs on `DS_MEMORY_DATA_ROOT/idiom` and `DS_MEMORY_DATA_ROOT/words`. Add user-facing data-root helpers that resolve ordinary user sessions to `DS_MEMORY_DATA_ROOT/user_data/<user_id>` and lazily copy the shared `idiom` and `words` folders as starter data. Update the normal `DisplayContent`, `DataOperate`, and local lookup path in `inquire` to use that session-aware root.

**Tech Stack:** FastAPI, JSON file storage, `unittest`, FastAPI `TestClient`.

---

### Task 1: Regression Test

**Files:**
- Modify: `tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

Add a test that registers two users, writes a word through user A's normal UI API session, then verifies user B's normal UI API session does not read that word.

- [ ] **Step 2: Run the focused test**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_auth.AuthRoutesTest.test_user_word_data_is_isolated_between_accounts -v`

Expected before implementation: the test fails because both users read and write the same shared `words/词库/query.json`.

### Task 2: Session-Aware User Data Root

**Files:**
- Modify: `app/auth.py`
- Modify: `app/api/v1/endpoints/DataOperate.py`
- Modify: `app/api/v1/endpoints/DisplayContent.py`
- Modify: `app/api/v1/endpoints/inquire.py`

- [ ] **Step 1: Add helpers**

Add helpers to `app/auth.py` that resolve the shared data root, create a per-user root, and copy starter `idiom` and `words` directories on first use.

- [ ] **Step 2: Wire user-facing endpoints**

Pass `Request` into user-facing endpoint handlers and derive `idiom`/`words` base directories from the current ordinary user session when present. Fall back to the shared data root for admin sessions so the page still works for the administrator.

- [ ] **Step 3: Run the focused test**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_auth.AuthRoutesTest.test_user_word_data_is_isolated_between_accounts -v`

Expected after implementation: pass.

### Task 3: Full Verification

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run auth tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_auth.AuthRoutesTest -v`

- [ ] **Step 2: Run full tests**

Run: `.\.venv\Scripts\python.exe -m unittest discover -v`

- [ ] **Step 3: Inspect working tree**

Run: `git status --short`
