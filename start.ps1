Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  Job Hunter V2 - Iniciando Servicos" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# Obtendo o IP Local para mostrar ao usuario (adaptador com Gateway = Wi-Fi/Ethernet real)
$localIp = ""
try {
    $netConfig = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq "Up" } | Select-Object -First 1
    if ($netConfig) { $localIp = $netConfig.IPv4Address.IPAddress }
} catch {
    $localIp = ""
}

Write-Host "1. Iniciando o Agendador (Scheduler) em segundo plano..." -ForegroundColor Yellow
$schedulerProcess = Start-Process -FilePath "python" -ArgumentList "infrastructure\background\scheduler_service.py" -PassThru -WindowStyle Hidden

Write-Host "2. Iniciando o Painel de Controle (Dashboard)..." -ForegroundColor Yellow
$dashboardProcess = Start-Process -FilePath "python" -ArgumentList "-m streamlit run infrastructure\web\streamlit_app.py --server.address 0.0.0.0" -PassThru

Write-Host ""
Write-Host "Servicos iniciados com sucesso!" -ForegroundColor Green
Write-Host "----------------------------------------------" -ForegroundColor Cyan
Write-Host "[PC]     http://localhost:8501" -ForegroundColor White
if ($localIp) {
    Write-Host "[REDE]   http://$localIp`:8501" -ForegroundColor White
    Write-Host "         (certifique-se que o Firewall permite o Python)" -ForegroundColor DarkGray
}
Write-Host "----------------------------------------------" -ForegroundColor Cyan
Write-Host "Pressione qualquer tecla para encerrar os servicos..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Write-Host "Encerrando Job Hunter..." -ForegroundColor Yellow
Stop-Process -Id $schedulerProcess.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $dashboardProcess.Id -Force -ErrorAction SilentlyContinue

Write-Host "Limpando cache Python..." -ForegroundColor DarkGray
Get-ChildItem -Path "." -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Feito!" -ForegroundColor Green
