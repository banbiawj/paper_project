# AI Compare Words Design

## Scope

Add an AI comparison feature to the main user page. A user can select two or
more visible entries in `templates/index.html`, then ask the system to compare
the selected entry details and explain the differences between them.

The comparison uses only the entries currently loaded on the page. It does not
perform extra word lookup, does not search other books or categories, and does
not save comparison output back into the word library.

## Current Context

The existing AI search flow is:

- The Vue app in `static/JavaScript/request.js` sends a single word to
  `/api/v1/inquire/query`.
- `app/api/v1/endpoints/inquire.py` first checks local storage, then calls
  `mylib.Agent.inquire.inquire_idiom()` or `inquire_words()`.
- AI client setup and JSON parsing live in `mylib/Agent/inquire.py`.
- The main page already renders a checkbox in each card, but it is not bound to
  Vue state.

The page data is available as `resultOutput`, so the selected entries can be
sent as full objects without additional backend reads.

## Recommended Architecture

Add a separate comparison endpoint under the existing inquire router:

`POST /api/v1/inquire/compare`

Request body:

```json
{
  "TypeName": "idiom",
  "items": [
    {"word": "...", "explain": "...", "nature": "...", "note": "..."}
  ]
}
```

The endpoint validates that at least two entries were provided and that every
entry has a non-empty `word`. It passes the selected entry objects to a new
agent helper, which asks the model to return a structured JSON object:

```json
{
  "summary": "...",
  "common_points": "...",
  "differences": [
    {
      "word": "...",
      "focus": "...",
      "usage": "...",
      "warning": "..."
    }
  ],
  "selection_advice": "..."
}
```

The endpoint response keeps the existing API envelope:

```json
{
  "code": 200,
  "message": "succeed",
  "data": { "...": "..." }
}
```

## Frontend Design

In `templates/index.html`, bind the existing card checkbox to selected entry
state. Add a compact compare action near the toolbar or floating actions. The
button is enabled only when two or more entries are selected.

In `static/JavaScript/request.js`, add:

- `selectedCompareItems`: selected words or entries keyed by word.
- `compareResult`: the structured AI result.
- `compareErrorMessage`: user-facing failure message.
- `compareLoading`: loading state while the AI request is running.
- Methods to toggle selection, clear selection, check selected state, and send
  the compare request.

When the user clicks AI compare:

1. If fewer than two entries are selected, show an error in the compare modal.
2. Otherwise, open a loading modal and send `TypeName` plus the selected entry
   objects to `/api/v1/inquire/compare`.
3. Render summary, common points, per-word differences, and selection advice.

## Error Handling

Frontend validation catches fewer than two selected entries before sending the
request. Backend validation returns an error if the payload is malformed, has
fewer than two items, or contains entries without `word`.

AI failures follow the current pattern in `inquire.py`: return a JSON error
response with a non-200 status and a readable `message`. The frontend displays
that message in the comparison modal.

## Testing

Backend tests cover:

- Rejecting a compare request with fewer than two entries.
- Rejecting entries without `word`.
- Returning structured comparison data when the agent helper succeeds.
- Preserving the existing `/inquire/query` behavior.

Frontend behavior is kept simple enough to verify through rendered template
assertions and manual browser testing: checkbox binding exists, the compare
button is present, and the modal has loading, error, and result sections.

