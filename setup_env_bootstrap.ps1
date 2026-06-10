$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("setup-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")

$envConfigPath = Join-Path $PSScriptRoot "env_config.json"
if (Test-Path $envConfigPath) {
  $envConfig = Get-Content -Raw -Encoding UTF8 $envConfigPath | ConvertFrom-Json
} else {
  $envConfig = [pscustomobject]@{
    venv_dir = ".venv"
    python = [pscustomobject]@{
      launcher_command = "py -3"
      fallback_command = "python"
      local_appdata_paths = @("Programs\Python\Python312\python.exe")
      winget_package_id = "Python.Python.3.12"
      installer_url = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
      installer_file = "python-3.12.10-amd64.exe"
      installer_args = "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1"
    }
  }
}

trap {
  Write-Host ""
  Write-Host "Environment setup failed." -ForegroundColor Red
  Write-Host $_.Exception.Message -ForegroundColor Red
  Write-Host ""
  Write-Host "Log file: $logFile"
  Stop-Transcript -ErrorAction SilentlyContinue | Out-Null
  $host.SetShouldExit(1)
  break
}

function Write-Step($message) {
  Write-Host ""
  Write-Host "== $message ==" -ForegroundColor Cyan
}

function Get-ConfigValue($object, $name, $fallback) {
  if ($null -ne $object -and $object.PSObject.Properties.Name -contains $name) {
    $value = $object.$name
    if ($null -ne $value -and "$value" -ne "") {
      return $value
    }
  }
  return $fallback
}

function Test-CommandLine($commandLine) {
  if (-not $commandLine) {
    return $false
  }

  $oldErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    cmd.exe /d /c "$commandLine --version >nul 2>nul"
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  } finally {
    $ErrorActionPreference = $oldErrorActionPreference
  }
}

function Find-Python {
  $pythonConfig = $envConfig.python

  $launcherCommand = Get-ConfigValue $pythonConfig "launcher_command" "py -3"
  if (Test-CommandLine $launcherCommand) {
    return $launcherCommand
  }

  $fallbackCommand = Get-ConfigValue $pythonConfig "fallback_command" "python"
  if (Test-CommandLine $fallbackCommand) {
    return $fallbackCommand
  }

  $localPaths = Get-ConfigValue $pythonConfig "local_appdata_paths" @("Programs\Python\Python312\python.exe")
  foreach ($relativePath in $localPaths) {
    $localPython = Join-Path $env:LOCALAPPDATA $relativePath
    if (Test-Path $localPython) {
      return $localPython
    }
  }

  return ""
}

function Invoke-CommandLine($commandLine) {
  Write-Host "> $commandLine"
  cmd /c $commandLine
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code $LASTEXITCODE"
  }
}

function Stop-VenvProcesses($venvDir) {
  $escaped = $venvDir.Replace("\", "\\")
  $processes = Get-CimInstance Win32_Process -Filter "name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
      $_.CommandLine -like "*$venvDir*" -or
      $_.CommandLine -like "*$escaped*"
    }

  foreach ($process in $processes) {
    Write-Host ("Stopping stale Python process: {0}" -f $process.ProcessId) -ForegroundColor Yellow
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
  }
}

function Remove-Venv($venvDir) {
  Stop-VenvProcesses $venvDir
  Start-Sleep -Milliseconds 500
  for ($i = 1; $i -le 3; $i++) {
    try {
      if (Test-Path $venvDir) {
        Remove-Item -LiteralPath $venvDir -Recurse -Force
      }
      return
    } catch {
      if ($i -eq 3) {
        throw
      }
      Start-Sleep -Seconds 1
    }
  }
}

Start-Transcript -Path $logFile -Append | Out-Null

Write-Host "========================================"
Write-Host "Environment bootstrap / dependency install"
Write-Host "========================================"
Write-Host "Log file: $logFile"
Write-Host "Env config: $envConfigPath"

$venvName = Get-ConfigValue $envConfig "venv_dir" ".venv"
$venvDir = Join-Path $PSScriptRoot $venvName
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvCheckCode = "import pathlib, sys; expected = pathlib.Path(sys.argv[1]).resolve(); actual = pathlib.Path(sys.prefix).resolve(); raise SystemExit(0 if actual == expected else 99)"

if ((Test-Path $venvDir) -and -not (Test-Path $venvPython)) {
  Write-Step "Removing incomplete virtual environment"
  Remove-Venv $venvDir
}

if (Test-Path $venvPython) {
  Write-Step "Checking existing virtual environment"
  & $venvPython -c $venvCheckCode $venvDir
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Existing .venv is broken or copied from another computer. Recreating it..." -ForegroundColor Yellow
    Remove-Venv $venvDir
  }
}

if (-not (Test-Path $venvPython)) {
  Write-Step "Checking Python"
  $pythonCmd = Find-Python

  if (-not $pythonCmd) {
    Write-Step "Python not found. Trying winget"
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
      $wingetPackageId = Get-ConfigValue $envConfig.python "winget_package_id" "Python.Python.3.12"
      cmd /c "winget install -e --id $wingetPackageId --scope user --accept-source-agreements --accept-package-agreements"
    }
    $pythonCmd = Find-Python
  }

  if (-not $pythonCmd) {
    Write-Step "Downloading Python installer"
    $installerDir = Join-Path $PSScriptRoot "installers"
    New-Item -ItemType Directory -Force -Path $installerDir | Out-Null
    $installerFile = Get-ConfigValue $envConfig.python "installer_file" "python-3.12.10-amd64.exe"
    $installerUrl = Get-ConfigValue $envConfig.python "installer_url" "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
    $installerArgs = Get-ConfigValue $envConfig.python "installer_args" "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1"
    $installer = Join-Path $installerDir $installerFile
    if (-not (Test-Path $installer)) {
      Invoke-WebRequest -Uri $installerUrl -OutFile $installer
    }
    Start-Process -FilePath $installer -ArgumentList $installerArgs -Wait
    $pythonCmd = Find-Python
  }

  if (-not $pythonCmd) {
    throw "Python was not found. Please install Python 3.12 manually and run this file again."
  }

  Write-Step "Creating virtual environment"
  Invoke-CommandLine "$pythonCmd -m venv `"$venvDir`""
}

if (-not (Test-Path $venvPython)) {
  throw "Virtual environment was not created: $venvPython"
}

Write-Step "Checking pip"
cmd /c "`"$venvPython`" -m pip --version >nul 2>nul"
if ($LASTEXITCODE -ne 0) {
  Write-Host "pip is missing from .venv. Repairing it..." -ForegroundColor Yellow
  cmd /c "`"$venvPython`" -m ensurepip --upgrade"
  if ($LASTEXITCODE -ne 0) {
    Write-Host "pip repair failed. Recreating .venv..." -ForegroundColor Yellow
    Remove-Venv $venvDir
    Write-Step "Creating virtual environment"
    $pythonCmd = Find-Python
    if (-not $pythonCmd) {
      throw "Python was not found. Please install Python 3.12 manually and run this file again."
    }
    Invoke-CommandLine "$pythonCmd -m venv `"$venvDir`""
  }
}

Write-Step "Running project setup"
Invoke-CommandLine "`"$venvPython`" `"$PSScriptRoot\setup_env.py`""

Write-Host ""
Write-Host "Environment is ready." -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "01_login"
Write-Host "02_run_task"

Stop-Transcript -ErrorAction SilentlyContinue | Out-Null
$host.SetShouldExit(0)
