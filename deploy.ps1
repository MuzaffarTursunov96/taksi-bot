# Barcha kerakli fayllarni bitta buyruq bilan serverga yuklaydi va botni qayta ishga tushiradi.
# Ishlatish: PowerShell'da shu papkada: .\deploy.ps1

$ErrorActionPreference = "Stop"

$server = "root@189.74.97.20"
$remoteDir = "/opt/taksibot"

$files = @(
    "main.py",
    "bot.py",
    "config.py",
    "storage.py",
    "commands.py",
    "telethon_accounts.py",
    "link_account.py",
    "menu_handlers.py",
    "admin_handlers.py",
    "handlers.py",
    "core.py",
    "filters.py",
    "requirements.txt",
    ".env"
)

Write-Host "Fayllar yuklanmoqda..." -ForegroundColor Cyan
scp $files "${server}:${remoteDir}/"

Write-Host "Bot qayta ishga tushirilmoqda..." -ForegroundColor Cyan
ssh $server "systemctl restart taksibot && sleep 2 && systemctl status taksibot --no-pager"

Write-Host "Tayyor!" -ForegroundColor Green
