# Arquitectura

```text
data/raw
   ↓
src/data
   ↓
src/features
   ↓
src/models
   ↓
artifacts/models + reports/metrics
   ↓
api (FastAPI) → Docker → ECR / ECS Fargate
   ↓
Prometheus (/metrics, alertas de drift)
```

El pipeline de entrenamiento no cambia al servir el modelo. La API carga `churn_pipeline.joblib`, valida el contrato con Pydantic y aplica el umbral de `params.yaml`. Docker fija el entorno de inferencia. Prometheus observa latencia, volumen de predicciones y la distribución de entradas para detectar data drift antes de decidir un reentrenamiento o un rollback.
