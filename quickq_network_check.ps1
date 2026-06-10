$ErrorActionPreference = "Continue"

Set-Location $PSScriptRoot

$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("quickq-network-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")

function W($text = "") {
  $text | Tee-Object -FilePath $logFile -Append
}

function Test-Port($name, $hostName, $port) {
  W ""
  W ("== {0} {1}:{2} ==" -f $name, $hostName, $port)
  try {
    $client = New-Object Net.Sockets.TcpClient
    $async = $client.BeginConnect($hostName, [int]$port, $null, $null)
    $ok = $async.AsyncWaitHandle.WaitOne(8000, $false)
    if ($ok -and $client.Connected) {
      $client.EndConnect($async)
      $client.Close()
      W "[PASS] TCP connected"
      return $true
    }
    $client.Close()
    W "[FAIL] TCP timeout"
    return $false
  } catch {
    W ("[FAIL] {0}: {1}" -f $_.Exception.GetType().Name, $_.Exception.Message)
    return $false
  }
}

W "========================================"
W "QuickQ / Telegram network diagnostics"
W "No Python required"
W "========================================"
W ("Time: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
W ("Computer: " + $env:COMPUTERNAME)
W ("User: " + $env:USERNAME)
W ("Directory: " + (Get-Location))
W ("Log file: " + $logFile)

W ""
W "1. Windows proxy registry"
$proxyPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
$proxyReg = Get-ItemProperty -Path $proxyPath -ErrorAction SilentlyContinue
if ($proxyReg) {
  W ("ProxyEnable: " + $proxyReg.ProxyEnable)
  W ("ProxyServer: " + $proxyReg.ProxyServer)
  W ("AutoConfigURL: " + $proxyReg.AutoConfigURL)
} else {
  W "[FAIL] Cannot read proxy registry"
}

W ""
W "2. DNS test"
try {
  $dns = Resolve-DnsName telegram.org -ErrorAction Stop
  foreach ($item in $dns) {
    W (($item.Name, $item.Type, $item.IPAddress) -join " ")
  }
} catch {
  W ("[FAIL] DNS error: " + $_.Exception.Message)
}

W ""
W "3. QuickQ common local proxy ports"
Test-Port "QuickQ HTTP/SOCKS possible port" "127.0.0.1" 8800 | Out-Null
Test-Port "Common proxy port" "127.0.0.1" 7890 | Out-Null
Test-Port "Common proxy port" "127.0.0.1" 1080 | Out-Null
Test-Port "Common proxy port" "127.0.0.1" 10808 | Out-Null

W ""
W "4. Telegram direct TCP test"
$targets = @(
  @("DC1", "149.154.175.50", 443),
  @("DC2", "149.154.167.50", 443),
  @("DC3", "149.154.175.100", 443),
  @("DC4", "149.154.167.91", 443),
  @("DC5", "91.108.56.130", 443)
)
foreach ($target in $targets) {
  Test-Port $target[0] $target[1] $target[2] | Out-Null
}

W ""
W "5. curl tests if curl exists"
$curl = Get-Command curl.exe -ErrorAction SilentlyContinue
if ($curl) {
  W "curl direct https://telegram.org"
  cmd /c "curl.exe -I -L --connect-timeout 10 https://telegram.org" 2>&1 | Tee-Object -FilePath $logFile -Append
  W ""
  W "curl via http://127.0.0.1:8800 https://telegram.org"
  cmd /c "curl.exe -I -L --connect-timeout 10 --proxy http://127.0.0.1:8800 https://telegram.org" 2>&1 | Tee-Object -FilePath $logFile -Append
  W ""
  W "curl via socks5://127.0.0.1:8800 https://telegram.org"
  cmd /c "curl.exe -I -L --connect-timeout 10 --proxy socks5://127.0.0.1:8800 https://telegram.org" 2>&1 | Tee-Object -FilePath $logFile -Append
} else {
  W "curl.exe not found"
}

W ""
W "6. Listening ports around proxy candidates"
cmd /c "netstat -ano | findstr LISTENING | findstr ""8800 7890 1080 10808""" 2>&1 | Tee-Object -FilePath $logFile -Append

W ""
W "Done. Send this log file to Codex."
W $logFile

Write-Host ""
Write-Host "========================================"
Write-Host "Finished."
Write-Host "Please send this log file:"
Write-Host $logFile
Write-Host "========================================"
