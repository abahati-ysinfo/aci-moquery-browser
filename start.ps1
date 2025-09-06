# ACI Moquery Log Browser - Windows PowerShell Setup & Start Script
# This script automates the complete setup and launch process

param(
    [switch]$SkipPrereqCheck,
    [switch]$DevMode
)

Write-Host "ACI Moquery Log Browser - Automated Setup & Launch" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan

# Function to check if a command exists
function Test-Command {
    param($Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

# Function to get version of a command
function Get-CommandVersion {
    param($Command, $VersionArg = "--version")
    try {
        $output = & $Command $VersionArg 2>$null
        return $output[0]
    } catch {
        return "Unknown"
    }
}

# Check prerequisites
if (-not $SkipPrereqCheck) {
    Write-Host "Checking prerequisites..." -ForegroundColor Yellow
    
    $missingPrereqs = @()
    
    # Check Python
    if (Test-Command "python") {
        $pythonVersion = Get-CommandVersion "python" "--version"
        Write-Host "[OK] Python found: $pythonVersion" -ForegroundColor Green
    } elseif (Test-Command "python3") {
        $pythonVersion = Get-CommandVersion "python3" "--version"
        Write-Host "[OK] Python3 found: $pythonVersion" -ForegroundColor Green
        # Create alias for consistency
        Set-Alias python python3
    } else {
        $missingPrereqs += "Python 3.11+"
        Write-Host "[ERROR] Python not found" -ForegroundColor Red
    }
    
    # Check Node.js
    if (Test-Command "node") {
        $nodeVersion = Get-CommandVersion "node" "--version"
        Write-Host "[OK] Node.js found: $nodeVersion" -ForegroundColor Green
    } else {
        $missingPrereqs += "Node.js 20+"
        Write-Host "[ERROR] Node.js not found" -ForegroundColor Red
    }
    
    # Check npm
    if (Test-Command "npm") {
        $npmVersion = Get-CommandVersion "npm" "--version"
        Write-Host "[OK] npm found: $npmVersion" -ForegroundColor Green
    } else {
        $missingPrereqs += "npm"
        Write-Host "[ERROR] npm not found" -ForegroundColor Red
    }
    
    # Check Poetry
    if (Test-Command "poetry") {
        $poetryVersion = Get-CommandVersion "poetry" "--version"
        Write-Host "[OK] Poetry found: $poetryVersion" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Poetry not found - attempting to install..." -ForegroundColor Yellow
        try {
            Invoke-RestMethod -Uri https://install.python-poetry.org | python -
            $env:PATH = $env:PATH + ";" + $env:APPDATA + "\Python\Scripts"
            if (Test-Command "poetry") {
                Write-Host "[OK] Poetry installed successfully" -ForegroundColor Green
            } else {
                $missingPrereqs += "Poetry (manual install required)"
            }
        } catch {
            $missingPrereqs += "Poetry (auto-install failed)"
            Write-Host "[ERROR] Poetry auto-install failed" -ForegroundColor Red
        }
    }
    
    if ($missingPrereqs.Count -gt 0) {
        Write-Host ""
        Write-Host "[ERROR] Missing prerequisites:" -ForegroundColor Red
        foreach ($prereq in $missingPrereqs) {
            Write-Host "   - $prereq" -ForegroundColor Red
        }
        Write-Host ""
        Write-Host "Please install the missing prerequisites and run this script again." -ForegroundColor Yellow
        Write-Host "Or use -SkipPrereqCheck to bypass this check." -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "[OK] All prerequisites found!" -ForegroundColor Green
}

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host ""
Write-Host "Setting up backend dependencies..." -ForegroundColor Yellow
Set-Location "backend"

# Check if poetry.lock exists, if not run install
if (-not (Test-Path "poetry.lock")) {
    Write-Host "Installing backend dependencies (first time setup)..." -ForegroundColor Cyan
    poetry install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Backend dependency installation failed!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Backend dependencies already installed, checking for updates..." -ForegroundColor Cyan
    poetry install --only=main
}

Set-Location ".."

Write-Host ""
Write-Host "Setting up frontend dependencies..." -ForegroundColor Yellow
Set-Location "frontend"

# Check if node_modules exists, if not run install
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies (first time setup)..." -ForegroundColor Cyan
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Frontend dependency installation failed!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Frontend dependencies already installed, checking for updates..." -ForegroundColor Cyan
    npm install --no-audit
}

Set-Location ".."

Write-Host ""
Write-Host "Starting ACI Moquery Log Browser..." -ForegroundColor Green

# Create data directory if it doesn't exist
if (-not (Test-Path "data")) {
    New-Item -ItemType Directory -Path "data" | Out-Null
    Write-Host "Created data directory" -ForegroundColor Cyan
}

# Start backend in background
Write-Host "Starting backend server..." -ForegroundColor Cyan
Set-Location "backend"

$backendJob = Start-Job -ScriptBlock {
    param($BackendPath)
    Set-Location $BackendPath
    poetry run fastapi dev app/main.py --port 9000
} -ArgumentList (Get-Location)

Set-Location ".."

# Wait a moment for backend to start
Write-Host "Waiting for backend to initialize..." -ForegroundColor Cyan
Start-Sleep -Seconds 3

# Check if backend is running
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:9000/api/config" -TimeoutSec 5 -UseBasicParsing
    Write-Host "[OK] Backend server is running on http://127.0.0.1:9000" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Backend may still be starting up..." -ForegroundColor Yellow
}

# Always start frontend in development mode on separate port
Write-Host "Starting frontend development server..." -ForegroundColor Cyan
Set-Location "frontend"

$frontendJob = Start-Job -ScriptBlock {
    param($FrontendPath)
    Set-Location $FrontendPath
    npm run dev -- --port 3000
} -ArgumentList (Get-Location)

Set-Location ".."

# Wait for frontend to start
Write-Host "Waiting for frontend to initialize..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

# Frontend runs on port 3000
$frontendUrl = "http://localhost:3000"
Write-Host "[OK] Frontend development server starting on $frontendUrl" -ForegroundColor Green

# Wait a bit more and then open browser
Write-Host "Opening browser..." -ForegroundColor Cyan
Start-Sleep -Seconds 2

try {
    Start-Process $frontendUrl
    Write-Host "[OK] Browser opened to $frontendUrl" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Could not auto-open browser. Please manually navigate to: $frontendUrl" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "ACI Moquery Log Browser is now running!" -ForegroundColor Green
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "Frontend URL: $frontendUrl" -ForegroundColor Cyan
Write-Host "Backend URL: http://127.0.0.1:9000" -ForegroundColor Cyan
Write-Host "API Documentation: http://127.0.0.1:9000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Usage:" -ForegroundColor White
Write-Host "   1. Open frontend at http://localhost:3000" -ForegroundColor White
Write-Host "   2. Upload moquery files (.txt, .log, .7z, .zip, .tar.gz)" -ForegroundColor White
Write-Host "   3. Browse detected ACI classes in the sidebar" -ForegroundColor White
Write-Host "   4. View object details and export data" -ForegroundColor White
Write-Host ""
Write-Host "To stop: Press Ctrl+C in this window" -ForegroundColor Yellow

Write-Host ""
Write-Host "Development Mode Active" -ForegroundColor Magenta
Write-Host "   - Frontend: http://localhost:3000 (Hot-reload enabled)" -ForegroundColor White
Write-Host "   - Backend: http://127.0.0.1:9000 (Auto-reload enabled)" -ForegroundColor White

# Keep script running and monitor jobs
try {
    Write-Host ""
Write-Host "Press Ctrl+C to stop all servers..." -ForegroundColor Yellow
    
    while ($true) {
        Start-Sleep -Seconds 1
        
        # Check if backend job is still running
        if ($backendJob.State -eq "Failed" -or $backendJob.State -eq "Stopped") {
            Write-Host ""
            Write-Host "[ERROR] Backend server stopped unexpectedly!" -ForegroundColor Red
            if ($frontendJob) {
                Stop-Job $frontendJob -ErrorAction SilentlyContinue
                Remove-Job $frontendJob -ErrorAction SilentlyContinue
            }
            break
        }
        
        # Check frontend job
        if ($frontendJob -and ($frontendJob.State -eq "Failed" -or $frontendJob.State -eq "Stopped")) {
            Write-Host ""
            Write-Host "[ERROR] Frontend server stopped unexpectedly!" -ForegroundColor Red
            Stop-Job $backendJob -ErrorAction SilentlyContinue
            Remove-Job $backendJob -ErrorAction SilentlyContinue
            break
        }
    }
} catch {
    Write-Host ""
    Write-Host "Shutting down servers..." -ForegroundColor Yellow
} finally {
    # Cleanup jobs
    if ($backendJob) {
        Stop-Job $backendJob -ErrorAction SilentlyContinue
        Remove-Job $backendJob -ErrorAction SilentlyContinue
    }
    if ($frontendJob) {
        Stop-Job $frontendJob -ErrorAction SilentlyContinue
        Remove-Job $frontendJob -ErrorAction SilentlyContinue
    }
    Write-Host "[OK] All servers stopped. Thank you for using ACI Moquery Log Browser!" -ForegroundColor Green
}
