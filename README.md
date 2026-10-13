# Photo Wall

Two containers: `frontend` (nginx, port 3000) and `backend` (Flask + gunicorn, port 8080). Photos are stored in a private S3 bucket.

## Run locally

1. `cp .env.example .env` and fill in `BUCKET_NAME`, `UPLOAD_PASSWORD` and AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`).
2. `docker compose up --build`
3. Open http://localhost:3000

## Tests

```
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pytest
```

S3 is faked with moto; no AWS access needed.

Note: `docker-compose.yml` loads `.env` into the backend. Docker `.env` values must not be quoted.

In AWS, leave `UPLOAD_PASSWORD` unset; the backend reads the SecureString parameter named by `UPLOAD_PASSWORD_PARAM` (default `/photo-wall/upload-password`).

## Deploying on AWS

The app runs on EC2 servers in two auto scaling groups (frontend and backend), each behind a load balancer. The servers need the following, created in advance in `us-east-1`:

- Two ECR repositories, `photowall-frontend` and `photowall-backend`, holding the images built from `./frontend` and `./backend` (build with `--platform linux/amd64`).
- Parameter Store entries `/photo-wall/bucket-name` (String), `/photo-wall/upload-password` (SecureString) and `/photo-wall/backend-url` (String, `http://` plus the internal load balancer's DNS name).
- CloudWatch log groups `/photo-wall/frontend` and `/photo-wall/backend`.
- An instance role that can read those parameters, pull from ECR, write logs and use the S3 bucket (`LabInstanceProfile` in AWS Academy).

`deploy/user-data-backend.sh` and `deploy/user-data-frontend.sh` are the startup scripts for the backend and frontend launch templates. Replace the placeholder `ACCOUNT_ID` with your AWS account ID before pasting a script into a launch template. On first boot each script installs Docker, pulls its image from ECR and starts the container.

| Part     | Container port | Health check path |
|----------|----------------|-------------------|
| Frontend | 3000           | `/health`         |
| Backend  | 8080           | `/api/health`     |
