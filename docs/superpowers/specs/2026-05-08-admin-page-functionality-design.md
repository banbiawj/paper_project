# Admin Page Functionality Design

## Scope

Implement the admin page as a real management console for the existing FastAPI
application. The first completed scope is:

- Dashboard with real statistics.
- Bookshelf and category management.
- Entry search, create, edit, and delete.
- Logout from the admin page.
- Admin API authentication checks on every admin data endpoint.

User management and system settings remain outside this implementation because
the project currently has no persistent user store or settings store.

## Current Context

The app uses FastAPI, Jinja templates, static assets, and JSON files under
`static/data/{idiom|words}` as storage. The public/index page already uses Vue 2
and the existing `/api/v1/DisplayContent/*` and `/api/v1/DataOperate/*`
endpoints to manage books, categories, and entries.

The admin page is currently a static Jinja template with local menu switching,
fake dashboard values, and placeholder sections. Login protection exists for
`/admin`, `/`, and `/logout`, but the existing data APIs do not enforce admin
session checks.

## Recommended Architecture

Add a dedicated admin API router under `/api/v1/admin`. These endpoints reuse
the existing JSON file storage and helper functions where practical, but place
admin-specific validation and response shapes in one place.

All admin API endpoints verify the signed admin session cookie. When invalid or
expired, they return a JSON `401` response. The admin page redirects to
`/login?next=/admin` when it receives `401`.

The existing public data endpoints remain in place for compatibility. The admin
page calls only `/api/v1/admin/*` so the UI is not coupled to the older endpoint
names or inconsistent response behavior.

## Admin API Surface

The admin API uses the existing type names:

- `idiom`
- `words`

Endpoints:

- `GET /api/v1/admin/summary`
  Returns counts for total entries, books, categories, and recent entry rows.
- `GET /api/v1/admin/library?type_name=idiom`
  Returns books and category files for a type.
- `GET /api/v1/admin/entries?type_name=idiom&book=词库&category=query.json&keyword=凌空`
  Returns entries from the selected JSON file, optionally filtered by keyword.
- `POST /api/v1/admin/books`
  Creates a book and its `query.json` and `default.json` files.
- `POST /api/v1/admin/categories`
  Creates a category JSON file inside a book.
- `POST /api/v1/admin/entries`
  Creates an entry in the selected book/category.
- `PUT /api/v1/admin/entries`
  Replaces an existing entry identified by its original `word`.
- `DELETE /api/v1/admin/entries`
  Deletes an entry identified by `word`.

The create/edit/delete endpoints update the selected category and keep
`query.json` aligned when possible, matching the behavior users already expect
from the current app.

## Frontend Design

`templates/admin.html` becomes a single-page admin console using vanilla
JavaScript or Vue 2 from the existing local asset. To keep the implementation
close to the existing project, Vue 2 is acceptable and preferred for list and
form state.

Views:

- Dashboard: real summary cards and a recent entries table.
- Books and categories: type selector, book list, category list, create book,
  and create category.
- Entry management: type/book/category selectors, keyword search, table view,
  create/edit/delete actions, and a modal or inline form for entry fields.
- Users: simple read-only placeholder explaining that persistent user management
  is not available yet.
- Settings: simple read-only placeholder explaining that settings storage is not
  available yet.

The sidebar footer uses the actual `admin_user` template variable and restores a
logout form posting to `/logout`.

## Data Flow

On page load:

1. Fetch `/api/v1/admin/summary`.
2. Fetch `/api/v1/admin/library` for the current type.
3. Load entries for the default selection: `idiom`, `词库`, `query.json`.

When changing type or book:

1. Refresh library data.
2. Select a valid default category, preferring `query.json`.
3. Refresh entries.

When creating, editing, or deleting data:

1. Submit to the admin API.
2. Refresh the affected list and dashboard summary.
3. Show an inline success or error message.

## Error Handling

The frontend handles:

- `401`: redirect to `/login?next=/admin`.
- Validation errors: show the API message in the current view.
- Empty lists: render a clear empty state instead of fake data.
- Network errors: show a retryable error message.

Backend errors return consistent JSON with `code`, `message`, and `data`.
Inputs are validated to prevent path traversal and invalid filenames.

## Testing

Add focused tests around the new admin API and template behavior:

- Unauthenticated admin API requests return `401`.
- Authenticated summary request returns real counts.
- The admin page renders the admin layout and logout form.
- Book/category/entry CRUD works against a temporary data root or controlled
  fixture.
- Existing auth tests continue to pass.

## Out Of Scope

- Multi-user account management.
- Runtime system settings persistence.
- Replacing the JSON file storage with a database.
- Changing the public/index page behavior.
