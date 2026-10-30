
# AI-Driven Smart Warehouse & Product Forecasting

A responsive warehouse dashboard with authentication, inventory management, order fulfilment, DSA-based route/layout optimization, and an optional inference bridge to the XGBoost demand forecasting model trained in the Colab notebook.

## Features

- Registration/login with PBKDF2 password hashing
- Inventory CRUD, quantity adjustments, CSV export and shelf visualization
- FIFO order queue and picking-route optimization (Dijkstra + branch-and-bound TSP for small orders)
- AVL-tree low-stock lookup, heap-based demand ranking and 0/1 knapsack shelf optimization
- Optional trained-model forecast panel for explicit Favorita `store_nbr` and `item_nbr` IDs
- 7/14/30-day recursive demand predictions, optional quantile bands, promotion/festival assumptions
- Forecast summary with a simple lead-time reorder-point estimate
- Local JSON storage for the demo; configure persistent storage or a database before relying on hosted data

## Run locally

1. Install Python 3.11.
2. Open a terminal in this folder.
3. Run `python -m pip install -r requirements.txt`.
4. Run `python app.py`.
5. Visit `http://localhost:8000` and register a test account.

The app can start without the ML bundle; the forecasting panel will report that the model is not configured. Inventory and DSA features continue to work.

## Connect the trained Colab model

1. Open `AI_Driven_Smart_Product_Forecasting_System_Website_Integration.ipynb` in Google Colab.
2. Run all cells in order using the dataset source you intend to report. Confirm the final validation checks pass.
3. Run the new **Export a portable inference bundle** cell. It creates `ml_artifacts/inference_bundle.joblib` under the notebook output directory.
4. For local testing, copy that file to this project's `ml_artifacts/inference_bundle.joblib` path.
5. Restart `python app.py`, sign in, open **Demand analytics**, and enter a real `store_nbr` and `item_nbr` from the notebook's training data.

For Render, do not commit a large model bundle to Git unless you have reviewed repository size and licensing. Upload the bundle to trusted object storage that provides a direct download URL, then set the Render environment variable `ML_BUNDLE_URL` to that URL. `ML_BUNDLE_PATH` defaults to `/tmp/inference_bundle.joblib` in the provided Render configuration. Keep the URL private if your storage provider supports signed links. Redeploy after changing environment variables.

### Important mapping note

The sample warehouse products (for example `SKU-1001`) are demo records and are **not** automatically linked to Favorita dataset identifiers. The ML panel deliberately asks for explicit store and item IDs to avoid making a false mapping. A production integration should add verified `store_nbr` / `item_nbr` fields to each inventory SKU or train a model on the warehouse's own sales history.

### Model and data caveats

- The notebook must be executed to train the model and create the bundle. Uploading an `.ipynb` file alone does not supply a ready-to-serve model artifact.
- If the notebook falls back to synthetic demo sales, its metrics are demonstration-only and must not be presented as real Favorita performance.
- Promotion and festival controls are scenario assumptions. The data used here does not directly provide discount percentage or weather data.
- The reorder-point figure is an estimate using a fixed five-day lead time and an approximate variability-based safety stock. Validate lead time, costs, and service level for real operations.

## Deployment

Render uses `python app.py` and the platform `PORT`. The provided configuration installs the optional ML runtime. For persistent inventory and user data, configure a supported external database or persistent disk; the free ephemeral filesystem can reset on restarts/redeploys. Never rely on local `data.json` for production persistence.

## Security notes

- Use test credentials while evaluating the demo.
- Tokens are held in process memory and are invalidated on restart; this is a prototype, not a hardened production identity system.
- Review authorization, rate limiting, CSRF/origin policy, database access controls and secret management before public production use.

## Main files

- `app.py` — HTTP API and DSA logic
- `index.html` — responsive single-page dashboard
- `ml_forecast.py` — optional trained-model inference bridge
- `requirements.txt` — ML inference dependencies
- `render.yaml` — Render deployment configuration
- `AI_Driven_Smart_Product_Forecasting_System_Website_Integration.ipynb` — training notebook with portable-bundle export cell
