# Use Node.js 18 as base image
FROM node:18-alpine

# Install Python and pip
RUN apk add --no-cache python3 py3-pip

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json pnpm-lock.yaml ./

# Install pnpm
RUN npm install -g pnpm

# Install Node.js dependencies
RUN pnpm install --frozen-lockfile

# Copy Python requirements
COPY pizzaz_server_python/requirements.txt ./pizzaz_server_python/
COPY solar-system_server_python/requirements.txt ./solar-system_server_python/

# Install Python dependencies in virtual environment
RUN python3 -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --no-cache-dir -r pizzaz_server_python/requirements.txt && \
    pip install --no-cache-dir -r solar-system_server_python/requirements.txt

# Copy the rest of the application
COPY . .

# Build the assets
ARG BASE_URL
ENV BASE_URL=${BASE_URL:-http://localhost:4444}
RUN pnpm run build

# Expose the port that Azure Web App expects
EXPOSE 8080

# Create startup script to run the MCP server on the correct port
RUN echo '#!/bin/sh' > /app/start.sh && \
    echo 'echo "Starting MCP server..."' >> /app/start.sh && \
    echo '. /opt/venv/bin/activate' >> /app/start.sh && \
    echo 'PORT=${PORT:-8080}' >> /app/start.sh && \
    echo 'echo "Listening on port $PORT"' >> /app/start.sh && \
    echo 'uvicorn pizzaz_server_python.main:app --host 0.0.0.0 --port $PORT' >> /app/start.sh && \
    chmod +x /app/start.sh

# Start the server
CMD ["/app/start.sh"]
