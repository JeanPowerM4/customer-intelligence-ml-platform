"""NovaTel customer churn prediction API."""

from __future__ import annotations

from io import StringIO
from time import perf_counter
from typing import Annotated

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.exposition import CONTENT_TYPE_LATEST

from api.dependencies import get_model, get_prediction_threshold
from api.schemas import CustomerInput, PredictionResponse
from src.models.prediction import predict_customers

app = FastAPI(
    title="NovaTel Customer Churn API",
    description=(
        "API REST para predicción de churn de clientes de NovaTel."
    ),
    version="1.0.0",
)

PREDICTIONS_TOTAL = Counter(
    "churn_predictions_total",
    "Total number of individual churn predictions",
    ["result"],
)
PREDICTION_LATENCY = Histogram(
    "churn_prediction_latency_seconds",
    "Latency of individual churn predictions",
)
CHURN_PROBABILITY = Histogram(
    "churn_probability",
    "Distribution of predicted churn probability",
    buckets=(0.1, 0.25, 0.5, 0.75, 0.9, 1.0),
)
INPUT_MONTHLY_FEE = Histogram(
    "churn_input_monthly_fee",
    "Distribution of monthly fee received by the model",
    buckets=(40, 60, 80, 100, 120, 150, 200),
)
INPUT_SUPPORT_CALLS = Histogram(
    "churn_input_support_calls",
    "Distribution of support calls received by the model",
    buckets=(0, 1, 2, 3, 5, 8, 12),
)
INPUT_PAYMENT_DELAY = Histogram(
    "churn_input_payment_delay_days",
    "Distribution of last payment delay received by the model",
    buckets=(0, 3, 7, 15, 30, 60, 90),
)
INPUT_DIGITAL_USAGE = Histogram(
    "churn_input_digital_usage_score",
    "Distribution of digital usage score received by the model",
    buckets=(1, 2, 4, 6, 8, 10),
)
LAST_CHURN_PROBABILITY = Gauge(
    "churn_last_probability",
    "Churn probability from the most recent prediction",
)


def _record_prediction(customer: CustomerInput, row: pd.Series, elapsed: float) -> float:
    probability = float(row["churn_probability"])
    prediction = int(row["churn_prediction"])

    PREDICTIONS_TOTAL.labels(result=str(prediction)).inc()
    CHURN_PROBABILITY.observe(probability)
    LAST_CHURN_PROBABILITY.set(probability)
    INPUT_MONTHLY_FEE.observe(customer.monthly_fee)
    INPUT_SUPPORT_CALLS.observe(customer.support_calls)
    INPUT_PAYMENT_DELAY.observe(customer.last_payment_delay)
    INPUT_DIGITAL_USAGE.observe(customer.digital_usage_score)
    PREDICTION_LATENCY.observe(elapsed)
    return probability


@app.get("/")
def root():
    return {
        "service": "customer-churn-api",
        "version": "1.0.0",
    }


@app.get("/health")
def health():
    get_model()
    return {
        "status": "healthy",
        "service": "customer-churn-api",
    }


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict", response_model=PredictionResponse)
def predict(customer: CustomerInput):
    start_time = perf_counter()
    try:
        model = get_model()
        threshold = get_prediction_threshold()
        dataframe = pd.DataFrame([customer.model_dump()])
        result = predict_customers(
            model=model,
            dataframe=dataframe,
            threshold=threshold,
        )
        row = result.iloc[0]
        probability = _record_prediction(
            customer,
            row,
            perf_counter() - start_time,
        )
        return PredictionResponse(
            customer_id=(
                str(row["customer_id"])
                if "customer_id" in result.columns
                else None
            ),
            churn_probability=probability,
            churn_prediction=int(row["churn_prediction"]),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/predict/batch")
async def predict_batch(file: Annotated[UploadFile, File()]):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=400,
            detail="The CSV file is empty.",
        )

    try:
        dataframe = pd.read_csv(StringIO(content.decode("utf-8")))
        if dataframe.empty:
            raise HTTPException(
                status_code=400,
                detail="The CSV file is empty.",
            )

        result = predict_customers(
            model=get_model(),
            dataframe=dataframe,
            threshold=get_prediction_threshold(),
        )
        output = StringIO()
        result.to_csv(output, index=False)
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="predictions.csv"'
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
