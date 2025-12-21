---
agent: agent
model: GPT-5.1 (Preview) (copilot)
description: Will read the provided JetBrains plugin release notes blog article and alter the features.json to process the released feature(s)
argument-hint: provide the blog article link followed by #fetch
---

Follow these steps and do not skip any of them:

1. Retrieve the blog article from the provided link and analyze its content to identify any new features discussed.
2. Skip any feature that starts with "Fixed", because that is not a new feature.
3. Extract tags to be put in the `tags` property of the feature in [features.json](/data/features.json). only use existing tags. If you think there is a need for one or more new tags, then verify with me first before adding them. 
4. Compare the features in the webpage to the features in [features.json](/data/features.json). The description can sometimes deviate a bit, but if a similar feature is found in [features.json](/data/features.json), then update that one instead of creating a new one
5. If the feature is not found in [features.json](/data/features.json), then add it to the [features.json](/data/features.json) file accordingly to ensure that the file correctly represents the new state of the features in the article.
6. Summarize the features from the provided URL in a list format indicating whether each feature was added as new or updated in [features.json](/data/features.json) like this:
   - ➕ Feature 1 (added)
   - ✏️ Feature 2 (edited)
   - ⏩ Feature 3 (skipped)

The link to the article will be provided here: ${input:blogUrl} #fetch