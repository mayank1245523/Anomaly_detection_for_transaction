# from flask import Flask, request, jsonify, render_template
# import joblib
# import numpy as np
# from datetime import datetime
# import re
# from flask_cors import CORS
# from collections import defaultdict
# import time
# import requests
# import sqlite3

# app = Flask(__name__)
# CORS(app)

# # ========== GLOBAL VARIABLES ==========
# ip_blacklist = set()
# transaction_history = defaultdict(list)

# # ========== LOAD MODELS & SCALER ==========
# try:
#     model = joblib.load('credit_card_fraud_model.pkl')
#     print("Model loaded successfully.")
# except FileNotFoundError:
#     model = None
#     print("Warning: Model file not found.")

# try:
#     scaler = joblib.load('scaler_latest.pkl')
#     print("Scaler loaded successfully.")
# except FileNotFoundError:
#     scaler = None
#     print("Warning: Scaler file not found.")

# try:
#     iso_model = joblib.load('isolation_forest.pkl')
#     print("Isolation Forest model loaded successfully.")
# except FileNotFoundError:
#     iso_model = None
#     print("Warning: Isolation Forest model not found.")

# # ========== DATABASE ==========
# def init_db():
#     conn = sqlite3.connect('transactions.db')
#     c = conn.cursor()
#     c.execute('''CREATE TABLE IF NOT EXISTS transactions
#                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
#                   timestamp TEXT, type TEXT, amount REAL,
#                   oldbalanceOrig REAL, newbalanceOrig REAL,
#                   oldbalanceDest REAL, newbalanceDest REAL,
#                   nameOrig TEXT, nameDest TEXT, location TEXT,
#                   client_ip TEXT, is_fraud INTEGER, probability REAL,
#                   rule_reason TEXT, anomaly_detected INTEGER)''')
#     conn.commit()
#     conn.close()

# init_db()

# def store_transaction(payload, client_ip, is_fraud, probability, rule_reason, anomaly_detected, location):
#     conn = sqlite3.connect('transactions.db')
#     c = conn.cursor()
#     c.execute('''INSERT INTO transactions 
#                  (timestamp, type, amount, oldbalanceOrig, newbalanceOrig, oldbalanceDest, newbalanceDest,
#                   nameOrig, nameDest, location, client_ip, is_fraud, probability, rule_reason, anomaly_detected)
#                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
#               (datetime.now().isoformat(),
#                payload.get('type'),
#                float(payload.get('amount', 0)),
#                float(payload.get('oldbalanceOrig', 0)),
#                float(payload.get('newbalanceOrig', 0)),
#                float(payload.get('oldbalanceDest', 0)),
#                float(payload.get('newbalanceDest', 0)),
#                payload.get('nameOrig', ''),
#                payload.get('nameDest', ''),
#                location,
#                client_ip,
#                1 if is_fraud else 0,
#                probability,
#                rule_reason or '',
#                1 if anomaly_detected else 0))
#     conn.commit()
#     conn.close()

# # ========== HELPER FUNCTIONS ==========
# def get_location_from_ip(ip):
#     try:
#         resp = requests.get(f'http://ip-api.com/json/{ip}', timeout=2)
#         data = resp.json()
#         if data.get('status') == 'success':
#             return {
#                 'country': data['country'],
#                 'city': data['city'],
#                 'lat': data['lat'],
#                 'lon': data['lon'],
#                 'isp': data['isp']
#             }
#     except Exception:
#         pass
#     return {'country': 'Unknown', 'city': 'Unknown'}

# def compute_features_and_values(payload: dict):
#     tx_type = payload.get("type", "payment").upper()
#     amount = float(payload.get("amount", 0.0))
#     oldbalanceOrig = float(payload.get("oldbalanceOrig", 0.0))
#     newbalanceOrig = float(payload.get("newbalanceOrig", 0.0))
#     oldbalanceDest = float(payload.get("oldbalanceDest", 0.0))
#     newbalanceDest = float(payload.get("newbalanceDest", 0.0))

#     hour = datetime.now().hour
#     is_night = 1 if hour < 6 else 0
#     amount_ratio = amount / (oldbalanceOrig + 1.0)

#     sender_balance_change = oldbalanceOrig - newbalanceOrig
#     receiver_balance_change = newbalanceDest - oldbalanceDest

#     orig_balance_zero = 1 if oldbalanceOrig == 0 else 0
#     dest_balance_zero = 1 if oldbalanceDest == 0 else 0
#     type_TRANSFER = 1 if tx_type == "TRANSFER" else 0

#     features = [
#         amount,
#         oldbalanceOrig,
#         newbalanceOrig,
#         oldbalanceDest,
#         newbalanceDest,
#         is_night,
#         amount_ratio,
#         sender_balance_change,
#         receiver_balance_change,
#         orig_balance_zero,
#         dest_balance_zero,
#         type_TRANSFER
#     ]

#     vals = {
#         "tx_type": tx_type,
#         "amount": amount,
#         "oldbalanceOrig": oldbalanceOrig,
#         "newbalanceOrig": newbalanceOrig,
#         "oldbalanceDest": oldbalanceDest,
#         "newbalanceDest": newbalanceDest,
#         "is_night": is_night,
#         "hour": hour,
#         "amount_ratio": amount_ratio,
#         "sender_balance_change": sender_balance_change,
#         "receiver_balance_change": receiver_balance_change,
#         "orig_balance_zero": orig_balance_zero,
#         "dest_balance_zero": dest_balance_zero,
#         "type_TRANSFER": type_TRANSFER,
#         "nameOrig": payload.get("nameOrig", "unknown_sender"),
#         "nameDest": payload.get("nameDest", "unknown_receiver"),
#         "location": payload.get("location", "unknown")
#     }

#     x = np.array(features).reshape(1, -1)
#     return x, vals

# def rule_based_checks(v):
#     amount = v["amount"]
#     sender_change = v["sender_balance_change"]
#     receiver_change = v["receiver_balance_change"]
#     tx_type = v["tx_type"]
#     sender_id = v["nameOrig"]
#     receiver_id = v["nameDest"]
#     current_location = v["location"]
#     current_time = time.time()
#     window = 600
#     max_tx = 5
#     max_amount = 100000

#     # --- DEBUG PRINT ---
#     print(f"DEBUG: amount={amount}, sender_change={sender_change}, receiver_change={receiver_change}")

#     # Basic balance checks
#     if amount <= 0:
#         return False, "amount must be positive"

#     if amount > v["oldbalanceOrig"]:
#         return True, "amount exceeds sender's available balance"

#     if receiver_change > amount:
#         return True, "receiver balance change exceeds the amount sent"

#     if abs(sender_change - amount) > 0.20 * amount:
#         return True, "sender balance change inconsistent with the amount sent"

#     if receiver_change < 0.70 * amount:
#         return True, f"receiver credited significantly less than expected (got {receiver_change}, expected at least {0.7*amount})"

#     if tx_type == "TRANSFER" and receiver_change == 0:
#         return True, "receiver balance not updated"

#     # Total movement check (fixed)
#     total_movement = sender_change + receiver_change
#     expected_total = 2 * amount
#     if abs(total_movement - expected_total) > 0.30 * amount:
#         return True, f"inconsistent total money movement (total={total_movement}, expected={expected_total})"

#     # Velocity checks
#     transaction_history[sender_id] = [
#         entry for entry in transaction_history[sender_id]
#         if current_time - entry['timestamp'] < window
#     ]
#     if len(transaction_history[sender_id]) >= max_tx:
#         return True, f"Sender {sender_id} ne {window//60} minutes mein {max_tx} se zyada transactions ki hain"

#     total_sent = sum(entry['amount'] for entry in transaction_history[sender_id]) + amount
#     if total_sent > max_amount:
#         return True, f"Sender {sender_id} exceeded the limit of {max_amount} in {window//60} minutes"

#     # Location change
#     if transaction_history[sender_id]:
#         last_entry = transaction_history[sender_id][-1]
#         last_location = last_entry.get('location', 'unknown')
#         if last_location != 'unknown' and current_location != 'unknown' and last_location != current_location:
#             return True, f"Location change detected: {last_location} → {current_location}"

#     # Log transaction
#     transaction_history[sender_id].append({
#         'timestamp': current_time,
#         'amount': amount,
#         'location': current_location
#     })

#     return False, ""

# # ========== ROUTES ==========
# @app.route("/")
# def home():
#     return render_template("index.html")

# @app.route("/predict", methods=["POST"])
# def predict():
#     try:
#         payload = request.get_json(force=True)
#         client_ip = request.remote_addr

#         # ---------- LOCATION LOGIC ----------
#         # Pehle frontend se aayi location lo
#         frontend_location = payload.get('location', '')
#         if frontend_location and frontend_location != 'unknown':
#             # Agar frontend ne location bheji hai to use karo
#             location_used = frontend_location
#         else:
#             # Varna IP se location lo
#             ip_location = get_location_from_ip(client_ip)
#             location_used = ip_location['city']
#         payload['location'] = location_used
#         # Ab location_used variable mein final location hai (frontend ya IP)
#         # ------------------------------------

#         # ---------- IP BLACKLIST CHECK ----------
#         if client_ip in ip_blacklist:
#             store_transaction(payload, client_ip, True, 1.0, "IP blacklisted", False, location_used)
#             return jsonify({
#                 "is_fraud": 1,
#                 "rule_reason": "IP address previously associated with fraud",
#                 "rule_flagged": True,
#                 "probability": 1.0,
#                 "client_ip": client_ip
#             })

#         # ---------- FEATURE COMPUTATION ----------
#         x, vals = compute_features_and_values(payload)

#         # ---------- RULE-BASED CHECKS ----------
#         flagged, reason = rule_based_checks(vals)
#         if flagged:
#             # IP blacklist mein add karo agar fraud mila
#             ip_blacklist.add(client_ip)
#             print(f"IP {client_ip} added to blacklist (rule-based fraud)")
#             store_transaction(payload, client_ip, True, 1.0, reason, False, location_used)
#             return jsonify({
#                 "is_fraud": 1,
#                 "rule_reason": reason,
#                 "rule_flagged": True,
#                 "features": vals,
#                 "probability": 1.0,
#                 "client_ip": client_ip
#             })

#         # ---------- ANOMALY DETECTION (DISABLED FOR NOW) ----------
#         anomaly_detected = False
#         # if scaler and iso_model:
#         #     try:
#         #         features_scaled = scaler.transform(x)
#         #         if iso_model.predict(features_scaled)[0] == -1:
#         #             anomaly_detected = True
#         #     except Exception as e:
#         #         print(f"Anomaly error: {e}")

#         # ---------- MODEL PREDICTION ----------
#         if model is None:
#             return jsonify({"error": "Model not loaded"}), 503

#         try:
#             pred = int(model.predict(x)[0])
#             proba = float(model.predict_proba(x)[0][1]) if hasattr(model, 'predict_proba') else (1.0 if pred == 1 else 0.0)
#         except ValueError as ve:
#             # Feature mismatch handling
#             msg = str(ve)
#             expected = None
#             if hasattr(model, 'n_features_in_'):
#                 expected = int(getattr(model, 'n_features_in_'))
#             else:
#                 try:
#                     if hasattr(model, 'steps'):
#                         for _, step in model.steps:
#                             if hasattr(step, 'n_features_in_'):
#                                 expected = int(getattr(step, 'n_features_in_'))
#                                 break
#                 except Exception:
#                     pass
#             if expected is None:
#                 m = re.search(r"expected (\d+) features", msg)
#                 if not m:
#                     m = re.search(r"expecting (\d+)", msg)
#                 if m:
#                     expected = int(m.group(1))
#             if expected is not None and x.shape[1] < expected:
#                 pad_width = expected - x.shape[1]
#                 pad = np.zeros((1, pad_width))
#                 x_padded = np.hstack([x, pad])
#                 pred = int(model.predict(x_padded)[0])
#                 proba = float(model.predict_proba(x_padded)[0][1]) if hasattr(model, 'predict_proba') else (1.0 if pred == 1 else 0.0)
#             else:
#                 return jsonify({"error": msg}), 400

#         # ---------- BLACKLIST UPDATE (MODEL FRAUD) ----------
#         if pred == 1:
#             ip_blacklist.add(client_ip)
#             print(f"IP {client_ip} added to blacklist (model fraud)")

#         # ---------- STORE TRANSACTION ----------
#         store_transaction(payload, client_ip, pred == 1, proba, None, anomaly_detected, location_used)

#         # ---------- FINAL RESPONSE ----------
#         return jsonify({
#             "is_fraud": pred,
#             "probability": round(proba, 6),
#             "rule_flagged": False,
#             "features": vals,
#             "anomaly_detected": anomaly_detected,
#             "client_ip": client_ip
#         })

#     except Exception as exc:
#         return jsonify({"error": str(exc)}), 400

# @app.route("/transactions")
# def transactions():
#     conn = sqlite3.connect('transactions.db')
#     c = conn.cursor()
#     c.execute('SELECT * FROM transactions ORDER BY id DESC LIMIT 20')
#     rows = c.fetchall()
#     conn.close()
#     return render_template("transactions.html", rows=rows)

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5000, debug=True)


from flask import Flask, request, jsonify, render_template
import joblib
import numpy as np
from datetime import datetime
import re
from flask_cors import CORS
from collections import defaultdict
import time
import sqlite3

app = Flask(__name__)
CORS(app)

# ========== GLOBAL VARIABLES ==========
# IP blacklist hata diya
transaction_history = defaultdict(list)

# ========== LOAD MODELS & SCALER ==========
try:
    model = joblib.load('credit_card_fraud_model.pkl')
    print("Model loaded successfully.")
except FileNotFoundError:
    model = None
    print("Warning: Model file not found.")

try:
    scaler = joblib.load('scaler_latest.pkl')
    print("Scaler loaded successfully.")
except FileNotFoundError:
    scaler = None
    print("Warning: Scaler file not found.")

try:
    iso_model = joblib.load('isolation_forest.pkl')
    print("Isolation Forest model loaded successfully.")
except FileNotFoundError:
    iso_model = None
    print("Warning: Isolation Forest model not found.")

# ========== DATABASE ==========
def init_db():
    conn = sqlite3.connect('transactions.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT, type TEXT, amount REAL,
                  oldbalanceOrig REAL, newbalanceOrig REAL,
                  oldbalanceDest REAL, newbalanceDest REAL,
                  nameOrig TEXT, nameDest TEXT,
                  is_fraud INTEGER, probability REAL,
                  rule_reason TEXT, anomaly_detected INTEGER)''')
    conn.commit()
    conn.close()

init_db()

def store_transaction(payload, is_fraud, probability, rule_reason, anomaly_detected):
    conn = sqlite3.connect('transactions.db')
    c = conn.cursor()
    c.execute('''INSERT INTO transactions 
                 (timestamp, type, amount, oldbalanceOrig, newbalanceOrig, oldbalanceDest, newbalanceDest,
                  nameOrig, nameDest, is_fraud, probability, rule_reason, anomaly_detected)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (datetime.now().isoformat(),
               payload.get('type'),
               float(payload.get('amount', 0)),
               float(payload.get('oldbalanceOrig', 0)),
               float(payload.get('newbalanceOrig', 0)),
               float(payload.get('oldbalanceDest', 0)),
               float(payload.get('newbalanceDest', 0)),
               payload.get('nameOrig', ''),
               payload.get('nameDest', ''),
               1 if is_fraud else 0,
               probability,
               rule_reason or '',
               1 if anomaly_detected else 0))
    conn.commit()
    conn.close()

# ========== HELPER FUNCTIONS ==========
# get_location_from_ip hata diya

def compute_features_and_values(payload: dict):
    tx_type = payload.get("type", "payment").upper()
    amount = float(payload.get("amount", 0.0))
    oldbalanceOrig = float(payload.get("oldbalanceOrig", 0.0))
    newbalanceOrig = float(payload.get("newbalanceOrig", 0.0))
    oldbalanceDest = float(payload.get("oldbalanceDest", 0.0))
    newbalanceDest = float(payload.get("newbalanceDest", 0.0))

    hour = datetime.now().hour
    is_night = 1 if hour < 6 else 0
    amount_ratio = amount / (oldbalanceOrig + 1.0)

    sender_balance_change = oldbalanceOrig - newbalanceOrig
    receiver_balance_change = newbalanceDest - oldbalanceDest

    orig_balance_zero = 1 if oldbalanceOrig == 0 else 0
    dest_balance_zero = 1 if oldbalanceDest == 0 else 0
    type_TRANSFER = 1 if tx_type == "TRANSFER" else 0

    features = [
        amount,
        oldbalanceOrig,
        newbalanceOrig,
        oldbalanceDest,
        newbalanceDest,
        is_night,
        amount_ratio,
        sender_balance_change,
        receiver_balance_change,
        orig_balance_zero,
        dest_balance_zero,
        type_TRANSFER
    ]

    vals = {
        "tx_type": tx_type,
        "amount": amount,
        "oldbalanceOrig": oldbalanceOrig,
        "newbalanceOrig": newbalanceOrig,
        "oldbalanceDest": oldbalanceDest,
        "newbalanceDest": newbalanceDest,
        "is_night": is_night,
        "hour": hour,
        "amount_ratio": amount_ratio,
        "sender_balance_change": sender_balance_change,
        "receiver_balance_change": receiver_balance_change,
        "orig_balance_zero": orig_balance_zero,
        "dest_balance_zero": dest_balance_zero,
        "type_TRANSFER": type_TRANSFER,
        "nameOrig": payload.get("nameOrig", "unknown_sender"),
        "nameDest": payload.get("nameDest", "unknown_receiver")
        # location hata diya
    }

    x = np.array(features).reshape(1, -1)
    return x, vals

def rule_based_checks(v):
    amount = v["amount"]
    sender_change = v["sender_balance_change"]
    receiver_change = v["receiver_balance_change"]
    tx_type = v["tx_type"]
    sender_id = v["nameOrig"]
    receiver_id = v["nameDest"]
    # current_location hata diya
    current_time = time.time()
    window = 600
    max_tx = 5
    max_amount = 100000

    # --- DEBUG PRINT ---
    print(f"DEBUG: amount={amount}, sender_change={sender_change}, receiver_change={receiver_change}")

    # Basic balance checks
    if amount <= 0:
        return False, "amount must be positive"

    if amount > v["oldbalanceOrig"]:
        return True, "amount exceeds sender's available balance"

    if receiver_change > amount:
        return True, "receiver balance change exceeds the amount sent"

    if abs(sender_change - amount) > 0.20 * amount:
        return True, "sender balance change inconsistent with the amount sent"

    if receiver_change < 0.70 * amount:
        return True, f"receiver credited significantly less than expected (got {receiver_change}, expected at least {0.7*amount})"

    if tx_type == "TRANSFER" and receiver_change == 0:
        return True, "receiver balance not updated"

    # Total movement check (fixed)
    total_movement = sender_change + receiver_change
    expected_total = 2 * amount
    if abs(total_movement - expected_total) > 0.30 * amount:
        return True, f"inconsistent total money movement (total={total_movement}, expected={expected_total})"

    # Velocity checks
    transaction_history[sender_id] = [
        entry for entry in transaction_history[sender_id]
        if current_time - entry['timestamp'] < window
    ]
    if len(transaction_history[sender_id]) >= max_tx:
        return True, f"Sender {sender_id} ne {window//60} minutes mein {max_tx} se zyada transactions ki hain"

    total_sent = sum(entry['amount'] for entry in transaction_history[sender_id]) + amount
    if total_sent > max_amount:
        return True, f"Sender {sender_id} exceeded the limit of {max_amount} in {window//60} minutes"

    # Location change rule hata diya

    # Log transaction (location field hata di)
    transaction_history[sender_id].append({
        'timestamp': current_time,
        'amount': amount
    })

    return False, ""

# ========== ROUTES ==========
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/predict", methods=["POST"])
def predict():
    try:
        payload = request.get_json(force=True)
        # client_ip variable hata diya

        # ---------- IP BLACKLIST CHECK HATA DIYA ----------

        # ---------- FEATURE COMPUTATION ----------
        x, vals = compute_features_and_values(payload)

        # ---------- RULE-BASED CHECKS ----------
        flagged, reason = rule_based_checks(vals)
        if flagged:
            store_transaction(payload, True, 1.0, reason, False)
            return jsonify({
                "is_fraud": 1,
                "rule_reason": reason,
                "rule_flagged": True,
                "features": vals,
                "probability": 1.0
                # client_ip hata diya
            })

        # ---------- ANOMALY DETECTION (DISABLED FOR NOW) ----------
        anomaly_detected = False
        # if scaler and iso_model:
        #     try:
        #         features_scaled = scaler.transform(x)
        #         if iso_model.predict(features_scaled)[0] == -1:
        #             anomaly_detected = True
        #     except Exception as e:
        #         print(f"Anomaly error: {e}")

        # ---------- MODEL PREDICTION ----------
        if model is None:
            return jsonify({"error": "Model not loaded"}), 503

        try:
            pred = int(model.predict(x)[0])
            proba = float(model.predict_proba(x)[0][1]) if hasattr(model, 'predict_proba') else (1.0 if pred == 1 else 0.0)
        except ValueError as ve:
            # Feature mismatch handling
            msg = str(ve)
            expected = None
            if hasattr(model, 'n_features_in_'):
                expected = int(getattr(model, 'n_features_in_'))
            else:
                try:
                    if hasattr(model, 'steps'):
                        for _, step in model.steps:
                            if hasattr(step, 'n_features_in_'):
                                expected = int(getattr(step, 'n_features_in_'))
                                break
                except Exception:
                    pass
            if expected is None:
                m = re.search(r"expected (\d+) features", msg)
                if not m:
                    m = re.search(r"expecting (\d+)", msg)
                if m:
                    expected = int(m.group(1))
            if expected is not None and x.shape[1] < expected:
                pad_width = expected - x.shape[1]
                pad = np.zeros((1, pad_width))
                x_padded = np.hstack([x, pad])
                pred = int(model.predict(x_padded)[0])
                proba = float(model.predict_proba(x_padded)[0][1]) if hasattr(model, 'predict_proba') else (1.0 if pred == 1 else 0.0)
            else:
                return jsonify({"error": msg}), 400

        # ---------- BLACKLIST UPDATE HATA DIYA ----------

        # ---------- STORE TRANSACTION ----------
        store_transaction(payload, pred == 1, proba, None, anomaly_detected)

        # ---------- FINAL RESPONSE ----------
        return jsonify({
            "is_fraud": pred,
            "probability": round(proba, 6),
            "rule_flagged": False,
            "features": vals,
            "anomaly_detected": anomaly_detected
            # client_ip hata diya
        })

    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

@app.route("/transactions")
def transactions():
    conn = sqlite3.connect('transactions.db')
    c = conn.cursor()
    c.execute('SELECT * FROM transactions ORDER BY id DESC LIMIT 20')
    rows = c.fetchall()
    conn.close()
    return render_template("transactions.html", rows=rows)


# ========== API ENDPOINTS FOR DASHBOARD ==========
@app.route("/api/stats")
def get_stats():
    conn = sqlite3.connect('transactions.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM transactions")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM transactions WHERE is_fraud = 1")
    fraud = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM transactions WHERE is_fraud = 0")
    safe = c.fetchone()[0]
    conn.close()
    return jsonify({"total": total, "fraud": fraud, "safe": safe})

# Optional: recent transactions API (agar table ko backend se populate karna ho to)
@app.route("/api/recent")
def get_recent():
    conn = sqlite3.connect('transactions.db')
    c = conn.cursor()
    c.execute("SELECT timestamp, type, amount, nameOrig, nameDest, is_fraud FROM transactions ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    recent = []
    for row in rows:
        recent.append({
            "time": row[0],
            "type": row[1],
            "amount": row[2],
            "sender": row[3],
            "receiver": row[4],
            "is_fraud": row[5]
        })
    return jsonify(recent)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)