From root directory

Build Container:
docker build -t tower-hamlets-dashboard:latest dashboard/

Run Container:
docker run -p 8501:8501 -v ~/.aws:/root/.aws tower-hamlets-dashboard:latest