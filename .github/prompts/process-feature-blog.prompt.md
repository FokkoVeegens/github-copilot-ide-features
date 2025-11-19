---
agent: agent
model: GPT-5.1 (Preview) (copilot)
description: Will read the provided blog article and alter the features.json to process the blogged feature(s)
argument-hint: provide the blog article link followed by #fetch
---

Follow these steps and do not skip any of them:

1. Retrieve the blog article from the provided link and analyze its content to identify any new features discussed.
2. Extract tags to be put in the `tags` property of the feature in [features.json](/data/features.json). only use existing tags. If you think there is a need for one or more new tags, then verify with me first before adding them. 
3. Based on the identified features, update the [features.json](/data/features.json) file accordingly to ensure that the file correctly represents the new state of the features in the article.

The link to the article will be provided here: ${input:blogUrl} #fetch