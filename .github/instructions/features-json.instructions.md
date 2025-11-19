---
applyTo: '**/features.json'
---

If you're asked to add a new feature, first verify if it already exists. If it exists, you'll need to update the table data instead of adding a new feature entry. You are allowed to retrieve the URL of an existing feature to have more context to compare with.

If the article talks about an IDE called "stable", like "VS Code Stable", it means it's the opposite of the `preview-version` flag. So if a feature is flagged `preview-version` and then an article describes the same feature as available for the "stable" version, then you should remove the `preview-version` flag and not change anything else for that feature.

When adding or updating features in `features.json`, please adhere to the following guidelines:

- Each feature must have a unique `id`, human-readable `name`. Never put the IDE name in the feature id or name. Examples of IDE names are "VS Code", "JetBrains", "Neovim", etc.
- Each feature must have one or more `tags`. Only use existing tags (e.g. `chat`, `models`, `policies`) unless we explicitly agree to add a new one.
- `availability` is a map of IDE identifiers (must match the IDE keys in metadata.json) to an object with at least:  
  - `stage`: one of the stage codes defined in metadata.json (e.g. `PRI`, `PUB`, `GA`).  
  - `url`: a GitHub Changelog URL pointing to the feature announcement.
- For every `availability` entry, always add a `publishdate` derived from the `url`. Take the `YYYY-MM-DD` immediately following `changelog/` in the URL and convert it to the format `dd-mmm-yyyy` using a 3-letter lowercase English month abbreviation (e.g. `2025-11-13` → `13-nov-2025`).
- Only use `flags` values that are already defined in metadata.json (e.g. `individual-only`, `preview-version`). If a new flag seems necessary, first get it reviewed and added to `metadata.json`.
- When adding new features from Changelog posts, reuse the exact same `url` and `publishdate` across all IDEs listed in the post, and ensure the set of IDE keys matches the product availability described there.