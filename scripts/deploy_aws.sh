#!/usr/bin/env bash
# Publica la API de churn en ECR y la ejecuta con ECS Express (Fargate).
# Crea recursos que pueden generar costo. Eliminar el servicio al terminar.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
REPOSITORY="novatel-churn-api"
IMAGE_TAG="aws-v1"
SERVICE_NAME="novatel-churn-api"

if [[ ! -f artifacts/models/churn_pipeline.joblib ]]; then
  echo "Falta el modelo. Ejecuta primero: python main.py train --data data/raw/customer_churn.csv"
  exit 1
fi

aws ecr describe-repositories \
  --repository-names "$REPOSITORY" \
  --region "$REGION" >/dev/null 2>&1 \
|| aws ecr create-repository \
  --repository-name "$REPOSITORY" \
  --image-scanning-configuration scanOnPush=true \
  --image-tag-mutability MUTABLE \
  --region "$REGION"

ECR_URI="$(aws ecr describe-repositories \
  --repository-names "$REPOSITORY" \
  --region "$REGION" \
  --query 'repositories[0].repositoryUri' \
  --output text)"
ECR_REGISTRY="${ECR_URI%%/*}"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  --load \
  -t "${REPOSITORY}:${IMAGE_TAG}" \
  .

docker tag "${REPOSITORY}:${IMAGE_TAG}" "${ECR_URI}:${IMAGE_TAG}"
docker push "${ECR_URI}:${IMAGE_TAG}"

cat > /tmp/ecs-task-trust.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

cat > /tmp/ecs-infra-trust.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "AllowAccessInfrastructureForECSExpressServices",
    "Effect": "Allow",
    "Principal": {"Service": "ecs.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam get-role --role-name ecsTaskExecutionRole >/dev/null 2>&1 \
  || aws iam create-role \
    --role-name ecsTaskExecutionRole \
    --assume-role-policy-document file:///tmp/ecs-task-trust.json

aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

aws iam get-role --role-name ecsInfrastructureRoleForExpressServices >/dev/null 2>&1 \
  || aws iam create-role \
    --role-name ecsInfrastructureRoleForExpressServices \
    --assume-role-policy-document file:///tmp/ecs-infra-trust.json

aws iam attach-role-policy \
  --role-name ecsInfrastructureRoleForExpressServices \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices

EXECUTION_ROLE_ARN="$(aws iam get-role \
  --role-name ecsTaskExecutionRole \
  --query 'Role.Arn' \
  --output text)"
INFRA_ROLE_ARN="$(aws iam get-role \
  --role-name ecsInfrastructureRoleForExpressServices \
  --query 'Role.Arn' \
  --output text)"

aws ecs create-express-gateway-service \
  --service-name "$SERVICE_NAME" \
  --primary-container "image=${ECR_URI}:${IMAGE_TAG},containerPort=8000" \
  --execution-role-arn "$EXECUTION_ROLE_ARN" \
  --infrastructure-role-arn "$INFRA_ROLE_ARN" \
  --health-check-path "/health" \
  --cpu "256" \
  --memory "512" \
  --scaling-target "minTaskCount=1,maxTaskCount=1,autoScalingMetric=AVERAGE_CPU,autoScalingTargetValue=60" \
  --monitor-resources DEPLOYMENT \
  --monitor-mode TEXT-ONLY \
  --region "$REGION"

echo "Servicio solicitado. Consulta el endpoint con describe-express-gateway-service."
echo "Para apagarlo, usa el comando de docs/deployment/aws.md."
