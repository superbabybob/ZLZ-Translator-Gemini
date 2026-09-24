$root = (Get-Item $PSScriptRoot).FullName
$dist = Join-Path $root "dist"
if (-not (Test-Path $dist)) {
    New-Item -ItemType Directory -Path $dist -ErrorAction SilentlyContinue | Out-Null
}

$zipPath = Join-Path $dist "ZLZ-Translator-Gemini-Release.zip"
if (Test-Path $zipPath) {
    try {
        [System.IO.File]::Delete($zipPath)
    } catch {
        # ignore if locked
    }
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)

$includes = @(
    "core", "hotkey", "discord_app", "tests",
    ".env.example", ".gitignore", "config.toml", "glossary.md",
    "README.md", "SETUP_GUIDE.md", "FRIEND_GUIDE.md", "requirements.txt",
    "run_all.bat", "run_discord.bat", "run_hotkey.bat", "setup.bat", "setup.ps1", "make_release.bat", "make_release.ps1", "make_share_zip.py"
)

foreach ($item in $includes) {
    $fullPath = Join-Path $root $item
    if (Test-Path $fullPath -PathType Leaf) {
        $entryName = "ZLZ-Translator-Gemini/$item"
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $fullPath, $entryName, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
    } elseif (Test-Path $fullPath -PathType Container) {
        Get-ChildItem -Path $fullPath -Recurse -File | ForEach-Object {
            $f = $_.FullName
            if ($f -notmatch '\\(__pycache__|\.venv|data|dist|\.git)\\' -and $_.Extension -ne '.pyc') {
                $rel = $f.Substring($root.Length + 1).Replace('\', '/')
                $entryName = "ZLZ-Translator-Gemini/$rel"
                [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $f, $entryName, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
            }
        }
    }
}

$zip.Dispose()
[System.GC]::Collect()
[System.GC]::WaitForPendingFinalizers()

$file = Get-Item $zipPath
Write-Host "Created release package: $($file.FullName) ($([math]::Round($file.Length / 1KB, 1)) KB)"
