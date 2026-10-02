# Despliegue en AWS

La imagen `novatel-churn-api` se publica en Amazon ECR y se ejecuta con ECS Express sobre Fargate. El cliente consume un endpoint HTTPS; el balanceador redirige al puerto 8000 del contenedor y usa `GET /health`.

## Antes de desplegar

1. Entrenar el modelo para que exista `artifacts/models/churn_pipeline.joblib`.
2. Tener AWS CLI autenticado en `us-east-1`.
3. Tener Docker en ejecución.

El script `scripts/deploy_aws.sh` crea un repositorio ECR, sube la imagen `aws-v1` y levanta el servicio `novatel-churn-api`. Esos recursos pueden generar costo. El script no se ejecuta solo: hay que lanzarlo de forma consciente y borrarlos al terminar el laboratorio.

## Comprobación

```bash
curl -i "https://${ENDPOINT}/health"
curl -sS -X POST "https://${ENDPOINT}/predict" \
  -H "Content-Type: application/json" \
  -d @docs/deployment/sample_customer.json
```

## Apagado

```bash
aws ecs delete-express-gateway-service \
  --service-arn "$SERVICE_ARN" \
  --region us-east-1
```

La imagen puede permanecer en ECR. El servicio en ejecución es lo que conviene eliminar al cerrar la práctica.
