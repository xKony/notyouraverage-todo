# Task-Derived Requester History with Highest-Uppercase Canonicalization

- Status: accepted

`nyatodo` derives **Requester** autocompletion suggestions dynamically from existing **Tasks** (including `Done`) and canonicalizes case-insensitive matches toward the variant with the most uppercase characters rather than maintaining a separate `requesters` table or normalizing to lowercase/first-seen casing.

## Considered Options

- **Separate `requesters` table with manual management**: Preserves **Requesters** independently of **Task** deletions and allows explicit canonical renaming, but adds extra schema, sync logic, and orphan-cleanup UI overhead for a lightweight personal workspace.
- **Lowercase or first-seen casing normalization**: Simple to implement, but either loses intentional capitalization (`@adrian` stays lowercase) or locks in an initial lowercase typo (`@adrian` typed first prevents `@Adrian` from winning).
- **Task-derived history with highest-uppercase canonicalization**: Queries stored **Tasks** dynamically, deduplicates case-insensitively by preferring the variant with the most uppercase characters (tie-breaking by most recently used **Task**), and auto-canonicalizes on save (excluding the edited **Task** itself when updating in **Thinking Space**). Keeps zero extra tables while naturally converging `@adrian` -> `@Adrian` or `ACME`.

## Consequences

- **All-caps sticky bias**: Because deduplication and save-time canonicalization prefer the variant with the most uppercase characters, an accidental all-caps entry (e.g., `@ADRIAN`) outranks `@Adrian` until that **Task**'s **Requester** is edited or deleted. Updating a **Task** in **Thinking Space** excludes that **Task**'s own prior value when checking history, so correcting the sole `@ADRIAN` **Task** back to `@Adrian` succeeds cleanly.
- **Task-derived lifecycle**: Deleting all **Tasks** associated with a **Requester** removes them from autocomplete history, whereas keeping `Done` **Tasks** retains them in suggestions.
