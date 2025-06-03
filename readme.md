## Stop and Remove Container

# if already run container with name mobile-log-api remove first

docker compose down log_api_app

## Run Docker Compose for build and deploy app, db, and redis

docker compose up -d --build

<!-- ## Run Docker Image

# For Windows:

docker run --name mobile-log-api -d -p 5001:5000 -e LOG_RETENTION_DAYS=45 -v "$(Get-Location)/uploads:/app/uploads" -v "$(Get-Location)/instance:/app/instance" log_api

# For MAC/Linux

docker run --name mobile-log-api -d -p 5001:5000 --env-file ./conf/.env -v $(pwd)/uploads:/app/uploads -v $(pwd)/instance:/app/instance log_api -->
