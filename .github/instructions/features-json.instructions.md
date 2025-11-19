---
applyTo: '**/features.json'
---
- Each feature must have a unique `id`, human-readable `name`, and a `category`. Only use existing categories (e.g. `chat`, `models`, `policies`) unless we explicitly agree to add a new one.
- `availability` is a map of IDE identifiers (must match the IDE keys in metadata.json) to an object with at least:  
  - `stage`: one of the stage codes defined in metadata.json (e.g. `PRI`, `PUB`, `GA`).  
  - `url`: a GitHub Changelog URL pointing to the feature announcement.
- For every `availability` entry, always add a `publishdate` derived from the `url`. Take the `YYYY-MM-DD` immediately following `changelog/` in the URL and convert it to the format `dd-mmm-yyyy` using a 3-letter lowercase English month abbreviation (e.g. `2025-11-13` → `13-nov-2025`).
- Only use `flags` values that are already defined in metadata.json (e.g. `individual-only`, `preview-version`). If a new flag seems necessary, first get it reviewed and added to `metadata.json`.
- When adding new features from Changelog posts, reuse the exact same `url` and `publishdate` across all IDEs listed in the post, and ensure the set of IDE keys matches the product availability described there.