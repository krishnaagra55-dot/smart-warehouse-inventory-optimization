#!/usr/bin/env python3
"""AI-Driven Smart Warehouse Inventory & Optimization System (DSA-II PBL).
Backend + DSA engine. Standard library only:  python app.py  ->  http://localhost:8000
"""
import json, os, secrets, hashlib, heapq, threading
from collections import deque
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.environ.get("DATA_DIR", BASE), "data.json")
LOCK = threading.Lock()

# ───────── Unit 1: Hash table (SKU -> item, chaining, O(1) avg) ─────────
class HashTable:
    def __init__(s, n=16): s.b = [[] for _ in range(n)]; s.n = 0
    def _i(s, k): return sum(ord(c) * 31 ** i for i, c in enumerate(k)) % len(s.b)
    def put(s, k, v):
        for p in s.b[s._i(k)]:
            if p[0] == k: p[1] = v; return
        s.b[s._i(k)].append([k, v]); s.n += 1
        if s.n > 2 * len(s.b):
            old = [p for b in s.b for p in b]; s.b = [[] for _ in range(2 * len(s.b))]; s.n = 0
            for k2, v2 in old: s.put(k2, v2)
    def get(s, k):
        for p in s.b[s._i(k)]:
            if p[0] == k: return p[1]
    def values(s): return [p[1] for b in s.b for p in b]

# ───────── Unit 1: AVL tree keyed by (qty, sku) for low-stock range queries ─────────
class Node:
    def __init__(s, k): s.k = k; s.l = s.r = None; s.h = 1
def H(n): return n.h if n else 0
def upd(n): n.h = 1 + max(H(n.l), H(n.r))
def rot_r(y): x = y.l; y.l = x.r; x.r = y; upd(y); upd(x); return x
def rot_l(x): y = x.r; x.r = y.l; y.l = x; upd(x); upd(y); return y
def rebalance(n):
    upd(n); b = H(n.l) - H(n.r)
    if b > 1:
        if H(n.l.l) < H(n.l.r): n.l = rot_l(n.l)
        return rot_r(n)
    if b < -1:
        if H(n.r.r) < H(n.r.l): n.r = rot_r(n.r)
        return rot_l(n)
    return n
def avl_ins(n, k):
    if not n: return Node(k)
    if k < n.k: n.l = avl_ins(n.l, k)
    else: n.r = avl_ins(n.r, k)
    return rebalance(n)
def avl_del(n, k):
    if not n: return None
    if k < n.k: n.l = avl_del(n.l, k)
    elif k > n.k: n.r = avl_del(n.r, k)
    else:
        if not n.l: return n.r
        if not n.r: return n.l
        m = n.r
        while m.l: m = m.l
        n.k = m.k; n.r = avl_del(n.r, m.k)
    return rebalance(n)
def avl_range(n, lo, hi, out):
    if not n: return
    if lo < n.k: avl_range(n.l, lo, hi, out)
    if lo <= n.k <= hi: out.append(n.k)
    if n.k < hi: avl_range(n.r, lo, hi, out)

# ───────── Unit 1: Heap sort + priority queue ─────────
def heap_sort_desc(a, key):
    a = a[:]; n = len(a)
    def sift(i, n):  # min-heap sift-down -> final array is descending
        while True:
            l, r, m = 2 * i + 1, 2 * i + 2, i
            if l < n and key(a[l]) < key(a[m]): m = l
            if r < n and key(a[r]) < key(a[m]): m = r
            if m == i: return
            a[i], a[m] = a[m], a[i]; i = m
    for i in range(n // 2 - 1, -1, -1): sift(i, n)
    for e in range(n - 1, 0, -1): a[0], a[e] = a[e], a[0]; sift(0, e)
    return a

# ───────── Unit 2: Warehouse graph, Dijkstra ─────────
ROWS, COLS, SHCAP = 4, 5, 30          # node 0 = dock, others = shelves
def nid(r, c): return r * COLS + c
G = {i: [] for i in range(ROWS * COLS)}
for r in range(ROWS):
    for c in range(COLS):
        if c + 1 < COLS: a, b = nid(r, c), nid(r, c + 1); G[a].append((b, 1)); G[b].append((a, 1))
        if r + 1 < ROWS: a, b = nid(r, c), nid(r + 1, c); G[a].append((b, 2)); G[b].append((a, 2))  # cross-aisle costs 2
def dijkstra(src):
    d = {i: 10**9 for i in G}; p = {}; d[src] = 0; pq = [(0, src)]
    while pq:
        du, u = heapq.heappop(pq)
        if du > d[u]: continue
        for v, w in G[u]:
            if du + w < d[v]: d[v] = du + w; p[v] = u; heapq.heappush(pq, (d[v], v))
    return d, p
DIST = {i: dijkstra(i) for i in G}
SHELVES = sorted(range(1, ROWS * COLS), key=lambda n: DIST[0][0][n])  # nearest-to-dock first

def walk(seq):
    """Dock -> seq -> dock using shortest paths. Returns (total distance, node path)."""
    full, tot, cur = [0], 0, 0
    for x in list(seq) + [0]:
        d, p = DIST[cur]; seg = [x]
        while seg[-1] != cur: seg.append(p[seg[-1]])
        full += seg[::-1][1:]; tot += d[x]; cur = x
    return tot, full

# ───────── Unit 4: Backtracking (TSP with branch & bound pruning) ─────────
def tsp(nodes):
    best = [10**9, list(nodes)]
    def go(cur, left, path, cost):
        if cost >= best[0]: return          # bound
        if not left:
            t = cost + DIST[cur][0][0]
            if t < best[0]: best[0] = t; best[1] = path[:]
            return
        for x in list(left):
            left.remove(x); path.append(x)
            go(x, left, path, cost + DIST[cur][0][x])
            path.pop(); left.add(x)
    go(0, set(nodes), [], 0)
    return best[1]

# ───────── Unit 3: 0/1 Knapsack (which SKUs earn prime shelf space) ─────────
def knapsack(ws, vs, cap):
    n = len(ws); dp = [[0] * (cap + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for c in range(cap + 1):
            dp[i][c] = dp[i - 1][c]
            if ws[i - 1] <= c: dp[i][c] = max(dp[i][c], dp[i - 1][c - ws[i - 1]] + vs[i - 1])
    c, pick = cap, []
    for i in range(n, 0, -1):
        if dp[i][c] != dp[i - 1][c]: pick.append(i - 1); c -= ws[i - 1]
    return dp[n][cap], pick

# ───────── State ─────────
HT = HashTable(); AVL = None; Q = deque(); HIST = []; USERS = {}; TOK = {}; NEXT = [1]
SEED = [("SKU-1001", "Laptop 15in", 25, 12, 90), ("SKU-1002", "Wireless Mouse", 120, 5, 95),
        ("SKU-1003", "Mechanical Keyboard", 60, 8, 70), ("SKU-1004", "27in Monitor", 18, 20, 60),
        ("SKU-1005", "Office Chair", 12, 25, 25), ("SKU-1006", "USB-C Cable", 300, 6, 98),
        ("SKU-1007", "Webcam HD", 40, 9, 55), ("SKU-1008", "Standing Desk", 6, 28, 15),
        ("SKU-1009", "Headphones", 55, 10, 80), ("SKU-1010", "Printer", 9, 22, 20),
        ("SKU-1011", "Power Bank", 80, 7, 85), ("SKU-1012", "Router", 30, 11, 50),
        ("SKU-1013", "Tablet", 14, 8, 65), ("SKU-1014", "Desk Lamp", 45, 14, 30)]

def free_map():
    f = {n: SHCAP for n in SHELVES}
    for it in HT.values():
        if it["shelf"] in f: f[it["shelf"]] -= it["size"]
    return f
def place(items, shelves=None, free=None):
    free = free if free is not None else {n: SHCAP for n in SHELVES}
    for it in items:                        # greedy first-fit
        it["shelf"] = next((n for n in (shelves or SHELVES) if free[n] >= it["size"]), None)
        if it["shelf"]: free[it["shelf"]] -= it["size"]
def setqty(it, q):
    global AVL
    AVL = avl_del(AVL, (it["qty"], it["sku"])); it["qty"] = q; AVL = avl_ins(AVL, (q, it["sku"]))
def wdist():
    its = HT.values(); t = sum(i["demand"] for i in its) or 1
    return round(sum(i["demand"] * DIST[0][0][i["shelf"]] for i in its) / t, 2)

def save():
    with open(DB, "w") as f:
        json.dump({"users": USERS, "items": HT.values(), "q": list(Q), "hist": HIST[-50:], "next": NEXT[0]}, f)
def load():
    global AVL
    if os.path.exists(DB):
        d = json.load(open(DB)); USERS.update(d["users"]); HIST.extend(d["hist"]); NEXT[0] = d["next"]; Q.extend(d["q"])
        for it in d["items"]: HT.put(it["sku"], it); AVL = avl_ins(AVL, (it["qty"], it["sku"]))
    else:
        items = [dict(sku=s, name=n, qty=q, size=z, demand=d, shelf=None) for s, n, q, z, d in SEED]
        place(items, SHELVES[::-1])          # baseline FIFO layout: far shelves first
        for it in items: HT.put(it["sku"], it); AVL = avl_ins(AVL, (it["qty"], it["sku"]))
        save()

def hash_pw(pw, salt): return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 120_000).hex()

# ───────── API ─────────
def err(m, c=400): return {"error": m}, c
def api(m, p, q, b, user):
    global AVL, Q
    if p == "/api/register" and m == "POST":
        u, pw = str(b.get("username", "")).strip().lower(), str(b.get("password", ""))
        if len(u) < 3 or len(pw) < 6: return err("Username min 3 chars, password min 6 chars")
        if u in USERS: return err("Username already taken", 409)
        salt = secrets.token_hex(16); USERS[u] = {"salt": salt, "hash": hash_pw(pw, salt)}; save()
        t = secrets.token_hex(24); TOK[t] = u; return {"token": t, "user": u}, 200
    if p == "/api/login" and m == "POST":
        u, pw = str(b.get("username", "")).strip().lower(), str(b.get("password", ""))
        r = USERS.get(u)
        if not r or not secrets.compare_digest(r["hash"], hash_pw(pw, r["salt"])): return err("Invalid credentials", 401)
        t = secrets.token_hex(24); TOK[t] = u; return {"token": t, "user": u}, 200
    if not user: return err("Unauthorized", 401)

    if p == "/api/items" and m == "GET":
        return {"items": sorted(HT.values(), key=lambda i: i["sku"]), "rows": ROWS, "cols": COLS, "cap": SHCAP}, 200
    if p == "/api/items" and m == "POST":
        try:
            it = dict(sku=str(b["sku"]).strip().upper(), name=str(b["name"]).strip(), qty=int(b["qty"]),
                      size=int(b["size"]), demand=int(b["demand"]), shelf=None)
        except (KeyError, ValueError): return err("Fill all fields with valid numbers")
        if not it["sku"] or not it["name"] or it["qty"] < 0 or not 1 <= it["size"] <= SHCAP or not 0 <= it["demand"] <= 100:
            return err(f"Invalid values (size 1-{SHCAP}, demand 0-100, qty >= 0)")
        if HT.get(it["sku"]): return err("SKU already exists", 409)
        place([it], free=free_map())
        if not it["shelf"]: return err("No shelf has enough free space")
        HT.put(it["sku"], it); AVL = avl_ins(AVL, (it["qty"], it["sku"])); save(); return {"ok": True, "shelf": it["shelf"]}, 200
    if p == "/api/item" and m == "GET":
        it = HT.get(q.get("sku", [""])[0].strip().upper()); return ({"item": it}, 200) if it else err("SKU not found", 404)
    if p == "/api/stock" and m == "POST":
        it = HT.get(str(b.get("sku", "")).upper())
        try: nq = it["qty"] + int(b["delta"])
        except (TypeError, KeyError, ValueError): return err("Invalid request")
        if nq < 0: return err("Stock cannot go below zero")
        setqty(it, nq); save(); return {"ok": True}, 200
    if p == "/api/orders" and m == "POST":
        lines = {}
        for l in b.get("lines", []):
            s = str(l.get("sku", "")).upper()
            if not HT.get(s): return err(f"Unknown SKU {s}")
            try: n = int(l["qty"])
            except (KeyError, ValueError): return err("Bad quantity")
            if n < 1: return err("Quantity must be >= 1")
            lines[s] = lines.get(s, 0) + n
        if not lines: return err("Order is empty")
        Q.append({"id": NEXT[0], "user": user, "lines": [{"sku": k, "qty": v} for k, v in lines.items()]}); NEXT[0] += 1
        save(); return {"ok": True}, 200
    if p == "/api/orders" and m == "GET": return {"queue": list(Q), "history": HIST[-10:][::-1]}, 200
    if p == "/api/process" and m == "POST":
        keep, done = deque(), 0
        while Q:
            o = Q.popleft()
            if not all(HT.get(l["sku"])["qty"] >= l["qty"] for l in o["lines"]): keep.append(o); continue
            nodes = []
            for l in o["lines"]:
                it = HT.get(l["sku"]); setqty(it, it["qty"] - l["qty"])
                if it["shelf"] not in nodes: nodes.append(it["shelf"])
            naive, _ = walk(nodes)                                   # FIFO pick order
            order = tsp(nodes) if len(nodes) <= 8 else sorted(nodes, key=lambda n: DIST[0][0][n])
            opt, path = walk(order)
            HIST.append({"id": o["id"], "lines": o["lines"], "naive": naive, "opt": opt, "path": path, "order": order}); done += 1
        Q = keep; save(); return {"processed": done, "pending": len(Q), "last": HIST[-1] if done else None}, 200
    if p == "/api/optimize" and m == "POST":
        its = sorted(HT.values(), key=lambda i: -i["demand"]); before = wdist()
        cap = 4 * SHCAP; val, pick = knapsack([i["size"] for i in its], [i["demand"] for i in its], cap)
        prime = [its[i] for i in pick]; rest = [i for i in its if i not in prime]
        place(prime + rest); save()
        return {"before": before, "after": wdist(), "prime": [i["sku"] for i in prime], "value": val}, 200
    if p == "/api/analytics" and m == "GET":
        its = HT.values(); mx = int(q.get("max", ["20"])[0]); low = []
        avl_range(AVL, (-1, ""), (mx, "\uffff"), low)
        pq = [(-i["demand"] / (i["qty"] + 1), i["sku"]) for i in its]; heapq.heapify(pq)
        restock = [heapq.heappop(pq)[1] for _ in range(min(5, len(pq)))]
        used = sum(i["size"] for i in its); sv = [h["naive"] - h["opt"] for h in HIST]; tn = sum(h["naive"] for h in HIST)
        return {"ranking": [{"sku": i["sku"], "name": i["name"], "demand": i["demand"]} for i in heap_sort_desc(its, lambda i: i["demand"])],
                "low": [{"qty": k[0], "sku": k[1], "name": HT.get(k[1])["name"]} for k in low], "restock": restock,
                "stats": {"skus": len(its), "units": sum(i["qty"] for i in its), "util": round(100 * used / (SHCAP * len(SHELVES)), 1),
                          "pending": len(Q), "orders": len(HIST), "saved": round(100 * sum(sv) / tn, 1) if tn else 0,
                          "wdist": wdist(), "avl_height": H(AVL)}}, 200
    return err("Not found", 404)

class Handler(BaseHTTPRequestHandler):
    def log_message(s, *a): pass
    def out(s, body, ctype, code=200):
        s.send_response(code); s.send_header("Content-Type", ctype); s.send_header("Content-Length", str(len(body))); s.end_headers(); s.wfile.write(body)
    def go(s, m):
        u = urlparse(s.path)
        if m == "GET" and u.path == "/": return s.out(open(os.path.join(BASE, "index.html"), "rb").read(), "text/html; charset=utf-8")
        body = {}
        if m == "POST":
            try: body = json.loads(s.rfile.read(int(s.headers.get("Content-Length", 0))) or b"{}")
            except ValueError: return s.out(b'{"error":"bad json"}', "application/json", 400)
        with LOCK:
            try: res, code = api(m, u.path, parse_qs(u.query), body, TOK.get(s.headers.get("Authorization", "")[7:]))
            except Exception as e: res, code = {"error": f"Server error: {e}"}, 500
        s.out(json.dumps(res).encode(), "application/json", code)
    def do_GET(s): s.go("GET")
    def do_POST(s): s.go("POST")

if __name__ == "__main__":
    load(); port = int(os.environ.get("PORT", 8000))
    print(f"Smart Warehouse running at http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()

