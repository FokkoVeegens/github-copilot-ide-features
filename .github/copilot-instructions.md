This repository contains a static website that is published to GitHub Pages. It provides an overview of GitHub Copilot features across different Integrated Development Environments (IDEs).

## Data

The data resides in the `data` folder in JSON format. 

### Features data

There is a json file (data/features.json) containing all features data per ide and also per category. If you feel the need to add additional categories, first check with me for verification.

## Metadata

There is also a metadata file containing some reused entities (data/metadata.json);

- IDEs: contains all IDEs used in the features data
- Stages: contains info about the stage a release of a feature is in; Private Preview, Public Preview, General Availability
- Flags: Some features come with additional notes, like "Only for Enterprise customers", these are stored as flags. If you need to add a flag, first ask me for verification

## Source code

The HTML resides in the root in index.html. The CSS styles are in src/css/styles.css and the logic that is written in JavaScript is in src/js/scripts.js.

Ensure you keep the codebase maintainable and readable. If you need to splitup files for the sake of maintainability, do so.