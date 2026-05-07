# Definition of done

- Documentation updated (do we need to update the README or other documentation?)
- Ensure all GitHub Actions workflows use the latest versions of the actions they depend on. Look up the absolute latest released version across all major versions. Apply SHA pinning using the commit SHA with the version tag as a comment (e.g. `uses: actions/checkout@<sha> # vX.Y.Z`).
- New tests added (if code was changed/added)
- All tests pass