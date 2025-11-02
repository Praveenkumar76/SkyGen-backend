# SkyGen Backend Startup Script
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  Starting SkyGen Backend Server" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Please create a .env file with the following variables:" -ForegroundColor Yellow
    Write-Host "  - GROQ_API_KEY=your_groq_api_key" -ForegroundColor Yellow
    Write-Host "  - SKYGEN_URL=your_supabase_url" -ForegroundColor Yellow
    Write-Host "  - SKYGEN_SERVICE_KEY=your_supabase_service_key" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Environment file found" -ForegroundColor Green
Write-Host "✓ Starting FastAPI server on http://localhost:8000" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the backend using uvicorn
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
