# Get Azure Secrets for GitHub Actions
# This script helps you find the values needed for GitHub Actions secrets

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory=$true)]
    [string]$WebAppName
)

Write-Host "🔍 Getting Azure secrets for GitHub Actions..." -ForegroundColor Green
Write-Host "Resource Group: $ResourceGroupName" -ForegroundColor Cyan
Write-Host "Web App: $WebAppName" -ForegroundColor Cyan

# Check if Azure CLI is installed
if (!(Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Error "Azure CLI is not installed. Please install it from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
}

# Check if logged in to Azure
$account = az account show 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not logged in to Azure. Please run 'az login' first."
    exit 1
}

Write-Host ""
Write-Host "📋 Add these values to your GitHub repository secrets:" -ForegroundColor Yellow
Write-Host "   GitHub Repo → Settings → Secrets and variables → Actions → New repository secret" -ForegroundColor White
Write-Host ""

# Get container configuration
Write-Host "🔐 Container Registry Credentials:" -ForegroundColor Cyan
try {
    $containerConfig = az webapp config container show --name $WebAppName --resource-group $ResourceGroupName --output json | ConvertFrom-Json

    if ($containerConfig) {
        Write-Host "   AZURE_WEBAPP_USERNAME: $($containerConfig.dockerRegistryUsername)" -ForegroundColor White
        Write-Host "   AZURE_WEBAPP_PASSWORD: $($containerConfig.dockerRegistryPassword)" -ForegroundColor White
        Write-Host ""
    } else {
        Write-Host "   ❌ No container configuration found. Your web app might not be using containers." -ForegroundColor Red
        Write-Host ""
    }
} catch {
    Write-Host "   ❌ Error getting container config. Your web app might not be using containers." -ForegroundColor Red
    Write-Host ""
}

# List ACRs in the resource group
Write-Host "📦 Azure Container Registries in this resource group:" -ForegroundColor Cyan
try {
    $acrs = az acr list --resource-group $ResourceGroupName --output json | ConvertFrom-Json

    if ($acrs.Count -gt 0) {
        foreach ($acr in $acrs) {
            Write-Host "   Registry: $($acr.name)" -ForegroundColor White
            Write-Host "   Login Server: $($acr.loginServer)" -ForegroundColor White

            # Get credentials
            try {
                $acrCreds = az acr credential show --name $acr.name --output json | ConvertFrom-Json
                Write-Host "   Username: $($acrCreds.username)" -ForegroundColor White
                Write-Host "   Password: $($acrCreds.passwords[0].value)" -ForegroundColor White
            } catch {
                Write-Host "   ❌ Could not get credentials for $($acr.name)" -ForegroundColor Red
            }
            Write-Host ""
        }
    } else {
        Write-Host "   No Azure Container Registries found in this resource group." -ForegroundColor Yellow
        Write-Host "   You may need to create one or use Docker Hub." -ForegroundColor Yellow
        Write-Host ""
    }
} catch {
    Write-Host "   ❌ Error listing ACRs." -ForegroundColor Red
    Write-Host ""
}

Write-Host "💡 Tips:" -ForegroundColor Green
Write-Host "   - If using ACR, the username is usually the ACR name" -ForegroundColor White
Write-Host "   - If using Docker Hub, username is your Docker Hub username" -ForegroundColor White
Write-Host "   - For Azure Web Apps, the registry is often the web app name + '.azurewebsites.net'" -ForegroundColor White
Write-Host ""
Write-Host "🔄 After adding secrets, push to main branch to trigger deployment!" -ForegroundColor Green
