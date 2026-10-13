#!/bin/bash
# Runs once at first boot. Output goes to /var/log/cloud-init-output.log.
set -euxo pipefail

REGION=us-east-1
ACCOUNT_ID=123456789012   # replace with your account id
REGISTRY=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

dnf install -y docker
systemctl enable --now docker

TOKEN=$(curl -sX PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
ZONE=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)

BACKEND_URL=$(aws ssm get-parameter --region $REGION --name /photo-wall/backend-url --query Parameter.Value --output text)

aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $REGISTRY
docker pull $REGISTRY/photowall-frontend:latest

# The log group /photo-wall/frontend is created in advance, so
# awslogs-create-group is not set: it would need logs:CreateLogGroup.
docker run -d --name frontend --restart always -p 3000:3000 \
  -e BACKEND_URL="$BACKEND_URL" -e DNS_RESOLVER=169.254.169.253 \
  -e INSTANCE_ID="$INSTANCE_ID" -e ZONE="$ZONE" \
  --log-driver awslogs --log-opt awslogs-region=$REGION \
  --log-opt awslogs-group=/photo-wall/frontend --log-opt awslogs-stream="$INSTANCE_ID" \
  $REGISTRY/photowall-frontend:latest
