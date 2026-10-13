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

BUCKET_NAME=$(aws ssm get-parameter --region $REGION --name /photo-wall/bucket-name --query Parameter.Value --output text)

aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $REGISTRY
docker pull $REGISTRY/photowall-backend:latest

# The log group /photo-wall/backend is created in advance, so
# awslogs-create-group is not set: it would need logs:CreateLogGroup.
# The upload password is not passed here: the backend reads it from Parameter Store itself.
docker run -d --name backend --restart always -p 8080:8080 \
  -e PORT=8080 -e AWS_REGION=$REGION -e BUCKET_NAME="$BUCKET_NAME" \
  -e INSTANCE_ID="$INSTANCE_ID" -e ZONE="$ZONE" \
  --log-driver awslogs --log-opt awslogs-region=$REGION \
  --log-opt awslogs-group=/photo-wall/backend --log-opt awslogs-stream="$INSTANCE_ID" \
  $REGISTRY/photowall-backend:latest
