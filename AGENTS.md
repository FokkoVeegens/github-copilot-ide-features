This repository contains a static website that is published to GitHub Pages. It provides an overview of major GitHub Copilot features across different Integrated Development Environments (IDEs). Also the available Large Language Models (LLMs) a part of this list.

## Data

### Features

The features data resides in [features.json](./data/features.json). A feature looks like this:

|Attribute L1|Attribute L2|Format|Instructions|
|-|-|-|-|
|id||string, lower case, dash separated|NEVER contains the name of an IDE (IDE is put in the **availability** attribute), NEVER contains the word "Copilot", short name for the feature, always first check if one already exists, NO DUPLICATE id's|
|name||string|Name of the feature, keep it less than 50 characters. NEVER contains the name of an IDE (IDE is put in the **availability** attribute), NEVER contains the word "Copilot", human-readable name of the feature|
|description||long string|Longer description of the feature, can contain about 2 sentences, will be shown as a popup when hovered over the name|
|tags||string array, all lower case|These should identify the feature and allow the user to filter features, never create a new one without approval from me|
|availability||object map|Map of IDE identifiers (matching keys in metadata.json) to availability objects|
||stage|string|One of the stage codes from metadata.json (PRI, PUB, GA)|
||url|string|GitHub Changelog URL pointing to the feature announcement|
||publishdate|string|Date in dd-mmm-yyyy format, derived from the date in the blog/changelog URL or the contents of the page behind the URL|
||flags|string array (optional)|Array of flag values defined in metadata.json (e.g., individual-only, preview-version)|

#### Add new/update existing feature guidance

- **No duplication**: If you're asked to add a new feature, first verify if it already exists. Naming can be slightly different. If you're unsure, ask me to validate if two features are the same. If a feature already exists in [./data/features.json](./data/features.json), you'll need to update the existing feature instead of adding a new entry. You are allowed to retrieve the URL of an existing feature to have more context to compare with. ALWAYS run [validate-features.ps1](./scripts/validate-features.ps1) to validate your work!
- **Example features**: For examples, please check existing data in the file.

#### Exceptions / special cases

- **Stages and flags**: If the article talks about an IDE called "stable", like "VS Code Stable", it means it's the opposite of the `preview-version` flag. So if a feature is flagged `preview-version` and then an article describes the same feature as available for the "stable" version, then you should remove the `preview-version` flag and not change anything else for that feature.
- **GitHub Copilot CLI / Background Agent**: The GitHub Copilot CLI (command line interface) has been renamed to the GitHub Copilot Background Agent. Keep this in mind when processing older blogs/updates.

#### INCLUDED FEATURES

These features should be in the features list:

- Major features
- Features visible by users
- Features that can be part of a demo

#### EXCLUDED FEATURES

These features should **NOT** be in the features list:

- Bugfixes
- Background improvements, not directly visible to the user
- Performance improvements (e.g., "faster edits", "improved responses", "optimized prompts")
- Improvements where the impact is not directly clear to the user
- Enhancements to existing features (UI polish, visual improvements)
- **Infrastructure changes** (new protocols, transports, backend architecture)
- **Default configuration changes** (e.g., "model X is now the default")
- **Quality improvements** (better/smarter suggestions, more accurate results - these are non-deterministic and hard to demo reliably)
- **Minor UI improvements** (fold/unfold controls, status indicators, visual polish)
- **Configuration details** (input placeholders, config generation methods)
- **Preview/V2 versions of existing features** (unless they represent a fundamentally different approach)
- Features that require specific, hard-to-reproduce scenarios to demonstrate

**The "Demo Test"**: If you cannot easily demonstrate the feature's value in a 2-minute live demo to a client, showing clear before/after differences, it should not be in the list. Good features are:
- Clearly distinct and identifiable
- Provide obvious value in common scenarios
- Work reliably enough to demonstrate
- Can be compared across different IDEs

#### New LLM models

If a feature describes the introduction of a new LLM model, use the following sources to retrieve more information for the description of the model:

- OpenAI models (e.g. GPT 5.2, o3, o4, GPT 5 mini etc): https://platform.openai.com/docs/models
- Anthropic models (e.g. Claude Sonnet 4, Claude Opus 4.5, Claude Haiku 4.5 etc): https://platform.claude.com/docs/en/about-claude/models/overview
- Google models (e.g. Gemini 2.5 Flash, Gemini 2.5 Pro, Gemini 3 etc.): https://ai.google.dev/gemini-api/docs/models
- xAI models (e.g. Grok Code Fast 1, Grok 3 mini etc): https://docs.x.ai/docs/models

You are allowed to follow one of the links to specific model information.

You can also check https://docs.github.com/en/copilot/reference/ai-models/model-comparison if no information can be found on the previously supplied URLs.

### Metadata

The metadata referred to (ides, stages, flags) can be found in [metadata.json](./data/metadata.json). The data in [metadata.json](./data/metadata.json) is fixed and should not be changed, except for Flags in very .

- IDEs: contains all IDEs used in the features data
- Stages: contains info about the stage a release of a feature is in; Private Preview, Public Preview, General Availability
- Flags: Some features come with additional notes, like "Only for Enterprise customers", these are stored as flags. If you need to add a flag, first ask me for verification

## Source code

The HTML resides in the root in index.html. The CSS styles are in src/css/styles.css and the logic that is written in JavaScript is in src/js/scripts.js.

Ensure you keep the codebase maintainable and readable. If you need to splitup files for the sake of maintainability, do so.
