# Customer Intelligence ML Platform

Sistema de predicción de churn de **NovaTel Perú S.A.C.**, del desarrollo del modelo a su operación.

El curso 1 deja un pipeline reproducible. El curso 2 lo expone como API, lo empaqueta en Docker, lo puede desplegar en AWS y lo observa con Prometheus.

## Qué incluye

- Dataset sintético y diccionario en `data/raw/`.
- Módulos reutilizables en `src/` (datos, features, modelos).
- Notebooks de entendimiento, entrenamiento, evaluación, validación y predicción batch.
- CLI de entrenamiento y predicción.
- Pruebas con pytest y CI en GitHub Actions.
- Versionado de datos y pipeline con DVC.
- API FastAPI: `GET /`, `GET /health`, `POST /predict`, `POST /predict/batch`, `GET /metrics`.
- Imagen Docker, Docker Compose y alertas de drift en Prometheus.
- Script de despliegue a ECR + ECS Express.

## Instalación

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Entrenamiento y pruebas

```bash
python main.py train --data data/raw/customer_churn.csv
pytest -q
```

El modelo queda en `artifacts/models/churn_pipeline.joblib`. No se versiona en Git; se reconstruye con el comando anterior o con `dvc repro`.

## API local

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Documentación interactiva: http://localhost:8000/docs

## Contenedor y monitoreo

Hace falta el modelo entrenado antes de construir la imagen.

```bash
docker compose up -d --build
curl http://localhost:8000/health
python monitoring/simulate_traffic.py --scenario normal --requests 50
python monitoring/simulate_traffic.py --scenario drift --requests 50
```

Prometheus queda en http://localhost:9090. La alerta `HighAveragePaymentDelay` se dispara cuando el atraso promedio de pago supera 15 días.

## AWS

Ver `docs/deployment/aws.md`. El despliegue crea recursos con costo; hay que apagar el servicio al terminar.

## Pipeline DVC

```bash
dvc repro
dvc metrics show
```
