<#
.SYNOPSIS
    ChatGPT Skills 업로드용 스킬별 zip을 생성한다.

.DESCRIPTION
    OpenAI Skills 규격상 zip 하나에는 "단일 최상위 폴더"와 "정확히 하나의 SKILL.md"만
    들어갈 수 있다. 따라서 skills/ 아래 스킬마다 zip을 하나씩 만든다.

    스킬 폴더(gpt/skills/<스킬>)는 자기완결적이다 — references/·assets/가 폴더 안에 있다.
    gpt/skills/ 는 sync_from_claude.py 가 레포 루트의 Claude판에서 만든 사본이므로,
    빌드 전에 sync 를 먼저 돌린다(이 스크립트가 자동으로 실행한다).

    Compress-Archive 는 엔트리 경로에 백슬래시를 넣어 업로드 측에서 폴더 구조가
    깨지므로 쓰지 않고, .NET ZipArchive 로 슬래시 경로를 직접 기록한다.

.PARAMETER OutDir
    산출물 디렉터리. 기본값: ~/Downloads/laighthouse-external-gpt-skills

.PARAMETER Skill
    특정 스킬만 빌드한다. 생략 시 skills/ 아래 전부.

.EXAMPLE
    .\build_skill_zips.ps1
    .\build_skill_zips.ps1 -Skill daily-detailed
#>
[CmdletBinding()]
param(
    [string]$OutDir = (Join-Path $env:USERPROFILE 'Downloads\laighthouse-external-gpt-skills'),
    [string]$Skill
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.IO.Compression | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem | Out-Null

$Root      = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillsDir = Join-Path $Root 'skills'

# zip 에서 제외할 항목 (빌드 부산물)
$ExcludeDirs  = @('__pycache__', '.git', 'node_modules')
$ExcludeFiles = @('.DS_Store', 'Thumbs.db')

# OpenAI Skills 규격 한도
$MaxZipBytes         = 50MB
$MaxFileCount        = 500
$MaxUncompressedFile = 25MB

function Add-Tree {
    # 한 디렉터리 트리를 (zip 엔트리 경로 -> 원본 파일 경로) 쌍으로 펼친다.
    param(
        [Parameter(Mandatory)][string]$BasePath,
        [Parameter(Mandatory)][string]$EntryPrefix,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.ArrayList]$Into
    )

    foreach ($file in (Get-ChildItem -LiteralPath $BasePath -Recurse -File)) {
        if ($ExcludeFiles -contains $file.Name) { continue }
        if ($file.Extension -eq '.pyc') { continue }

        $relative = $file.FullName.Substring($BasePath.Length).TrimStart([char]92, [char]47)
        $segments = $relative -split '[\\/]'

        $skip = $false
        foreach ($segment in $segments) {
            if ($ExcludeDirs -contains $segment) { $skip = $true; break }
        }
        if ($skip) { continue }

        [void]$Into.Add([PSCustomObject]@{
            Entry  = $EntryPrefix + ($segments -join '/')
            Source = $file.FullName
        })
    }
}

function Get-BundleFiles {
    # 스킬 폴더를 zip 에 넣을 파일 목록으로 만든다.
    # 엔트리 경로는 항상 슬래시이며 <skill-name>/ 으로 시작한다.
    param(
        [Parameter(Mandatory)][string]$SkillPath,
        [Parameter(Mandatory)][string]$SkillName
    )

    $pairs = New-Object System.Collections.ArrayList
    Add-Tree -BasePath $SkillPath -EntryPrefix "$SkillName/"        -Into $pairs
    return $pairs
}

function New-SkillZip {
    param(
        [Parameter(Mandatory)][string]$ZipPath,
        [Parameter(Mandatory)][object[]]$Files
    )

    if (Test-Path -LiteralPath $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }

    $stream  = [System.IO.File]::Open($ZipPath, [System.IO.FileMode]::CreateNew)
    $archive = New-Object System.IO.Compression.ZipArchive($stream, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($item in $Files) {
            $entry       = $archive.CreateEntry($item.Entry, [System.IO.Compression.CompressionLevel]::Optimal)
            $entryStream = $entry.Open()
            try {
                $bytes = [System.IO.File]::ReadAllBytes($item.Source)
                $entryStream.Write($bytes, 0, $bytes.Length)
            } finally {
                $entryStream.Dispose()
            }
        }
    } finally {
        $archive.Dispose()
        $stream.Dispose()
    }
}

function Test-SkillZip {
    # 만들어진 zip 을 다시 열어 OpenAI Skills 규격을 검사한다.
    # 위반 사항 목록을 반환한다 (비어 있으면 통과).
    param(
        [Parameter(Mandatory)][string]$ZipPath,
        [Parameter(Mandatory)][string]$SkillName
    )

    $problems = New-Object System.Collections.ArrayList

    $stream  = [System.IO.File]::OpenRead($ZipPath)
    $archive = New-Object System.IO.Compression.ZipArchive($stream, [System.IO.Compression.ZipArchiveMode]::Read)
    try {
        $entries = @($archive.Entries)

        # 1. 엔트리 경로에 백슬래시가 없어야 한다
        $backslash = @($entries | Where-Object { $_.FullName.Contains([char]92) })
        if ($backslash.Count -gt 0) {
            [void]$problems.Add("엔트리 경로에 백슬래시 $($backslash.Count)건")
        }

        # 2. 최상위 폴더가 정확히 하나여야 한다
        $tops = @($entries | ForEach-Object { ($_.FullName -split '/')[0] } | Sort-Object -Unique)
        if ($tops.Count -ne 1) {
            [void]$problems.Add("최상위 폴더가 $($tops.Count)개 ($($tops -join ', '))")
        } elseif ($tops[0] -ne $SkillName) {
            [void]$problems.Add("최상위 폴더 이름이 '$($tops[0])' — '$SkillName' 이어야 함")
        }

        # 3. SKILL.md 가 스킬 루트에 정확히 하나여야 한다 (대소문자 무시)
        $manifests = @($entries | Where-Object { $_.FullName -imatch '(^|/)skill\.md$' })
        if ($manifests.Count -ne 1) {
            [void]$problems.Add("SKILL.md 가 $($manifests.Count)개")
        } elseif ($manifests[0].FullName -ne "$SkillName/SKILL.md") {
            [void]$problems.Add("SKILL.md 위치가 '$($manifests[0].FullName)'")
        }

        # 5. 규격 한도
        if ($entries.Count -gt $MaxFileCount) {
            [void]$problems.Add("파일 수 $($entries.Count)개 > $MaxFileCount")
        }
        $tooBig = @($entries | Where-Object { $_.Length -gt $MaxUncompressedFile })
        if ($tooBig.Count -gt 0) {
            [void]$problems.Add("25MB 초과 파일 $($tooBig.Count)건")
        }

        # 6. 본문이 참조하는 references/·assets/ 경로가 실제로 번들에 있는지
        $entryNames = @{}
        foreach ($e in $entries) { $entryNames[$e.FullName] = $true }

        $textEntries = @($entries | Where-Object { $_.FullName -like '*.md' -or $_.FullName -like '*.py' })
        foreach ($md in $textEntries) {
            $reader = New-Object System.IO.StreamReader($md.Open(), [System.Text.Encoding]::UTF8)
            try { $text = $reader.ReadToEnd() } finally { $reader.Dispose() }

            if (-not $md.FullName.EndsWith('SKILL.md')) { continue }
            foreach ($m in [regex]::Matches($text, '(?<![\w/])(references|assets)/[A-Za-z0-9._-]+\.(md|py|js|css)')) {
                $target = "$SkillName/" + $m.Value
                if (-not $entryNames.ContainsKey($target)) {
                    [void]$problems.Add("$($md.FullName) 이 참조하는 $($m.Value) 가 번들에 없음")
                }
            }
        }
    } finally {
        $archive.Dispose()
        $stream.Dispose()
    }

    return $problems
}

# --- 실행 -------------------------------------------------------------------

if (-not (Test-Path -LiteralPath $SkillsDir)) {
    throw "skills/ 디렉터리를 찾을 수 없습니다: $SkillsDir"
}
# gpt/skills/ 를 Claude판에서 다시 만든다
& python (Join-Path $Root 'sync_from_claude.py')
if ($LASTEXITCODE -ne 0) { throw "sync_from_claude.py 실패" }
if (-not (Test-Path -LiteralPath $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

$skillDirs = @(Get-ChildItem -LiteralPath $SkillsDir -Directory)
if ($Skill) {
    $skillDirs = @($skillDirs | Where-Object { $_.Name -eq $Skill })
    if ($skillDirs.Count -eq 0) { throw "그런 스킬이 없습니다: $Skill" }
}

Write-Host ""
Write-Host "출력 위치: $OutDir"
Write-Host ""

$failed = 0

foreach ($dir in $skillDirs) {
    $name    = $dir.Name
    $zipPath = Join-Path $OutDir "$name.zip"

    $files = @(Get-BundleFiles -SkillPath $dir.FullName -SkillName $name)
    New-SkillZip -ZipPath $zipPath -Files $files

    $problems = @(Test-SkillZip -ZipPath $zipPath -SkillName $name)
    $zipBytes = (Get-Item -LiteralPath $zipPath).Length
    if ($zipBytes -gt $MaxZipBytes) {
        $problems += "zip 이 50MB 를 초과합니다"
    }
    $sizeKB = [math]::Round($zipBytes / 1KB, 1)

    if ($problems.Count -eq 0) {
        Write-Host ("  OK   {0,-20} {1,3} files  {2,8} KB" -f $name, $files.Count, $sizeKB)
    } else {
        $failed++
        Write-Host ("  FAIL {0,-20} {1,3} files  {2,8} KB" -f $name, $files.Count, $sizeKB) -ForegroundColor Red
        foreach ($p in $problems) { Write-Host "       - $p" -ForegroundColor Red }
    }
}

Write-Host ""
if ($failed -gt 0) {
    Write-Host "$failed 개 스킬이 검증에 실패했습니다." -ForegroundColor Red
    exit 1
}

Write-Host "$($skillDirs.Count) 개 스킬 zip 생성 완료."
Write-Host "ChatGPT > Sidebar > Plugins > Skills > Create > Upload from your computer 에서"
Write-Host "각 zip 을 하나씩 업로드하세요."
Write-Host ""
