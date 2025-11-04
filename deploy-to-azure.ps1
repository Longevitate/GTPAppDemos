# Azure Deployment Script for OpenAI Apps SDK Examples
# This script builds and deploys the MCP servers to Azure Container Apps

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory=$true)]
    [string]$Location,

    [Parameter(Mandatory=$false)]
    [string]$ContainerAppName = "openai-apps-sdk-$(Get-Random -Maximum 9999)",

    [Parameter(Mandatory=$false)]
    [string]$ContainerRegistryName = "openaiappssdk$(Get-Random -Maximum 9999)",

    [Parameter(Mandatory=$false)]
    [string]$ExistingWebAppName,

    [Parameter(Mandatory=$false)]
    [switch]$UseExistingWebApp
)

Write-Host "🚀 Starting Azure deployment for OpenAI Apps SDK Examples" -ForegroundColor Green
Write-Host "Resource Group: $ResourceGroupName" -ForegroundColor Cyan
Write-Host "Location: $Location" -ForegroundColor Cyan
Write-Host "Container App Name: $ContainerAppName" -ForegroundColor Cyan
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

# Create resource group if it doesn't exist
Write-Host "📁 Creating/checking resource group..." -ForegroundColor Yellow
az group create --name $ResourceGroupName --location $Location --output none

# Create container registry first
Write-Host "📦 Creating Azure Container Registry..." -ForegroundColor Yellow
az acr create --resource-group $ResourceGroupName --name $ContainerRegistryName --sku Basic --output none

# Get registry credentials
$registryLoginServer = "$ContainerRegistryName.azurecr.io"
$registryUsername = az acr credential show --name $ContainerRegistryName --query username -o tsv
$acrPassword = az acr credential show --name $ContainerRegistryName --output json | ConvertFrom-Json
$acrPassword = $acrPassword.passwords[0].value

# Check if Docker is available
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not available in PATH. Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
    Write-Host "Alternative: You can build and push the image manually:" -ForegroundColor Yellow
    Write-Host "  1. Install Docker Desktop" -ForegroundColor White
    Write-Host "  2. Run: docker build -t $registryLoginServer/openai-apps-sdk:latest ." -ForegroundColor White
    Write-Host "  3. Run: docker login $registryLoginServer --username $registryUsername --password <password>" -ForegroundColor White
    Write-Host "  4. Run: docker push $registryLoginServer/openai-apps-sdk:latest" -ForegroundColor White
    exit 1
}

# Build and push Docker image
Write-Host "🐳 Building Docker image..." -ForegroundColor Yellow
docker build -t "$registryLoginServer/openai-apps-sdk:latest" .

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to build Docker image"
    exit 1
}

Write-Host "🔐 Logging in to Azure Container Registry..." -ForegroundColor Yellow
docker login "$registryLoginServer" --username $registryUsername --password $acrPassword

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to login to Azure Container Registry"
    exit 1
}

Write-Host "📤 Pushing Docker image..." -ForegroundColor Yellow
docker push "$registryLoginServer/openai-apps-sdk:latest"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to push Docker image"
    exit 1
}

# Create or update container registry
Write-Host "📦 Creating/updating Azure Container Registry..." -ForegroundColor Yellow

# Check if ACR already exists
$acrExists = az acr show --name $ContainerRegistryName --resource-group $ResourceGroupName --output json 2>$null
if ($LASTEXITCODE -eq 0) {
    # ACR exists, update it to enable admin access
    az acr update --name $ContainerRegistryName --admin-enabled true --output none
} else {
    # Create new ACR
    az acr create --resource-group $ResourceGroupName --name $ContainerRegistryName --sku Basic --admin-enabled true --output none
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to create/update Azure Container Registry"
    exit 1
}

# Get ACR credentials
Write-Host "🔑 Getting ACR credentials..." -ForegroundColor Yellow
$acrCredentials = az acr credential show --name $ContainerRegistryName --output json | ConvertFrom-Json
$acrUsername = $acrCredentials.username
$acrPassword = $acrCredentials.passwords[0].value

if ($UseExistingWebApp) {
    if (-not $ExistingWebAppName) {
        Write-Error "ExistingWebAppName parameter is required when using -UseExistingWebApp"
        exit 1
    }

    # Deploy directly to existing web app
    Write-Host "🔄 Deploying to existing Azure Web App: $ExistingWebAppName" -ForegroundColor Yellow

    # Build Docker image
    Write-Host "🐳 Building Docker image..." -ForegroundColor Yellow
    docker build -t "$ContainerRegistryName.azurecr.io/openai-apps-sdk:latest" .

    # Login to ACR
    Write-Host "🔐 Logging in to Azure Container Registry..." -ForegroundColor Yellow
    docker login "$ContainerRegistryName.azurecr.io" --username $acrUsername --password $acrPassword

    # Push Docker image
    Write-Host "📤 Pushing Docker image..." -ForegroundColor Yellow
    docker push "$ContainerRegistryName.azurecr.io/openai-apps-sdk:latest"

    # Deploy to existing web app
    Write-Host "🚀 Deploying to Azure Web App..." -ForegroundColor Yellow
    az webapp config container set `
        --name $ExistingWebAppName `
        --resource-group $ResourceGroupName `
        --docker-custom-image-name "$ContainerRegistryName.azurecr.io/openai-apps-sdk:latest" `
        --docker-registry-server-url "https://$ContainerRegistryName.azurecr.io" `
        --docker-registry-server-user $acrUsername `
        --docker-registry-server-password $acrPassword `
        --output none

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to deploy to existing web app"
        exit 1
    }

    # Get web app URL
    $webAppInfo = az webapp show --name $ExistingWebAppName --resource-group $ResourceGroupName --output json | ConvertFrom-Json
    $containerAppUrl = $webAppInfo.defaultHostName

    Write-Host "✅ Deployment to existing web app completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "🌐 Your MCP servers are available at:" -ForegroundColor Cyan
    Write-Host "   Pizzaz Server: https://$containerAppUrl:8000" -ForegroundColor White
    Write-Host "   Solar System Server: https://$containerAppUrl:8001" -ForegroundColor White
    Write-Host ""
    Write-Host "🔗 To use with ChatGPT:" -ForegroundColor Cyan
    Write-Host "   1. Go to ChatGPT Settings > Connectors" -ForegroundColor White
    Write-Host "   2. Add a new connector with URL: https://$containerAppUrl/mcp" -ForegroundColor White
    Write-Host "   3. Or use ngrok locally: ngrok http 8000" -ForegroundColor White
    Write-Host ""
    Write-Host "📚 For more info, see the README.md file" -ForegroundColor Cyan

    exit 0
}

# Deploy infrastructure using Bicep
Write-Host "🏗️  Deploying Azure infrastructure..." -ForegroundColor Yellow
az deployment group create `
    --resource-group $ResourceGroupName `
    --template-file azuredeploy.bicep `
    --parameters containerAppName=$ContainerAppName containerRegistryName=$ContainerRegistryName acrUsername=$acrUsername acrPassword=$acrPassword `
    --output none

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to deploy Azure infrastructure"
    exit 1
}

# Get deployment outputs
Write-Host "📋 Getting deployment outputs..." -ForegroundColor Yellow
$outputs = az deployment group show --resource-group $ResourceGroupName --name azuredeploy --output json | ConvertFrom-Json
$containerAppUrl = $outputs.properties.outputs.containerAppUrl.value

Write-Host "✅ Deployment completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Your MCP servers are available at:" -ForegroundColor Cyan
Write-Host "   Pizzaz Server: $containerAppUrl:8000" -ForegroundColor White
Write-Host "   Solar System Server: $containerAppUrl:8001" -ForegroundColor White
Write-Host ""
Write-Host "🔗 To use with ChatGPT:" -ForegroundColor Cyan
Write-Host "   1. Go to ChatGPT Settings > Connectors" -ForegroundColor White
Write-Host "   2. Add a new connector with URL: $containerAppUrl/mcp" -ForegroundColor White
Write-Host "   3. Or use ngrok locally: ngrok http 8000" -ForegroundColor White
Write-Host ""
Write-Host "📚 For more info, see the README.md file" -ForegroundColor Cyan
