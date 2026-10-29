# Smart Warehouse — Inventory & Route Optimization

A full-stack warehouse operations dashboard built with Python's standard library and a responsive HTML, CSS, and JavaScript frontend.

## Features

- Inventory dashboard and stock analytics
- User registration and login
- Inventory creation, search, and stock adjustments
- CSV inventory export
- Warehouse shelf visualization
- FIFO order processing
- Route optimization using Dijkstra's algorithm
- Demand ranking and restock prioritization
- Low-stock queries using an AVL tree
- Knapsack-based inventory optimization
- Local JSON persistence

## Requirements

- Python 3.8 or later
- A modern web browser
- No third-party Python packages required for local execution

## Run locally

1. Open a terminal in the project folder.
2. Run `python app.py`.
3. Open `http://localhost:8000` in your browser.
4. Register a test account and explore the dashboard.

## Deployment

The application can be hosted on a Python-compatible service such as Render. Configure the service to start with `python app.py` and use the platform-provided `PORT` environment variable.

**Important:** The current application stores data locally in `data.json`. Configure persistent storage or a database before relying on production data. Do not use real customer information until authentication, storage, and security have been reviewed.
