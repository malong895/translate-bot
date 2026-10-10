param(
    [Parameter(Mandatory = $true)]
    [string]$VpsIp,
    [string]$VpsUser = "ubuntu",
    [string]$KeyPath = "$env:USERPROFILE\OneDrive\Documents\IT.FF\vps\oracle_key",
    [string]$Project = $PSScriptRoot
)

$ErrorActionPreference = "Stop"
$ssh = @("-i", $KeyPath, "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=NUL")
$target = "$VpsUser@$VpsIp"

Write-Host "== 1/6 Staging clean copy =="
$stage = Join-Path $env:TEMP ("translatebot_deploy_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stage | Out-Null
foreach ($f in @("bot.py", "translator.py", "config.json", "requirements.txt")) {
    Copy-Item (Join-Path $Project $f) $stage
}

Write-Host "== 2/6 Uploading to VPS =="
ssh @ssh $target "rm -rf ~/translatebot"
scp @ssh -r "$stage" "${target}:~/translatebot"
if ($LASTEXITCODE -ne 0) { throw "upload failed" }

Write-Host "== 3/6 Installing Python on server =="
ssh @ssh $target "sudo apt-get update -y && sudo apt-get install -y python3-venv python3-pip"
if ($LASTEXITCODE -ne 0) { throw "apt failed" }

Write-Host "== 4/6 Installing bot libraries =="
ssh @ssh $target "cd ~/translatebot && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "pip failed" }

Write-Host "== 5/6 Creating 24/7 service (translatebot.service) =="
$unit = @"
[Unit]
Description=Translate Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$VpsUser
WorkingDirectory=/home/$VpsUser/translatebot
ExecStart=/home/$VpsUser/translatebot/venv/bin/python3 bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"@
$unit | ssh @ssh $target "sudo tee /etc/systemd/system/translatebot.service > /dev/null"
ssh @ssh $target "sudo systemctl daemon-reload && sudo systemctl enable --now translatebot"
if ($LASTEXITCODE -ne 0) { throw "service failed" }

Write-Host "== 6/6 Stopping local instance (avoid double replies) =="
Stop-ScheduledTask -TaskName "TranslateBot" -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*translate-bot*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 5
ssh @ssh $target "systemctl is-active translatebot && journalctl -u translatebot -n 5 --no-pager"

Write-Host ""
Write-Host "DONE! Translate bot is now 24/7 on the VPS (PC can be off)."
Write-Host "  status : ssh -i $KeyPath ${target} systemctl status translatebot"
Write-Host "  logs   : ssh -i $KeyPath ${target} journalctl -u translatebot -f"
Write-Host "  restart: ssh -i $KeyPath ${target} sudo systemctl restart translatebot"
