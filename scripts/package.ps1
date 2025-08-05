#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Scribed packaging script for Windows
.DESCRIPTION
    This script helps build and test Scribed packages on Windows systems.
.PARAMETER Action
    The action to perform: python, test, windows, source, or all
.EXAMPLE
    .\scripts\package.ps1 all
#>

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("python", "test", "windows", "source", "all")]
    [string]$Action = ""
)

function Write-Header {
    param([string]$Title)
    Write-Host "=" * 50 -ForegroundColor Cyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host "=" * 50 -ForegroundColor Cyan
}

function Invoke-Command-Safe {
    param([string]$Command)
    Write-Host "Running: $Command" -ForegroundColor Yellow
    $result = Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Command failed: $Command" -ForegroundColor Red
        exit 1
    }
    return $result
}

function Build-PythonPackages {
    Write-Header "Building Python packages..."
    
    # Clean previous builds
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    
    # Install build dependencies
    Invoke-Command-Safe "python -m pip install build twine"
    
    # Build packages
    Invoke-Command-Safe "python -m build"
    
    Write-Host "✅ Python packages built successfully!" -ForegroundColor Green
    Write-Host "Files created:" -ForegroundColor Green
    Get-ChildItem "dist" | ForEach-Object { Write-Host "  - dist/$($_.Name)" -ForegroundColor Green }
}

function Test-PythonPackages {
    Write-Header "Testing Python packages..."
    
    # Check package integrity
    Invoke-Command-Safe "twine check dist/*"
    
    Write-Host "✅ Package checks passed!" -ForegroundColor Green
}

function Build-WindowsExecutable {
    Write-Header "Building Windows executable..."
    
    # Install PyInstaller
    Invoke-Command-Safe "python -m pip install pyinstaller"
    
    # Build executable
    Invoke-Command-Safe "pyinstaller --onefile --name scribed src/scribed/cli.py --hidden-import=scribed"
    
    Write-Host "✅ Windows executable built successfully!" -ForegroundColor Green
    Write-Host "Executable: dist/scribed.exe" -ForegroundColor Green
}

function New-SourceArchive {
    Write-Header "Creating source archive..."
    
    # Get version
    $version = "dev"
    try {
        $gitTag = git describe --tags --abbrev=0 2>$null
        if ($gitTag) {
            $version = $gitTag -replace "^v", ""
        }
    } catch {}
    
    $archiveName = "scribed-$version-source.zip"
    
    # Create zip archive
    $exclude = @(".*", "__pycache__", "build", "dist", "node_modules", "*.pyc")
    Get-ChildItem -Recurse | Where-Object {
        $include = $true
        foreach ($pattern in $exclude) {
            if ($_.Name -like $pattern -or $_.FullName -like "*\$pattern\*") {
                $include = $false
                break
            }
        }
        $include
    } | Compress-Archive -DestinationPath $archiveName -Force
    
    Write-Host "✅ Source archive created: $archiveName" -ForegroundColor Green
}

function Show-Usage {
    Write-Host "🚀 Scribed Windows Packaging Script" -ForegroundColor Cyan
    Write-Host "=" * 50 -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Available actions:" -ForegroundColor Yellow
    Write-Host "  python    - Build Python packages" -ForegroundColor White
    Write-Host "  test      - Test Python packages" -ForegroundColor White
    Write-Host "  windows   - Build Windows executable" -ForegroundColor White
    Write-Host "  source    - Create source archive" -ForegroundColor White
    Write-Host "  all       - Do everything" -ForegroundColor White
    Write-Host ""
    Write-Host "Usage: .\scripts\package.ps1 <action>" -ForegroundColor Yellow
}

# Main script
if (-not $Action) {
    Show-Usage
    exit 0
}

Write-Host "🚀 Scribed Windows Packaging Script" -ForegroundColor Cyan

switch ($Action) {
    "python" { Build-PythonPackages }
    "test" { Test-PythonPackages }
    "windows" { Build-WindowsExecutable }
    "source" { New-SourceArchive }
    "all" {
        Build-PythonPackages
        Test-PythonPackages
        Build-WindowsExecutable
        New-SourceArchive
    }
}

Write-Host ""
Write-Host "🎉 Packaging complete!" -ForegroundColor Green
