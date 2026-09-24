$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = (Get-Item $PSScriptRoot).FullName

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ZLZ-translator (Gemini-version): ติดตั้งครั้งแรก" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. ตรวจหา Python
$pyExe = $null
$pyArgs = @()

# ลองเช็ก py -3
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $ver = & py -3 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $pyExe = "py"
        $pyArgs = @("-3")
    }
}

# ลองเช็ก python
if (-not $pyExe -and (Get-Command "python" -ErrorAction SilentlyContinue)) {
    $ver = & python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $pyExe = "python"
        $pyArgs = @()
    }
}

# ลองหาตามโฟลเดอร์มาตรฐาน
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

# ถ้าไม่พบ Python
if (-not $pyExe) {
    Write-Host "[!] ไม่พบ Python บนเครื่องนี้" -ForegroundColor Yellow
    $hasWinget = Get-Command "winget" -ErrorAction SilentlyContinue
    if ($hasWinget) {
        Write-Host "พบระบบ winget ในเครื่อง สามารถติดตั้ง Python 3.12 ให้อัตโนมัติได้" -ForegroundColor Green
        $ans = Read-Host "ต้องการให้ติดตั้ง Python 3.12 ให้อัตโนมัติเลยหรือไม่? [Y/n]"
        if ($ans -ne "n" -and $ans -ne "N") {
            Write-Host "กำลังดาวน์โหลดและติดตั้ง Python 3.12 ผ่าน winget..." -ForegroundColor Cyan
            & winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
            Write-Host ""
            Write-Host "[!] ติดตั้งเสร็จแล้ว กรุณาปิดหน้าต่างนี้แล้วเปิดใหม่อีกครั้งเพื่อให้ Windows โหลด PATH ใหม่" -ForegroundColor Yellow
            Read-Host "กด Enter เพื่อปิดหน้าต่าง..."
            exit 0
        }
    }
    
    Write-Host "กำลังเปิดหน้าเว็บ python.org เพื่อดาวน์โหลด..." -ForegroundColor Cyan
    try {
        Start-Process "https://www.python.org/downloads/"
    } catch {}
    Write-Host "กรุณาติดตั้ง Python 3.11 ขึ้นไป แล้ว **อย่าลืมติ๊ก Add python.exe to PATH** ก่อนกด Install" -ForegroundColor Yellow
    Write-Host "จากนั้นค่อยรันไฟล์นี้ใหม่อีกครั้ง" -ForegroundColor Yellow
    Read-Host "กด Enter เพื่อปิด..."
    exit 1
}

# 2. สร้าง Virtual Environment (.venv)
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "[1/4] กำลังสร้าง virtual environment (.venv)..." -ForegroundColor Cyan
    & $pyExe @pyArgs -m venv (Join-Path $root ".venv")
    if (-not (Test-Path $venvPy)) {
        Write-Host "[!] สร้าง .venv ไม่สำเร็จ กรุณาตรวจสอบว่าติดตั้ง Python 3.11 ขึ้นไปอย่างสมบูรณ์" -ForegroundColor Red
        Read-Host "กด Enter เพื่อปิด..."
        exit 1
    }
    Write-Host "[1/4] สร้าง virtual environment (.venv) สำเร็จ!" -ForegroundColor Green
} else {
    Write-Host "[1/4] พบ virtual environment (.venv) เรียบร้อย" -ForegroundColor Green
}

# 3. ติดตั้ง Dependencies
Write-Host "[2/4] กำลังติดตั้งไลบรารีที่จำเป็น..." -ForegroundColor Cyan
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] ติดตั้งไลบรารีไม่สำเร็จ กรุณาตรวจสอบการเชื่อมต่ออินเทอร์เน็ต" -ForegroundColor Red
    Read-Host "กด Enter เพื่อปิด..."
    exit 1
}
Write-Host "[2/4] ติดตั้งไลบรารีสำเร็จเรียบร้อย" -ForegroundColor Green

# 4. เตรียมไฟล์ .env
$envFile = Join-Path $root ".env"
$envExample = Join-Path $root ".env.example"
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
}

Write-Host ""
Write-Host "[3/4] ตรวจสอบ API Key:" -ForegroundColor Cyan

# ตรวจว่ามี GEMINI_API_KEY หรือยัง
$currentKey = ""
if (Test-Path $envFile) {
    $line = Get-Content $envFile | Where-Object { $_ -match '^GEMINI_API_KEY\s*=\s*(.+)$' }
    if ($line) {
        $currentKey = $Matches[1].Trim()
    }
}

if (-not $currentKey) {
    Write-Host "ยังไม่ได้ใส่ GEMINI_API_KEY" -ForegroundColor Yellow
    Write-Host "(สามารถขอรับคีย์ฟรีได้ที่ https://aistudio.google.com/apikey)" -ForegroundColor Gray
    Write-Host ""
    $inputKey = Read-Host "วาง GEMINI_API_KEY ของคุณตรงนี้ (หรือกด Enter เพื่อข้ามไปใส่ในโปรแกรม)"
    if ($inputKey.Trim()) {
        & $venvPy -c "import pathlib; from core.config import set_env_value; set_env_value(pathlib.Path(r'''$root'''), 'GEMINI_API_KEY', r'''$($inputKey.Trim())''')"
        Write-Host "[OK] บันทึก GEMINI_API_KEY เรียบร้อยแล้ว!" -ForegroundColor Green
    }
} else {
    Write-Host "[OK] พบ GEMINI_API_KEY ในระบบเรียบร้อย" -ForegroundColor Green
}

# 5. สร้าง Shortcut บน Desktop
Write-Host ""
Write-Host "[4/4] ทางลัดบนหน้าจอ:" -ForegroundColor Cyan
$createLnk = Read-Host "ต้องการสร้าง Shortcut บนหน้า Desktop หรือไม่? [Y/n]"
if ($createLnk -ne "n" -and $createLnk -ne "N") {
    try {
        # ค้นหาตำแหน่ง Desktop (รองรับทั้งภาษาอังกฤษ และโฟลเดอร์ OneDrive เช่น 'เดสก์ท็อป')
        $desktop = $null
        try {
            $regDesktop = Get-ItemPropertyValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" -Name Desktop -ErrorAction Stop
            $desktop = [System.Environment]::ExpandEnvironmentVariables($regDesktop)
        } catch {}
        if (-not $desktop -or -not (Test-Path $desktop)) {
            $desktop = [Environment]::GetFolderPath("Desktop")
        }

        # สร้างไฟล์ shortcut ชั่วคราวใน $root ก่อน เพื่อไม่ให้ COM พังตอนเจอชื่อโฟลเดอร์ภาษาไทย
        $tempLnk = Join-Path $root "ZLZ-translator (Gemini-version).lnk"
        $ws = New-Object -ComObject WScript.Shell
        $s = $ws.CreateShortcut($tempLnk)
        $s.TargetPath = Join-Path $root "run_hotkey.bat"
        $s.WorkingDirectory = $root
        $s.Description = "ZLZ-translator (Gemini-version)"
        $s.Save()

        # ใช้ Copy-Item ของ PowerShell คัดลอกไปยัง Desktop (รองรับภาษาไทย 100%)
        if ($desktop -and (Test-Path $desktop)) {
            $destLnk = Join-Path $desktop "ZLZ-translator (Gemini-version).lnk"
            Copy-Item -Path $tempLnk -Destination $destLnk -Force
            Remove-Item -Force $tempLnk -ErrorAction SilentlyContinue
            # ลบ shortcut ชื่อเดิมหากมี
            $oldLnk = Join-Path $desktop "Discord Translator.lnk"
            if (Test-Path $oldLnk) { Remove-Item -Force $oldLnk -ErrorAction SilentlyContinue }
            Write-Host "[OK] สร้าง Shortcut 'ZLZ-translator (Gemini-version)' บนหน้า Desktop เรียบร้อยแล้ว!" -ForegroundColor Green
        } else {
            Write-Host "[OK] สร้าง Shortcut ไว้ในโฟลเดอร์โปรเจกต์เรียบร้อย (สามารถลากไปวางบน Desktop ได้เอง)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[!] ไม่สามารถสร้าง Shortcut บน Desktop ได้อัตโนมัติ ($($_.Exception.Message))" -ForegroundColor Yellow
        Write-Host "คุณสามารถคลิกขวาที่ไฟล์ run_hotkey.bat แล้วเลือก 'Send to > Desktop' ได้เองครับ" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  ติดตั้งเสร็จสมบูรณ์เรียบร้อย!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

$startNow = Read-Host "ต้องการเปิดใช้งานโปรแกรมทันทีหรือไม่? [Y/n]"
if ($startNow -ne "n" -and $startNow -ne "N") {
    $pyw = Join-Path $root ".venv\Scripts\pythonw.exe"
    Start-Process $pyw -ArgumentList "-m hotkey.app" -WorkingDirectory $root
    Write-Host ""
    Write-Host "[OK] เปิดโปรแกรมแล้ว (ไอคอนสีน้ำเงินจะอยู่ที่ System Tray มุมขวาล่างของจอ)" -ForegroundColor Green
    Start-Sleep -Seconds 3
    exit 0
}

Write-Host "ดับเบิลคลิก run_hotkey.bat หรือ Shortcut บน Desktop เมื่อต้องการใช้งาน" -ForegroundColor Gray
Read-Host "กด Enter เพื่อเสร็จสิ้น..."
