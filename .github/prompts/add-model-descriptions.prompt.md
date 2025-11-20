---
agent: agent
model: GPT-5.1 (Preview) (copilot)
description: Will retrieve model descriptions from provider websites and update the features.json file accordingly
---

Update the description for ALL entries in [features.json](/data/features.json) that have the `models` `flag` and that **do not have a description yet**. Summarize the description of the model to 1 sentence and put that in the description. Don't include the model name in the description. Don't include IDE's in the description, just describe what the model is about. Use the following web pages to find the models. If necessary, follow 1 link per model to retrieve the details of that model (in most cases, the short description is already available on these pages directly);
- Models with `gpt` in their name: https://platform.openai.com/docs/models #fetch 
- Models with `claude` in their name: https://platform.claude.com/docs/en/about-claude/models/overview #fetch
- Models with `gemini` in their name: https://ai.google.dev/gemini-api/docs/models #fetch 

Fallback: If you can't find information on a model, retrieve the information from https://docs.github.com/en/copilot/reference/ai-models/model-comparison #fetch

In your response, summarize the models you updated, showing the before and after description for each updated model.