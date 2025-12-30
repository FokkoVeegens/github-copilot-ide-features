# Update processed.json with URLs from features.json

$ErrorActionPreference = "Stop"

# Load metadata, features, and processed
$metadataPath = Join-Path $PSScriptRoot "..\data\metadata.json"
$featuresPath = Join-Path $PSScriptRoot "..\data\features.json"
$processedPath = Join-Path $PSScriptRoot "..\data\processed.json"

Write-Host "Loading metadata from: $metadataPath"
$metadata = Get-Content $metadataPath -Raw | ConvertFrom-Json

Write-Host "Loading features from: $featuresPath"
$features = Get-Content $featuresPath -Raw | ConvertFrom-Json

Write-Host "Loading processed URLs from: $processedPath"
$processed = Get-Content $processedPath -Raw | ConvertFrom-Json

# Function to remove anchor from URL
function Remove-UrlAnchor {
    param([string]$url)
    if ($url -match '^([^#]+)') {
        return $matches[1]
    }
    return $url
}

# Function to determine type from URL
function Get-UrlType {
    param([string]$url, [string]$ideId)
    
    # Check if it's a GitHub changelog
    if ($url -match 'github\.blog/changelog') {
        return "github-changelog"
    }
    
    # Find matching IDE by id
    $ide = $metadata.ides | Where-Object { $_.id -eq $ideId }
    if ($ide) {
        return $ideId
    }
    
    return "unknown"
}

# Collect all unique URLs from features (without anchors)
Write-Host ""
Write-Host "Collecting URLs from features..." -ForegroundColor Cyan
$featureUrls = @{}  # Dictionary to track URL -> IDE ID mapping

foreach ($feature in $features.features) {
    if ($feature.availability) {
        foreach ($ideId in $feature.availability.PSObject.Properties.Name) {
            $avail = $feature.availability.$ideId
            if ($avail.url) {
                $cleanUrl = Remove-UrlAnchor -url $avail.url
                if (-not $featureUrls.ContainsKey($cleanUrl)) {
                    $featureUrls[$cleanUrl] = $ideId
                }
            }
        }
    }
}

Write-Host "Found $($featureUrls.Count) unique URLs in features" -ForegroundColor Cyan

# Collect processed URLs (without anchors)
$processedUrls = @()
foreach ($item in $processed.processed) {
    $cleanUrl = Remove-UrlAnchor -url $item.url
    $processedUrls += $cleanUrl
}

Write-Host "Found $($processedUrls.Count) URLs in processed.json" -ForegroundColor Cyan

# Find missing URLs
$missingUrls = @()
foreach ($url in $featureUrls.Keys) {
    if ($processedUrls -notcontains $url) {
        $missingUrls += @{
            url = $url
            ideId = $featureUrls[$url]
        }
    }
}

# Add missing URLs to processed.json
if ($missingUrls.Count -gt 0) {
    Write-Host ""
    Write-Host "Found $($missingUrls.Count) missing URL(s) in processed.json" -ForegroundColor Yellow
    
    foreach ($missing in $missingUrls) {
        $type = Get-UrlType -url $missing.url -ideId $missing.ideId
        $newEntry = [PSCustomObject]@{
            url = $missing.url
            type = $type
        }
        
        $processed.processed += $newEntry
        Write-Host "  ➕ Added: $($missing.url) (type: $type)" -ForegroundColor Yellow
    }
    
    # Save updated processed.json
    $processed | ConvertTo-Json -Depth 10 | Set-Content $processedPath -Encoding UTF8
    Write-Host ""
    Write-Host "✅ Updated processed.json with $($missingUrls.Count) new URL(s)" -ForegroundColor Green
    exit 0
} else {
    Write-Host ""
    Write-Host "✅ All URLs from features.json are present in processed.json" -ForegroundColor Green
    exit 0
}
