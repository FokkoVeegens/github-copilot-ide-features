# Definition of done

- Documentation updated (do we need to update the README or other documentation?)
- Ensure all GitHub Actions workflows use the latest versions of the actions they depend on. Look up the absolute latest released version across all major versions. Apply SHA pinning using the commit SHA with the version tag as a comment (e.g. `uses: actions/checkout@<sha> # vX.Y.Z`).
- New tests added (if code was changed/added)
- Python lint is clean (`ruff check scripts tests`)
- All Python tests pass (`pytest`)
- All JavaScript unit tests pass (`npm run test:unit`)
- All Playwright browser tests pass (`npm run test:browser`; install dependencies with `npm ci` and `npx playwright install chromium` when needed)
- All frontend/JavaScript tests pass together (`npm test`)

# Important notes

The GITHUB_TOKEN used by the GitHub Copilot Cloud Agent should never be used to retrieve data for items in the ./data folder.

When adding a new fetch workflow, ensure it includes both a "Commit new files" step (runs only on `main`, i.e. `if: github.ref == 'refs/heads/main'`) and a "Simulate commit (non-default branch)" step (runs on all other branches, logs what would have been committed without pushing).