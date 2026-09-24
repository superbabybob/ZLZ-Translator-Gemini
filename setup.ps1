$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = (Get-Item $PSScriptRoot).FullName

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ZLZ-translator (Gemini-version): Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Detect Python
$pyExe = $null
$pyArgs = @()

# Check py -3
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $ver = & py -3 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $pyExe = "py"
        $pyArgs = @("-3")
    }
}

# Check python
if (-not $pyExe -and (Get-Command "python" -ErrorAction SilentlyContinue)) {
    $ver = & python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $pyExe = "python"
        $pyArgs = @()
    }
}

# Check standard installation paths
if (-not $pyExe) {
    $paths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:ProgramFiles\Python3*\python.exe"
    )
    foreach ($p in $paths) {
        $found = Get-Item $p -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $pyExe = $found.FullName
            $pyArgs = @()
            break
        }
    }
}

# If Python is not found
if (-not $pyExe) {
    Write-Host "[!] Python was not found on this computer." -ForegroundColor Yellow
    $hasWinget = Get-Command "winget" -ErrorAction SilentlyContinue
    if ($hasWinget) {
        Write-Host "winget package manager is available. We can install Python 3.12 automatically." -ForegroundColor Green
        $ans = Read-Host "Install Python 3.12 automatically via winget? [Y/n]"
        if ($ans -ne "n" -and $ans -ne "N") {
            Write-Host "Downloading and installing Python 3.12 via winget..." -ForegroundColor Cyan
            & winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
            Write-Host ""
            Write-Host "[!] Installation finished. Please close this window and run setup.bat again to refresh PATH." -ForegroundColor Yellow
            Read-Host "Press Enter to exit..."
            exit 0
        }
    }
    
    Write-Host "Opening python.org download page in browser..." -ForegroundColor Cyan
    try {
        Start-Process "https://www.python.org/downloads/"
    } catch {}
    Write-Host "Please install Python 3.11 or newer and check 'Add python.exe to PATH' before clicking Install." -ForegroundColor Yellow
    Write-Host "Then run setup.bat again." -ForegroundColor Yellow
    Read-Host "Press Enter to exit..."
    exit 1
}

# 2. Create Virtual Environment (.venv)
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "[1/4] Creating virtual environment (.venv)..." -ForegroundColor Cyan
    & $pyExe @pyArgs -m venv (Join-Path $root ".venv")
    if (-not (Test-Path $venvPy)) {
        Write-Host "[!] Failed to create .venv. Please ensure Python 3.11+ is properly installed." -ForegroundColor Red
        Read-Host "Press Enter to exit..."
        exit 1
    }
    Write-Host "[1/4] Virtual environment created successfully!" -ForegroundColor Green
} else {
    Write-Host "[1/4] Virtual environment (.venv) found." -ForegroundColor Green
}

# 3. Install Dependencies
Write-Host "[2/4] Installing required packages..." -ForegroundColor Cyan
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Failed to install packages. Please check your internet connection." -ForegroundColor Red
    Read-Host "Press Enter to exit..."
    exit 1
}
Write-Host "[2/4] Packages installed successfully!" -ForegroundColor Green

# 4. Prepare .env file
$envFile = Join-Path $root ".env"
$envExample = Join-Path $root ".env.example"
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
}

Write-Host ""
Write-Host "[3/4] Checking Gemini API Key:" -ForegroundColor Cyan

# Check if GEMINI_API_KEY already exists
$currentKey = ""
if (Test-Path $envFile) {
    $line = Get-Content $envFile | Where-Object { $_ -match '^GEMINI_API_KEY\s*=\s*(.+)$' }
    if ($line) {
        $currentKey = $Matches[1].Trim()
    }
}

if (-not $currentKey) {
    Write-Host "GEMINI_API_KEY is not configured yet." -ForegroundColor Yellow
    Write-Host "(Get a free key at https://aistudio.google.com/apikey)" -ForegroundColor Gray
    Write-Host ""
    $inputKey = Read-Host "Paste your GEMINI_API_KEY here (or press Enter to skip and configure in GUI later)"
    if ($inputKey.Trim()) {
        & $venvPy -c "import pathlib; from core.config import set_env_value; set_env_value(pathlib.Path(r'''$root'''), 'GEMINI_API_KEY', r'''$($inputKey.Trim())''')"
        Write-Host "[OK] GEMINI_API_KEY saved successfully!" -ForegroundColor Green
    }
} else {
    Write-Host "[OK] GEMINI_API_KEY found." -ForegroundColor Green
}

# 5. Create Desktop Shortcut
Write-Host ""
Write-Host "[4/4] Desktop Shortcut:" -ForegroundColor Cyan
$createLnk = Read-Host "Create a shortcut on Desktop? [Y/n]"
if ($createLnk -ne "n" -and $createLnk -ne "N") {
    try {
        $desktop = $null
        try {
            $regDesktop = Get-ItemPropertyValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" -Name Desktop -ErrorAction Stop
            $desktop = [System.Environment]::ExpandEnvironmentVariables($regDesktop)
        } catch {}
        if (-not $desktop -or -not (Test-Path $desktop)) {
            $desktop = [Environment]::GetFolderPath("Desktop")
        }

        $tempLnk = Join-Path $root "ZLZ-translator (Gemini-version).lnk"
        $ws = New-Object -ComObject WScript.Shell
        $s = $ws.CreateShortcut($tempLnk)
        $s.TargetPath = Join-Path $root "run_hotkey.bat"
        $s.WorkingDirectory = $root
        $s.Description = "ZLZ-translator (Gemini-version)"
        $s.Save()

        if ($desktop -and (Test-Path $desktop)) {
            $destLnk = Join-Path $desktop "ZLZ-translator (Gemini-version).lnk"
            Copy-Item -Path $tempLnk -Destination $destLnk -Force
            Remove-Item -Force $tempLnk -ErrorAction SilentlyContinue
            $oldLnk = Join-Path $desktop "Discord Translator.lnk"
            if (Test-Path $oldLnk) { Remove-Item -Force $oldLnk -ErrorAction SilentlyContinue }
            Write-Host "[OK] Desktop shortcut created successfully!" -ForegroundColor Green
        } else {
            Write-Host "[OK] Shortcut created in project folder." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[!] Could not create Desktop shortcut automatically ($($_.Exception.Message))" -ForegroundColor Yellow
        Write-Host "You can right-click 'run_hotkey.bat' and select 'Send to > Desktop'." -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Setup completed successfully!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

$startNow = Read-Host "Start program now? [Y/n]"
if ($startNow -ne "n" -and $startNow -ne "N") {
    $pyw = Join-Path $root ".venv\Scripts\pythonw.exe"
    Start-Process $pyw -ArgumentList "-m hotkey.app" -WorkingDirectory $root
    Write-Host ""
    Write-Host "[OK] Program started (blue icon located in System Tray at bottom-right of screen)." -ForegroundColor Green
    Start-Sleep -Seconds 3
    exit 0
}

Write-Host "Double-click 'run_hotkey.bat' or Desktop shortcut anytime to use." -ForegroundColor Gray
Read-Host "Press Enter to exit..."
