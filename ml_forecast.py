
"""Inference bridge for the Colab-trained Favorita forecasting model."""

from pathlib import Path
import os
import urllib.request

BASE = Path(__file__).resolve().parent
MODEL_PATH = BASE / "ml_artifacts" / "portable_model" / "main_model.json"
METADATA_PATH = BASE / "ml_artifacts" / "portable_model" / "inference_metadata.joblib"
DEFAULT_BUNDLE = BASE / "ml_artifacts" / "inference_bundle.joblib"


def _load_bundle():
    model_path = Path(os.environ.get("ML_MODEL_PATH", str(MODEL_PATH)))
    metadata_path = Path(os.environ.get("ML_METADATA_PATH", str(METADATA_PATH)))

    if model_path.exists() and metadata_path.exists():
        try:
            import joblib
            import xgboost as xgb

            model = xgb.XGBRegressor()
            model.load_model(str(model_path))

            bundle = joblib.load(metadata_path)
            bundle["model"] = model

            return bundle, None
        except Exception as exc:
            return None, f"Could not load portable model files: {exc}"

    path = Path(os.environ.get("ML_BUNDLE_PATH", str(DEFAULT_BUNDLE)))

    if not path.exists() and os.environ.get("ML_BUNDLE_URL"):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(
                os.environ["ML_BUNDLE_URL"],
                headers={"User-Agent": "SmartWarehouse-ML/1.0"}
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                path.write_bytes(response.read())
        except Exception as exc:
            return None, f"Could not download ML_BUNDLE_URL: {exc}"

    if not path.exists():
        return None, (
            "Model files not found. Expected main_model.json and "
            "inference_metadata.joblib in ml_artifacts/portable_model/."
        )

    try:
        import joblib
        return joblib.load(path), None
    except Exception as exc:
        return None, f"Could not load model bundle: {exc}"


def status():
    bundle, error = _load_bundle()

    if error:
        return {"available": False, "message": error}

    return {
        "available": True,
        "data_source": bundle.get("data_source", "unknown"),
        "train_end": str(bundle.get("train_end", "unknown")),
        "supported_horizons": [7, 14, 30]
    }


def forecast(store_id, item_id, horizon=7, promotion=False, festival=False):
    if horizon not in (7, 14, 30):
        raise ValueError("horizon must be 7, 14, or 30 days")

    bundle, error = _load_bundle()

    if error:
        raise RuntimeError(error)

    import numpy as np
    import pandas as pd

    model = bundle["model"]
    feature_cols = bundle["feature_cols"]
    history = bundle["history"]

    store_id = int(store_id)
    item_id = int(item_id)

    hist = history[
        (history.store_nbr == store_id) &
        (history.item_nbr == item_id)
    ].sort_values("date")

    if hist.empty:
        raise LookupError(
            "No training history found for this store_id and item_id. "
            "Choose IDs present in the Favorita dataset."
        )

    sales_history = hist.unit_sales.astype(float).tolist()
    last_date = pd.Timestamp(hist.date.max())
    static = hist.iloc[-1]

    holiday_dates = set(
        pd.to_datetime(
            bundle.get("holiday_dates", []), errors="coerce"
        ).dropna().normalize()
    )

    records = []
    quantile_models = bundle.get("quantile_models", {})

    for step, dt in enumerate(
        pd.date_range(
            last_date + pd.Timedelta(days=1),
            periods=horizon,
            freq="D"
        )
    ):
        dow = dt.dayofweek
        promo = int(bool(promotion))
        festival_flag = int(
            bool(festival) or dt.normalize() in holiday_dates
        )

        def lag_value(k):
            return sales_history[-k] if len(sales_history) >= k else 0.0

        row = {
            c: (
                float(static[c])
                if c in static.index and pd.notna(static[c])
                else 0.0
            )
            for c in feature_cols
        }

        row.update({
            "store_nbr": store_id,
            "item_nbr": item_id,
            "onpromotion": promo,
            "is_holiday": festival_flag,
            "festival_flag": festival_flag,
            "day_of_week": dow,
            "month": dt.month,
            "day_of_month": dt.day,
            "week_of_year": int(dt.isocalendar().week),
            "year": dt.year,
            "is_weekend": int(dow >= 5),
            "dow_sin": np.sin(2 * np.pi * dow / 7),
            "dow_cos": np.cos(2 * np.pi * dow / 7),
            "month_sin": np.sin(2 * np.pi * dt.month / 12),
            "month_cos": np.cos(2 * np.pi * dt.month / 12),
            "promotion_weekend": promo * int(dow >= 5),
            "promotion_festival": promo * festival_flag,
            "lag_1": lag_value(1),
            "lag_7": lag_value(7),
            "lag_14": lag_value(14),
            "lag_28": lag_value(28),
            "lag_30": lag_value(30),
            "rolling_mean_7": (
                float(np.mean(sales_history[-7:]))
                if sales_history else 0.0
            ),
            "rolling_std_7": (
                float(np.std(sales_history[-7:], ddof=1))
                if len(sales_history) > 1 else 0.0
            ),
            "rolling_mean_28": (
                float(np.mean(sales_history[-28:]))
                if sales_history else 0.0
            ),
            "rolling_std_28": (
                float(np.std(sales_history[-28:], ddof=1))
                if len(sales_history) > 1 else 0.0
            )
        })

        x = (
            pd.DataFrame([row], columns=feature_cols)
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0)
        )

        pred = max(0.0, float(model.predict(x)[0]))

        rec = {
            "date": dt.strftime("%Y-%m-%d"),
            "predicted_demand": round(pred, 3),
            "promotion_assumption": bool(promo),
            "festival_proxy_assumption": bool(festival_flag)
        }

        if all(q in quantile_models for q in (0.1, 0.5, 0.9)):
            rec["q10"] = max(
                0.0, float(quantile_models[0.1].predict(x)[0])
            )
            rec["q50"] = max(
                0.0, float(quantile_models[0.5].predict(x)[0])
            )
            rec["q90"] = max(
                0.0, float(quantile_models[0.9].predict(x)[0])
            )

        records.append(rec)
        sales_history.append(pred)

    values = np.asarray(
        [r["predicted_demand"] for r in records], dtype=float
    )

    daily_mean = float(values.mean())
    lead_time = 5

    safety_stock = (
        1.645 *
        float(values.std(ddof=1) if len(values) > 1 else 0.0) *
        np.sqrt(lead_time)
    )

    reorder_point = daily_mean * lead_time + safety_stock

    return {
        "store_id": store_id,
        "item_id": item_id,
        "horizon": horizon,
        "data_source": bundle.get("data_source", "unknown"),
        "train_end": str(bundle.get("train_end", "unknown")),
        "forecast": records,
        "summary": {
            "forecast_total": round(float(values.sum()), 2),
            "average_daily_demand": round(daily_mean, 2),
            "lead_time_days": lead_time,
            "safety_stock_estimate": round(float(safety_stock), 2),
            "reorder_point_estimate": round(float(reorder_point), 2)
        }
    }
