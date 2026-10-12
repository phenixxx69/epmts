# Prepares and starts EPMTS (Windows). Called by quickstart.cmd.
# Usage: setup.ps1 [home|editor|server] [pack folder]   (default: home)
# Checks Python 3.9+ (with tkinter) and ffmpeg, offers to download what is missing, keeps a
# private Python environment in .venv\, then starts the tool. No param block on purpose:
# PowerShell would read "--options" as its own parameters.
$Target = 'home'
$ToolArguments = @($args)
if ($ToolArguments.Count -gt 0 -and $ToolArguments[0] -in 'home', 'editor', 'server') {
    $Target = $ToolArguments[0]
    $ToolArguments = @($ToolArguments | Select-Object -Skip 1)
}
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Venv = Join-Path $Root '.venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
# Two series: a Python is always installed beside the user's, never over another of its series.
$PythonInstallers = @{ '3.12' = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'; '3.13' = 'https://www.python.org/ftp/python/3.13.9/python-3.13.9-amd64.exe' }
$FfmpegUrl = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
$Requirements = Join-Path $Root 'tools\python\requirements.txt'
$Scripts = @{ home = 'tools\python\home\epmts_home.py'; editor = 'tools\python\editor\epmts_editor.py'; server = 'tools\python\server\epmts_server.py' }
$Script = Join-Path $Root $Scripts[$Target]

# Asks a yes/no question.
function Confirm-Step([string]$Question) {
    $answer = Read-Host "$Question [y/N]"
    return $answer -match '^[yYoO]'
}

# Runs a command quietly and returns its standard output, or $null when it fails. Windows
# PowerShell 5.1 turns a native command's stderr into a terminating error under 'Stop'.
function Invoke-Quiet([string]$FilePath, [string[]]$Arguments) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & $FilePath @Arguments 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        return ($output -join "`n").Trim()
    } catch {
        return $null
    } finally {
        $ErrorActionPreference = $previous
    }
}

# Lists the python.exe of every Python 3.9+ found (the Microsoft Store alias is ignored).
function Get-PythonCandidates {
    $launchers = @()
    $pyLauncher = Get-Command 'py' -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $listing = Invoke-Quiet $pyLauncher.Source @('-0p')
        if ($listing) {
            $launchers += [regex]::Matches($listing, '[A-Za-z]:\\[^\r\n*]*?python\.exe') | ForEach-Object { $_.Value.Trim() }
        }
    }
    $command = Get-Command 'python' -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notlike '*WindowsApps*') { $launchers += $command.Source }
    $launchers += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
    $found = @()
    foreach ($launcher in $launchers) {
        $path = Invoke-Quiet $launcher @('-c', "import sys; print(sys.executable if sys.version_info >= (3, 9) else '')")
        if ($path -and $found -notcontains $path) { $found += $path }
    }
    return $found
}

# Tells whether a Python can import tkinter (the window toolkit, from tcl/tk).
function Test-Tk([string]$Python) {
    return $null -ne (Invoke-Quiet $Python @('-c', 'import tkinter; print(1)'))
}

# Returns the first Python 3.9+, with tkinter when $NeedTk, or $null.
function Find-Python([bool]$NeedTk) {
    foreach ($candidate in Get-PythonCandidates) {
        if (-not $NeedTk -or (Test-Tk $candidate)) { return $candidate }
    }
    return $null
}

# Adds tcl/tk to an installed Python by running the python.org installer of the same version in
# "modify" mode. Returns $true when tkinter works afterwards.
function Repair-Tk([string]$Python) {
    # Python code without double quotes: Windows PowerShell 5.1 mangles them in native arguments.
    $code = "import json, platform, sys; v = sys.version_info; arch = 'arm64' if platform.machine().upper() == 'ARM64' else ('amd64' if sys.maxsize > 2**32 else ''); print(json.dumps({'version': '%d.%d.%d' % v[:3], 'final': v.releaselevel == 'final', 'arch': arch, 'prefix': sys.base_prefix}))"
    $info = Invoke-Quiet $Python @('-c', $code)
    if (-not $info) { return $false }
    $info = $info | ConvertFrom-Json
    Write-Host ''
    Write-Host "Your Python $($info.version) has no tcl/tk, which the EPMTS windows need."
    if (-not $info.final -or $info.prefix -like '*WindowsApps*') {
        Write-Host 'This Python cannot be repaired automatically.'
        return $false
    }
    $allUsers = ($env:ProgramFiles -and $info.prefix -like "$env:ProgramFiles*") -or ($env:ProgramW6432 -and $info.prefix -like "$env:ProgramW6432*")
    $question = "Download the Python $($info.version) installer from python.org and add tcl/tk?"
    if ($allUsers) { $question += ' (Windows will ask for administrator rights)' }
    if (-not (Confirm-Step $question)) { return $false }
    $suffix = ''
    if ($info.arch) { $suffix = '-' + $info.arch }
    $url = "https://www.python.org/ftp/python/$($info.version)/python-$($info.version)$suffix.exe"
    $installer = Join-Path $env:TEMP "python-$($info.version)-installer.exe"
    $log = Join-Path $env:TEMP 'epmts-python-tcltk.log'
    try {
        Write-Host 'Downloading the installer...'
        Invoke-WebRequest -Uri $url -OutFile $installer
    } catch {
        Write-Host "No Windows installer is published for Python $($info.version)."
        return $false
    }
    Write-Host 'Adding tcl/tk (a progress window opens)...'
    $arguments = @('/passive', '/modify', 'Include_tcltk=1', "InstallAllUsers=$([int]$allUsers)", '/log', "`"$log`"")
    try {
        if ($allUsers) {
            Start-Process -FilePath $installer -ArgumentList $arguments -Verb RunAs -Wait
        } else {
            Start-Process -FilePath $installer -ArgumentList $arguments -Wait
        }
    } catch {
        Write-Host 'The installer was cancelled.'
        return $false
    } finally {
        Remove-Item $installer -ErrorAction SilentlyContinue
    }
    if (Test-Tk $Python) {
        Write-Host 'tcl/tk added.'
        return $true
    }
    Write-Host "tcl/tk could not be added (installer log: $log)."
    return $false
}

# Installs Python from python.org for the current user, with tcl/tk: 3.12, or 3.13 when the
# Python to keep untouched is a 3.12 (both would share one folder).
function Install-Python([string]$Reason, [string]$AvoidSeries = '') {
    $series = '3.12'
    if ($AvoidSeries -eq '3.12') { $series = '3.13' }
    Write-Host ''
    Write-Host $Reason
    if (-not (Confirm-Step "Download and install Python $series from python.org now (for your user only, with tcl/tk)?")) {
        Write-Host 'Install Python from https://www.python.org/downloads/ (tick "Add python.exe to PATH" and "tcl/tk"), then run this again.'
        exit 1
    }
    $installer = Join-Path $env:TEMP "python-$series-installer.exe"
    Write-Host 'Downloading Python...'
    Invoke-WebRequest -Uri $PythonInstallers[$series] -OutFile $installer
    Write-Host 'Installing Python (a progress window opens)...'
    Start-Process -FilePath $installer -ArgumentList '/passive', 'InstallAllUsers=0', 'PrependPath=1', 'Include_tcltk=1', 'Include_launcher=1', 'Include_test=0' -Wait
    Remove-Item $installer -ErrorAction SilentlyContinue
}

$NeedTk = $Target -ne 'server'
$Python = Find-Python $NeedTk
if (-not $Python -and $NeedTk) {
    $withoutTk = Find-Python $false
    if ($withoutTk -and (Repair-Tk $withoutTk)) {
        $Python = $withoutTk
    } elseif ($withoutTk) {
        $series = Invoke-Quiet $withoutTk @('-c', "import sys; print('%d.%d' % sys.version_info[:2])")
        Install-Python 'EPMTS can install its own Python, with tcl/tk, next to yours (yours is not changed).' $series
        $Python = Find-Python $true
    }
}
if (-not $Python) {
    if (-not (Get-PythonCandidates)) {
        Install-Python 'Python 3.9 or newer is not installed.'
    }
    $Python = Find-Python $NeedTk
}
if (-not $Python) {
    Write-Host 'No usable Python was found. Restart your computer and run quickstart again.'
    exit 1
}

$ffmpegInRepo = Get-ChildItem (Join-Path $Root 'tools\bin') -Recurse -Filter 'ffmpeg.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -and -not $ffmpegInRepo) {
    Write-Host ''
    Write-Host 'ffmpeg is not installed. It is needed for videos (import, thumbnails, conversion for games); pictures work without it.'
    if (Confirm-Step 'Download ffmpeg (about 100 MB) into tools\bin now?') {
        $zip = Join-Path $env:TEMP 'ffmpeg-essentials.zip'
        Write-Host 'Downloading ffmpeg...'
        Invoke-WebRequest -Uri $FfmpegUrl -OutFile $zip
        Expand-Archive -Path $zip -DestinationPath (Join-Path $Root 'tools\bin') -Force
        Remove-Item $zip -ErrorAction SilentlyContinue
        Write-Host 'ffmpeg installed in tools\bin.'
    } else {
        Write-Host 'Continuing without ffmpeg.'
    }
}

if ((Test-Path $VenvPython) -and $NeedTk -and -not (Test-Tk $VenvPython)) {
    # Made from a Python without tcl/tk: rebuild it from the Python chosen above.
    Remove-Item -Recurse -Force $Venv
}
if (-not (Test-Path $VenvPython)) {
    Write-Host 'Creating the private Python environment in .venv\ ...'
    if ($null -eq (Invoke-Quiet $Python @('-m', 'venv', $Venv))) { Write-Host 'Could not create the Python environment.'; exit 1 }
}

# Reinstalls the requirements only when the requirement file changed.
$Stamp = Join-Path $Venv '.installed'
$current = Get-Content $Requirements -Raw
if (-not (Test-Path $Stamp) -or (Get-Content $Stamp -Raw) -ne $current) {
    Write-Host 'Installing the Python packages (first start only)...'
    $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $VenvPython -m pip install -q -r $Requirements
    $pipStatus = $LASTEXITCODE
    $ErrorActionPreference = $previous
    if ($pipStatus -ne 0) { Write-Host 'Package installation failed (check your internet connection).'; exit 1 }
    Set-Content -Path $Stamp -Value $current -NoNewline
}

if ($Target -eq 'home') {
    # The home window needs no console: start it with pythonw and let this window close.
    Start-Process -FilePath (Join-Path $Venv 'Scripts\pythonw.exe') -ArgumentList ('"' + $Script + '"')
    exit 0
}
$ErrorActionPreference = 'Continue'
& $VenvPython $Script @ToolArguments
exit $LASTEXITCODE
