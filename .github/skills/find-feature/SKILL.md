---
name: find-feature
description: Use the release notes in the data folder of this repository to determine from which version onwards for every IDE a specific feature is available.
argument-hint: "Name or description of the feature"
---

GitHub Copilot is an AI coding assistant, supported in the following IDEs:
- Visual Studio Code
- Visual Studio 2022 and 2026
- JetBrains IDEs (e.g., IntelliJ IDEA, PyCharm, WebStorm)
- Neovim
- Eclipse
- Xcode
- SQL Server Management Studio (SSMS)
- GitHub Copilot CLI

Every IDE has a different support for GitHub Copilot features, and the availability of features may vary across versions. To determine from which version onwards a specific feature is available for each IDE, you can refer to the release notes in the data folder of this repository. The release notes contain detailed information about the features introduced in each version of GitHub Copilot for different IDEs. By reviewing these notes, you can identify when a particular feature was added and which IDEs support it.

## Output format

Generate a markdown table with the following columns, where every IDE where the feature is present, is represented as a row:

| IDE | Version Introduced (Preview/beta/insiders) | Version Introduced (GA/stable) | Feature Description |
| --- | --- | --- | --- |

Where:
- **IDE**: The name of the Integrated Development Environment (IDE) that supports the feature.
- **Version Introduced (Preview/beta/insiders)**: The version of the IDE in which the feature was first introduced for that IDE where the feature was in preview, or in beta or in the insiders version of that IDE. If none can be found, leave empty.
- **Version Introduced (GA/stable)**: The version of the IDE in which the feature became part of the GA or stable version of the IDE. If the feature was never introduced in a preview, beta, or insiders release, mention it only in this column and leave the preview/beta/insiders column empty.
- **Feature Description**: A brief description of the feature, as provided in the release notes.

## Important notes

- Visual Studio 2026 contains all features Visual Studio 2022 has
