## Build Docker Image
docker build -t log_api . 

## Stop and Remove Container
if already run container with name mobile-log-api
docker stop mobile-log-api
docker rm mobile-log-api

## Run Docker Image
docker run --name mobile-log-api -d -p 5001:5000 --env-file ./conf/.env -v "$(Get-Location)/uploads:/app/uploads" -v "$(Get-Location)/instance:/app/instance" log_api