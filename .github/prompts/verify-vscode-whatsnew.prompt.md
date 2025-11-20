---
agent: agent
model: GPT-5.1 (Preview) (copilot)
description: Will read the provided blog article and check if any updates to existing features need to be made in features.json
argument-hint: provide the blog article link followed by #fetch
---

This is the URL that contains updates for the IDE "VS Code": ${input:blogUrl} #fetch. Verify if there are updates on that page which are not reflected in [features.json](/data/features.json). Don't add new features to our [features.json](/data/features.json) file, only verify existing features on [features.json](/data/features.json).

When you find that a Copilot-related change in the VS Code release notes clearly corresponds to an existing feature id in [features.json](/data/features.json) (for example, custom chat modes renamed to custom agents matching the `custom-agents` feature), add or update the `vs-code` entry under that feature’s `availability` with the correct URL and publication date from the release notes. You will need to retrieve ${input:blogUrl} #fetch to get the correct publication date as it is not stored in the URL itself.