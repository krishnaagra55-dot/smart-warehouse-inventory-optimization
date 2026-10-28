<<<<<<< HEAD
# Nexus Warehouse — Smart Inventory & Route Optimization

A full-stack warehouse operations dashboard built with Python's standard library and a responsive HTML/CSS/JavaScript frontend. Created as a DSA-II project for inventory management, demand analytics, shelf placement, and order picking-route optimization.

## Features

- Responsive dashboard with stock, SKU, storage-utilization, and order KPIs
- User registration and login with salted PBKDF2-SHA256 password hashes
- Inventory creation, SKU lookup, stock adjustments, search, and stock-health filters
- CSV export for inventory
- Warehouse shelf map with the latest picking route highlighted
- FIFO order queue and order fulfilment workflow
- Shortest-path picking using Dijkstra's algorithm; backtracking TSP search for small pick lists
- Demand ranking with Heap Sort and restock prioritization with a priority queue
- Low-stock range queries using an AVL tree
- 0/1 Knapsack-based selection of high-demand items for prime shelf capacity
- Greedy nearest-available shelf assignment
- Local JSON persistence generated automatically by the server

## Requirements

- Python 3.8 or later
- A modern web browser
- No third-party Python packages are required

## Run locally

1. Download or clone this repository.
2. Open a terminal in the project folder.
3. Run:

   ```bash
   python app.py
   ```

   On Windows, `py app.py` may be used if the `python` command is unavailable.

4. Open <http://localhost:8000>.
5. Register a test account and explore the dashboard.

Stop the server with `Ctrl+C` in the terminal.

### Windows one-click launcher

Double-click `run.bat` to start the server. Then open <http://localhost:8000> in your browser.

## DSA concepts

| Concept | Project use |
| --- | --- |
| Hash table | SKU-to-item lookup |
| AVL tree | Low-stock quantity range queries |
| Heap Sort | Demand ranking |
| Priority queue / heap | Restock prioritization |
| Graph + Dijkstra | Shortest warehouse walking paths |
| Backtracking + branch and bound | Small-order picking-route search (TSP) |
| 0/1 Knapsack (dynamic programming) | Selecting SKUs for prime shelf space |
| FIFO queue | Pending orders |
| Greedy allocation | Assigning new stock to available shelves |

## Data and security notes

- `data.json` is generated at runtime and is intentionally excluded from Git because it may contain account hashes and operational records.
- Use test credentials. This educational demo is not a production-ready, internet-facing warehouse system.
- Before public deployment, add HTTPS, stronger session management, rate limiting, role-based access control, CSRF protections where relevant, robust input validation, and a managed persistent database.
- The app currently uses in-memory authentication tokens; restarting the server invalidates active sessions.

## Project structure

```text
smart-warehouse-optimization/
├── app.py          # Python backend, REST API, DSA algorithms
├── index.html      # Responsive frontend dashboard
├── README.md       # Project documentation
├── .gitignore      # Excludes local data and generated files
└── run.bat         # Windows one-click launcher
```
=======
# smart-warehouse-inventory-optimization
>>>>>>> b92675500ceb0e92ac5cb67a3317f3c12f9067a2
