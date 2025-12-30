# Validate that feature IDs and names don't contain IDE identifiers

$ErrorActionPreference = "Stop"

# Load metadata and features
$metadataPath = Join-Path $PSScriptRoot "..\data\metadata.json"
$featuresPath = Join-Path $PSScriptRoot "..\data\features.json"

Write-Host "Loading metadata from: $metadataPath"
$metadata = Get-Content $metadataPath -Raw | ConvertFrom-Json

Write-Host "Loading features from: $featuresPath"
$features = Get-Content $featuresPath -Raw | ConvertFrom-Json

# Get IDE identifiers and names
$ideIds = $metadata.ides | ForEach-Object { $_.id }
$ideNames = $metadata.ides | ForEach-Object { $_.name }
Write-Host "IDE identifiers to check: $($ideIds -join ', ')"
Write-Host "IDE names to check: $($ideNames -join ', ')"
Write-Host ""

# Track validation errors and warnings
$errors = @()
$warnings = @()

# Keywords that might indicate irrelevant content
$excludedKeywords = @("enhancement", "enhancements", "bugfix", "bugfixes", "performance", "improvement", "improvements")

# Check each feature
foreach ($feature in $features.features) {
    # Check if feature ID contains "copilot" (case-insensitive)
    if ($feature.id -match "(?i)copilot") {
        $errors += "Feature ID '$($feature.id)' contains the word 'copilot' which is not allowed"
    }
    
    # Check if feature name contains "copilot" (case-insensitive)
    if ($feature.name -match "(?i)copilot") {
        $errors += "Feature name '$($feature.name)' (ID: $($feature.id)) contains the word 'copilot' which is not allowed"
    }
    
    # Check for excluded keywords in feature ID and name
    foreach ($keyword in $excludedKeywords) {
        if ($feature.id -match "(?i)\b$([regex]::Escape($keyword))\b") {
            $warnings += "Feature ID '$($feature.id)' contains excluded keyword '$keyword' - might contain irrelevant content"
        }
        if ($feature.name -match "(?i)\b$([regex]::Escape($keyword))\b") {
            $warnings += "Feature name '$($feature.name)' (ID: $($feature.id)) contains excluded keyword '$keyword' - might contain irrelevant content"
        }
    }
    
    foreach ($ideId in $ideIds) {
        # Check if feature ID contains IDE identifier as a separate word (with word boundaries)
        if ($feature.id -match "\b$([regex]::Escape($ideId))\b") {
            $errors += "Feature ID '$($feature.id)' contains IDE identifier '$ideId'"
        }
        
        # Check if feature name contains IDE identifier as a separate word (case-insensitive with word boundaries)
        if ($feature.name -match "(?i)\b$([regex]::Escape($ideId))\b") {
            $errors += "Feature name '$($feature.name)' (ID: $($feature.id)) contains IDE identifier '$ideId'"
        }
        
        # Check if feature description contains IDE identifier as a separate word (case-insensitive with word boundaries)
        if ($feature.description -match "(?i)\b$([regex]::Escape($ideId))\b") {
            $errors += "Feature description for '$($feature.name)' (ID: $($feature.id)) contains IDE identifier '$ideId'"
        }
    }
    
    foreach ($ideName in $ideNames) {
        # Check if feature ID contains IDE name as a separate word (case-insensitive with word boundaries)
        if ($feature.id -match "(?i)\b$([regex]::Escape($ideName))\b") {
            $errors += "Feature ID '$($feature.id)' contains IDE name '$ideName'"
        }
        
        # Check if feature name contains IDE name as a separate word (case-insensitive with word boundaries)
        if ($feature.name -match "(?i)\b$([regex]::Escape($ideName))\b") {
            $errors += "Feature name '$($feature.name)' (ID: $($feature.id)) contains IDE name '$ideName'"
        }
        
        # Check if feature description contains IDE name as a separate word (case-insensitive with word boundaries)
        if ($feature.description -match "(?i)\b$([regex]::Escape($ideName))\b") {
            $errors += "Feature description for '$($feature.name)' (ID: $($feature.id)) contains IDE name '$ideName'"
        }
    }
}

# Report results
if ($warnings.Count -gt 0) {
    Write-Host "⚠️  WARNINGS FOUND" -ForegroundColor Yellow
    Write-Host "Found $($warnings.Count) warning(s):" -ForegroundColor Yellow
    Write-Host ""
    foreach ($warning in $warnings) {
        Write-Host "  ⚠️  $warning" -ForegroundColor Yellow
    }
    Write-Host ""
}

if ($errors.Count -gt 0) {
    Write-Host "VALIDATION FAILED" -ForegroundColor Red
    Write-Host "Found $($errors.Count) error(s):" -ForegroundColor Red
    Write-Host ""
    foreach ($error in $errors) {
        Write-Host "  ❌ $error" -ForegroundColor Red
    }
    exit 1
} else {
    Write-Host "✅ VALIDATION PASSED" -ForegroundColor Green
    Write-Host "All features have valid IDs and names (no IDE identifiers or names found)" -ForegroundColor Green
    exit 0
}
