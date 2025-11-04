# Deploy to Existing Azure Web App
# This script deploys the OpenAI Apps SDK Examples to your existing Azure Web App

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory=$true)]
    [string]$WebAppName,

    [Parameter(Mandatory=$false)]
    [string]$ContainerRegistryName = "openaiappssdk$(Get-Random -Maximum 9999)"
)

Write-Host "🚀 Deploying OpenAI Apps SDK Examples to existing Azure Web App" -ForegroundColor Green
Write-Host "Resource Group: $ResourceGroupName" -ForegroundColor Cyan
Write-Host "Web App: $WebAppName" -ForegroundColor Cyan
Write-Host "Container Registry: $ContainerRegistryName" -ForegroundColor Cyan

# Check if Azure CLI is installed
if (!(Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Error "Azure CLI is not installed. Please install it from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
}

# Check if Docker is installed
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed. Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
    exit 1
}

# Check if logged in to Azure
$account = az account show 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not logged in to Azure. Please run 'az login' first."
    exit 1
}

# Use GitHub Container Registry for consistency with GitHub Actions
$githubUsername = Read-Host "Enter your GitHub username"
$imageName = "ghcr.io/$githubUsername/openai-apps-sdk-examples:latest"

Write-Host "🐳 Building Docker image..." -ForegroundColor Yellow
docker build -t $imageName .

Write-Host "🔐 Logging in to GitHub Container Registry..." -ForegroundColor Yellow
Write-Host "   You need a GitHub Personal Access Token with 'write:packages' permission" -ForegroundColor Yellow
$githubToken = Read-Host "Enter your GitHub Personal Access Token" -AsSecureString
$githubTokenPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($githubToken))

docker login ghcr.io --username $githubUsername --password $githubTokenPlain

# Push Docker image
Write-Host "📤 Pushing Docker image..." -ForegroundColor Yellow
docker push $imageName

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to push Docker image"
    exit 1
}

# Deploy to existing web app
Write-Host "🚀 Deploying to Azure Web App..." -ForegroundColor Yellow
az webapp config container set `
    --name $WebAppName `
    --resource-group $ResourceGroupName `
    --docker-custom-image-name $imageName `
    --output none

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to deploy to web app"
    exit 1
}

# Get web app URL
$webAppInfo = az webapp show --name $WebAppName --resource-group $ResourceGroupName --output json | ConvertFrom-Json
$webAppUrl = "https://" + $webAppInfo.defaultHostName

Write-Host "✅ Deployment completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Your MCP servers are available at:" -ForegroundColor Cyan
Write-Host "   Pizzaz Server: $webAppUrl`:8000" -ForegroundColor White
Write-Host "   Solar System Server: $webAppUrl`:8001" -ForegroundColor White
Write-Host ""
Write-Host "🔗 To use with ChatGPT:" -ForegroundColor Cyan
Write-Host "   1. Go to ChatGPT Settings > Connectors" -ForegroundColor White
Write-Host "   2. Add a new connector with URL: $webAppUrl/mcp" -ForegroundColor White
Write-Host ""
Write-Host "📝 Note: Make sure your Azure Web App has the following app settings:" -ForegroundColor Yellow
Write-Host "   - WEBSITES_PORT=8000" -ForegroundColor White
Write-Host "   - Or configure the startup command to run both servers" -ForegroundColor White
