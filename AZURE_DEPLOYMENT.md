# Azure Deployment Guide

This guide will help you deploy the OpenAI Apps SDK Examples to Azure using Azure Container Apps.

## Prerequisites

1. **Azure CLI**: Install from [https://docs.microsoft.com/en-us/cli/azure/install-azure-cli](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
2. **Docker Desktop**: Install from [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/) (required for building container images)
3. **Azure Account**: You need an active Azure subscription with Container Apps enabled

## Quick Deployment

### Option 1: Deploy to New Azure Container Apps (Recommended)

#### Step 1: Login to Azure
```bash
az login
```

#### Step 2: Run the deployment script
```powershell
# On Windows PowerShell
.\deploy-to-azure.ps1 -ResourceGroupName "my-openai-apps-rg" -Location "EastUS"
```

### Option 2: Deploy to Existing Azure Web App

If you already have an Azure Web App, you can deploy directly to it:

#### Step 1: Login to Azure
```bash
az login
```

#### Step 2: Run the existing web app deployment script
```powershell
# Deploy to your existing web app
.\deploy-to-existing-webapp.ps1 -ResourceGroupName "gptApps" -WebAppName "provgpt"
```

#### Step 3: Set up GitHub Actions (Optional)

To enable automatic deployments via GitHub Actions:

1. Go to your GitHub repository settings > Secrets and variables > Actions
2. Add these secrets (you already have these from your existing repo):
   - `AZURE_CLIENT_ID`: Your Azure service principal client ID
   - `AZURE_TENANT_ID`: Your Azure tenant ID
   - `AZURE_SUBSCRIPTION_ID`: Your Azure subscription ID
   - `AZURE_WEBAPP_NAME`: Your web app name (provgpt)

3. The `.github/workflows/azure-deploy.yml` file will automatically deploy on pushes to main branch using GitHub Container Registry (ghcr.io)

Or using Azure CLI:
```bash
# Set variables
RESOURCE_GROUP="my-openai-apps-rg"
LOCATION="EastUS"
APP_NAME="openai-apps-sdk-$(openssl rand -hex 4)"
REGISTRY_NAME="openaiappssdk$(openssl rand -hex 4)"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Deploy infrastructure
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file azuredeploy.bicep \
  --parameters containerAppName=$APP_NAME containerRegistryName=$REGISTRY_NAME

# Build and push Docker image
az acr login --name $REGISTRY_NAME
docker build -t "$REGISTRY_NAME.azurecr.io/openai-apps-sdk:latest" .
docker push "$REGISTRY_NAME.azurecr.io/openai-apps-sdk:latest"
```

## Manual Deployment Steps

If you prefer to deploy manually:

### 1. Create Azure Resources
```bash
# Create resource group
az group create --name my-openai-apps-rg --location eastus

# Create container registry
az acr create --resource-group my-openai-apps-rg --name myopenaiappssdk --sku Basic

# Create log analytics workspace
az monitor log-analytics workspace create \
  --resource-group my-openai-apps-rg \
  --name my-openai-apps-logs \
  --location eastus

# Create container app environment
az containerapp env create \
  --name my-openai-apps-env \
  --resource-group my-openai-apps-rg \
  --location eastus \
  --logs-workspace-id $(az monitor log-analytics workspace show \
    --resource-group my-openai-apps-rg \
    --name my-openai-apps-logs \
    --query id -o tsv) \
  --logs-workspace-key $(az monitor log-analytics workspace get-shared-keys \
    --resource-group my-openai-apps-rg \
    --name my-openai-apps-logs \
    --query primarySharedKey -o tsv)
```

### 2. Build and Push Docker Image
```bash
# Login to ACR
az acr login --name myopenaiappssdk

# Build image
docker build -t myopenaiappssdk.azurecr.io/openai-apps-sdk:latest .

# Push image
docker push myopenaiappssdk.azurecr.io/openai-apps-sdk:latest
```

### 3. Deploy Container App
```bash
az containerapp create \
  --name my-openai-apps \
  --resource-group my-openai-apps-rg \
  --environment my-openai-apps-env \
  --image myopenaiappssdk.azurecr.io/openai-apps-sdk:latest \
  --target-port 8000 \
  --ingress external \
  --cpu 0.5 \
  --memory 1Gi \
  --registry-server myopenaiappssdk.azurecr.io \
  --registry-username $(az acr credential show --name myopenaiappssdk --query username -o tsv) \
  --registry-password $(az acr credential show --name myopenaiappssdk --query passwords[0].value -o tsv)
```

## Accessing Your Deployed App

After deployment, you'll get a URL like: `https://your-app-name.region.azurecontainerapps.io`

Your MCP server will be available at:
- Pizzaz Server: `https://your-app-name.region.azurecontainerapps.io`

Note: Currently deploying the Pizzaz server. You can modify the Dockerfile to run additional servers if needed.

## ChatGPT Integration

### Option 1: Direct Azure URL
1. Go to ChatGPT Settings > Connectors
2. Add a new connector
3. Use URL: `https://your-app-name.region.azurecontainerapps.io/mcp`

### Option 2: Use ngrok for local testing
If you want to test locally first:
```bash
# Install ngrok from https://ngrok.com/
ngrok http 8000  # For the Python server
# or
ngrok http 3000  # For the Node server
```

Then use the ngrok URL in ChatGPT connectors.

## Troubleshooting

### Common Issues

1. **Port conflicts**: Make sure ports 8000 and 8001 are available
2. **Azure quota limits**: Check your Azure subscription limits for Container Apps
3. **Docker build fails**: Ensure Docker is running and you have sufficient disk space

### Logs
View application logs:
```bash
az containerapp logs show \
  --name my-openai-apps \
  --resource-group my-openai-apps-rg \
  --follow
```

## Cost Estimation

- **Azure Container Apps**: ~$0.03/hour for 0.5 CPU, 1GB RAM
- **Azure Container Registry**: ~$0.50/month for Basic tier
- **Log Analytics**: ~$2.50/GB ingested

Total estimated cost: ~$20-30/month for light usage.

## Cleanup

To remove all resources:
```bash
az group delete --name my-openai-apps-rg --yes
```
