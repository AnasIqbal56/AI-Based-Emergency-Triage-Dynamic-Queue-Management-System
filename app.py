import os
import json
import time
import uuid
import math
import numpy as np
import pandas as pd
import xgboost as xgb
import random
import threading
from flask import Flask, render_template, request, jsonify

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    print("[WARNING] SHAP not installed. Run: pip install shap")

app = Flask(__name__)

# --- Configuration ---
MODEL_PATH = "models/xgboost_model.json"
FEATURES_PATH = "models/feature_columns.json"

# Queue: Logarithmic aging — effective_score = severity + ALPHA * log(1 + wait_minutes)
ALPHA = 8.0

# Resource constraints
NUM_DOCTORS = 3
TREATMENT_TIME_MINUTES = 15

# Dynamic re-evaluation
REASSESSMENT_CHECK_INTERVAL = 60   # seconds between background checks
REASSESSMENT_THRESHOLD = 30        # minutes before flagging for reassessment

# --- Load Model ---
xgb_model = xgb.XGBClassifier()
xgb_model.load_model(MODEL_PATH)

with open(FEATURES_PATH, 'r') as f:
    feature_cols = json.load(f)

# --- SHAP Explainer ---
shap_explainer = None
if SHAP_AVAILABLE:
    try:
        shap_explainer = shap.TreeExplainer(xgb_model)
        print("[INFO] SHAP TreeExplainer initialized.")
    except Exception as e:
        print(f"[WARNING] SHAP init failed: {e}")

# --- In-Memory State ---
WAITING_QUEUE = []
BUSY_DOCTORS = []      # [{'doctor_id', 'patient_id', 'patient_name', 'free_at'}]
AVAILABLE_DOCTORS = NUM_DOCTORS
lock = threading.Lock()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def compute_shap_explanation(row_data):
    """Compute SHAP values for a single prediction, return top 5 contributors."""
    if not SHAP_AVAILABLE or shap_explainer is None:
        return []
    try:
        df = pd.DataFrame([row_data])
        shap_values = shap_explainer.shap_values(df)
        sv = shap_values[1][0] if isinstance(shap_values, list) else shap_values[0]

        explanations = []
        for i, col in enumerate(feature_cols):
            explanations.append({
                "feature": col,
                "value": float(row_data.get(col, 0)),
                "impact": round(float(abs(sv[i])), 4),
                "raw_impact": round(float(sv[i]), 4),
                "direction": "increases risk" if sv[i] > 0 else "decreases risk"
            })
        explanations.sort(key=lambda x: x['impact'], reverse=True)
        return explanations[:5]
    except Exception as e:
        print(f"[WARNING] SHAP failed: {e}")
        return []


def classify_severity(score):
    if score >= 75:
        return "Critical"
    elif score >= 50:
        return "High Risk"
    elif score >= 25:
        return "Medium Risk"
    return "Low Risk"


def get_all_queues():
    """Calculates live effective scores using logarithmic aging and returns sorted queues."""
    current_time = time.time()

    for p in WAITING_QUEUE:
        wt = (current_time - p['arrival_time']) / 60.0
        p['wait_time_minutes'] = round(wt, 2)
        # Logarithmic aging: starvation-free, sub-linear growth
        p['effective_score'] = round(p['severity_score'] + ALPHA * math.log(1 + wt), 2)
        # Flag reassessment
        if wt >= REASSESSMENT_THRESHOLD and not p.get('recently_reassessed', False):
            p['needs_reassessment'] = True

    aging_queue = sorted(WAITING_QUEUE, key=lambda x: x['effective_score'], reverse=True)
    age_based_queue = sorted(WAITING_QUEUE, key=lambda x: (-x.get('age', 0), x['arrival_time']))
    fifo_queue = sorted(WAITING_QUEUE, key=lambda x: x['arrival_time'])

    return {"aging": aging_queue, "age_based": age_based_queue, "fifo": fifo_queue}


# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    return render_template("index.html")


@app.route('/api/predict', methods=['POST'])
def add_patient():
    data = request.json

    row_data = {}
    for col in feature_cols:
        val = data.get(col, 0)
        try:
            row_data[col] = float(val)
        except:
            row_data[col] = 0.0

    df = pd.DataFrame([row_data])
    mortality_prob = xgb_model.predict_proba(df)[0][1]
    severity_score = round(float(mortality_prob * 100), 2)
    category = classify_severity(severity_score)
    shap_explanation = compute_shap_explanation(row_data)

    patient_id = str(uuid.uuid4())[:6]
    patient_name = data.get("patient_name", f"Patient-{patient_id}").strip()
    if not patient_name:
        patient_name = f"Patient-{patient_id}"

    patient_record = {
        "id": patient_id,
        "name": patient_name,
        "age": float(data.get("age", 0)),
        "severity_score": severity_score,
        "category": category,
        "arrival_time": time.time(),
        "wait_time_minutes": 0.0,
        "effective_score": severity_score,
        "ground_truth": -1,
        "features": row_data,
        "shap_explanation": shap_explanation,
        "needs_reassessment": False,
        "recently_reassessed": False,
        "reassessment_count": 0
    }

    with lock:
        WAITING_QUEUE.append(patient_record)

    return jsonify({
        "status": "success",
        "new_patient": patient_record,
        "shap_explanation": shap_explanation,
        "queues": get_all_queues(),
        "available_doctors": AVAILABLE_DOCTORS
    })


@app.route('/api/queue', methods=['GET'])
def fetch_queue():
    return jsonify({
        "queues": get_all_queues(),
        "available_doctors": AVAILABLE_DOCTORS,
        "total_doctors": NUM_DOCTORS
    })


@app.route('/api/clear', methods=['POST'])
def clear_queue():
    global WAITING_QUEUE
    with lock:
        WAITING_QUEUE = []
    return jsonify({"status": "cleared", "queues": get_all_queues()})


@app.route('/api/treat/<patient_id>', methods=['POST'])
def treat_patient(patient_id):
    global WAITING_QUEUE, AVAILABLE_DOCTORS

    with lock:
        if AVAILABLE_DOCTORS <= 0:
            return jsonify({
                "status": "error",
                "message": f"All {NUM_DOCTORS} doctors busy. Please wait.",
                "queues": get_all_queues(),
                "available_doctors": 0
            }), 429

        patient = None
        new_queue = []
        for p in WAITING_QUEUE:
            if p['id'] == patient_id:
                patient = p
            else:
                new_queue.append(p)
        WAITING_QUEUE = new_queue

        if patient:
            AVAILABLE_DOCTORS -= 1
            BUSY_DOCTORS.append({
                'doctor_id': NUM_DOCTORS - AVAILABLE_DOCTORS,
                'patient_id': patient_id,
                'patient_name': patient.get('name', patient_id),
                'free_at': time.time() + (TREATMENT_TIME_MINUTES * 60)
            })

    return jsonify({
        "status": "treated",
        "queues": get_all_queues(),
        "available_doctors": AVAILABLE_DOCTORS,
        "treatment_time_minutes": TREATMENT_TIME_MINUTES
    })


@app.route('/api/explain/<patient_id>', methods=['GET'])
def explain_patient(patient_id):
    """Return SHAP explanation for a queued patient."""
    for p in WAITING_QUEUE:
        if p['id'] == patient_id:
            if p.get('shap_explanation'):
                return jsonify({"status": "success", "patient_id": patient_id,
                                "severity_score": p['severity_score'],
                                "shap_explanation": p['shap_explanation']})
            if p.get('features'):
                exp = compute_shap_explanation(p['features'])
                p['shap_explanation'] = exp
                return jsonify({"status": "success", "patient_id": patient_id,
                                "severity_score": p['severity_score'],
                                "shap_explanation": exp})
    return jsonify({"status": "error", "message": "Patient not found"}), 404


@app.route('/api/reevaluate/<patient_id>', methods=['POST'])
def reevaluate_patient(patient_id):
    """Re-evaluate a patient with updated vitals."""
    data = request.json or {}

    with lock:
        for p in WAITING_QUEUE:
            if p['id'] == patient_id:
                features = p.get('features', {}).copy()
                for col in feature_cols:
                    if col in data:
                        try:
                            features[col] = float(data[col])
                        except:
                            pass

                df = pd.DataFrame([features])
                mortality_prob = xgb_model.predict_proba(df)[0][1]
                new_severity = round(float(mortality_prob * 100), 2)
                shap_exp = compute_shap_explanation(features)
                old_severity = p['severity_score']

                p['severity_score'] = new_severity
                p['category'] = classify_severity(new_severity)
                p['features'] = features
                p['shap_explanation'] = shap_exp
                p['needs_reassessment'] = False
                p['recently_reassessed'] = True
                p['reassessment_count'] = p.get('reassessment_count', 0) + 1

                return jsonify({
                    "status": "success", "patient_id": patient_id,
                    "old_severity": old_severity, "new_severity": new_severity,
                    "category": p['category'], "shap_explanation": shap_exp,
                    "queues": get_all_queues(), "available_doctors": AVAILABLE_DOCTORS
                })

    return jsonify({"status": "error", "message": "Patient not found"}), 404


@app.route('/api/fairness', methods=['GET'])
def fairness_analysis():
    """Compute fairness metrics across age groups and gender."""
    try:
        from sklearn.metrics import roc_auc_score, recall_score

        df_all = pd.read_csv("data/modeling_dataset.csv")
        X = df_all[feature_cols].fillna(0)
        y_true = df_all['mortality'].values
        y_prob = xgb_model.predict_proba(X)[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)

        results = {"overall": {
            "auroc": round(float(roc_auc_score(y_true, y_prob)), 4),
            "recall": round(float(recall_score(y_true, y_pred)), 4),
            "count": int(len(y_true))
        }}

        # By age group
        age_results = {}
        for label, (lo, hi) in {"18-40": (18, 40), "40-60": (40, 60),
                                 "60-80": (60, 80), "80+": (80, 200)}.items():
            mask = (df_all['age'] >= lo) & (df_all['age'] < hi)
            if mask.sum() < 10:
                continue
            yt, yp, ypd = y_true[mask], y_prob[mask], y_pred[mask]
            if len(set(yt)) < 2:
                continue
            age_results[label] = {
                "auroc": round(float(roc_auc_score(yt, yp)), 4),
                "recall": round(float(recall_score(yt, ypd)), 4),
                "count": int(mask.sum()),
                "mortality_rate": round(float(yt.mean()), 4)
            }
        results["by_age_group"] = age_results

        # By gender
        gender_results = {}
        for gval, glabel in [(0, "Female"), (1, "Male")]:
            mask = df_all['is_male'] == gval
            if mask.sum() < 10:
                continue
            yt, yp, ypd = y_true[mask], y_prob[mask], y_pred[mask]
            if len(set(yt)) < 2:
                continue
            gender_results[glabel] = {
                "auroc": round(float(roc_auc_score(yt, yp)), 4),
                "recall": round(float(recall_score(yt, ypd)), 4),
                "count": int(mask.sum()),
                "mortality_rate": round(float(yt.mean()), 4)
            }
        results["by_gender"] = gender_results

        return jsonify({"status": "success", "fairness": results})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/status', methods=['GET'])
def system_status():
    """Return current system status."""
    current_time = time.time()
    busy_info = [{
        "doctor_id": d['doctor_id'],
        "patient_name": d.get('patient_name', '?'),
        "minutes_remaining": round(max(0, (d['free_at'] - current_time) / 60.0), 1)
    } for d in BUSY_DOCTORS]

    return jsonify({
        "available_doctors": AVAILABLE_DOCTORS,
        "total_doctors": NUM_DOCTORS,
        "busy_doctors": busy_info,
        "queue_length": len(WAITING_QUEUE),
        "treatment_time_minutes": TREATMENT_TIME_MINUTES
    })


# ============================================================
# SIMULATION
# ============================================================

def add_patients_delayed(patients_to_add, delay_seconds=60):
    global WAITING_QUEUE
    for p in patients_to_add:
        p["arrival_time"] = time.time()
        with lock:
            WAITING_QUEUE.append(p)
        time.sleep(delay_seconds)


@app.route('/api/simulate', methods=['POST'])
def simulate_patients():
    try:
        df_all = pd.read_csv("data/modeling_dataset.csv")
        sample_df = df_all.sample(n=25)

        patients_to_add = []
        for idx, row in sample_df.iterrows():
            row_data = {col: float(row.get(col, 0)) for col in feature_cols}
            df_pred = pd.DataFrame([row_data])
            mortality_prob = xgb_model.predict_proba(df_pred)[0][1]
            severity_score = round(float(mortality_prob * 100), 2)
            category = classify_severity(severity_score)
            shap_exp = compute_shap_explanation(row_data)

            patient_id = str(uuid.uuid4())[:6]
            gt = int(row['mortality']) if 'mortality' in row else -1

            patients_to_add.append({
                "id": patient_id, "name": f"Sim Patient {patient_id}",
                "age": float(row.get("age", 0)),
                "severity_score": severity_score, "category": category,
                "arrival_time": 0, "wait_time_minutes": 0.0,
                "effective_score": severity_score, "ground_truth": gt,
                "features": row_data, "shap_explanation": shap_exp,
                "needs_reassessment": False, "recently_reassessed": False,
                "reassessment_count": 0
            })

        thread = threading.Thread(target=add_patients_delayed, args=(patients_to_add, 60))
        thread.daemon = True
        thread.start()

        return jsonify({
            "status": "success",
            "message": "Simulation started! Patients arrive one by one over 25 minutes.",
            "queues": get_all_queues(),
            "available_doctors": AVAILABLE_DOCTORS
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# BACKGROUND THREADS
# ============================================================

def doctor_release_loop():
    """Releases doctors when their treatment window expires."""
    global AVAILABLE_DOCTORS
    while True:
        time.sleep(10)
        current_time = time.time()
        with lock:
            released = [d for d in BUSY_DOCTORS if current_time >= d['free_at']]
            for d in released:
                BUSY_DOCTORS.remove(d)
                AVAILABLE_DOCTORS = min(AVAILABLE_DOCTORS + 1, NUM_DOCTORS)


def reassessment_loop():
    """Flags patients who have waited beyond the reassessment threshold."""
    while True:
        time.sleep(REASSESSMENT_CHECK_INTERVAL)
        current_time = time.time()
        with lock:
            for p in WAITING_QUEUE:
                wt = (current_time - p['arrival_time']) / 60.0
                if wt >= REASSESSMENT_THRESHOLD:
                    if p.get('recently_reassessed', False):
                        p['recently_reassessed'] = False
                    p['needs_reassessment'] = True


if __name__ == '__main__':
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)

    threading.Thread(target=doctor_release_loop, daemon=True).start()
    threading.Thread(target=reassessment_loop, daemon=True).start()

    print(f"[INFO] {NUM_DOCTORS} doctors | {TREATMENT_TIME_MINUTES}min treatment | α={ALPHA} (log aging)")
    app.run(debug=True, port=5000)
