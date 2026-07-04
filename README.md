# 🏥 AI-Based Emergency Triage & Dynamic Queue Management System

An end-to-end, clinically interpretable machine learning pipeline and real-time dashboard designed to optimize Emergency Department (ED) triage. This project addresses two critical challenges in modern healthcare operations: subjective, bias-prone patient assessment and patient starvation in traditional priority queues.

---

## 📌 Project Overview & Purpose

Emergency Departments frequently suffer from bottlenecks due to inefficient triage systems. This project provides a robust, two-pronged solution:

1. **AI-Driven Clinical Risk Assessment**: An XGBoost machine learning model trained on **94,000+ MIMIC-IV** clinical records. The model analyzes 26 physiological and demographic features to output a continuous risk score: `P(Mortality) × 100`.
2. **Starvation-Free Queue Management**: A dynamic queuing system that employs a **Logarithmic Aging Heuristic** to balance clinical severity with wait times. This ensures that low-risk patients do not wait indefinitely (starve) while high-risk patients are still prioritized:
   $$\text{Effective Score} = \text{Severity Score} + \alpha \times \ln(1 + \text{wait\_minutes})$$
   *(where $\alpha = 8.0$ governs the speed of wait-time aging).*

---

## 🛠️ Tech Stack

The application is built using a modern, performant, and explainable AI stack:

- **Database / Data Storage**: [DuckDB](https://duckdb.org/) (high-performance columnar database for rapid SQL extraction of MIMIC-IV ICU cohorts).
- **Core Modeling & Processing**:
  - `pandas` & `numpy` (data manipulation)
  - `scikit-learn` (logistic regression baselines, evaluation metrics, fairness metrics)
  - `xgboost` (gradient boosting tree classifier for high-accuracy predictions)
- **Model Explainability**: [SHAP](https://github.com/shap/shap) (TreeExplainer to compute feature impact contributions for each individual patient).
- **Web Dashboard**: 
  - `Flask` (Python backend utilizing background threads for dynamic reassessment and doctor simulation loops)
  - Vanilla HTML & CSS (clean, responsive clinician interface)
- **Research & Development**: Jupyter Notebooks (`notebook>=7.0.0`, `nbformat`).

---

## 📂 Repository Structure

```text
emergency-triage-systems/
│
├── notebooks/
│   ├── 01_Data_Extraction_and_EDA.ipynb   # Cohort extraction via DuckDB & cohort analysis
│   ├── 02_Feature_Engineering.ipynb        # Data cleanup, boundary constraints, median imputation
│   ├── 03_Model_Training.ipynb             # XGBoost vs. Logistic Regression model training
│   └── 04_Queue_Simulation.ipynb           # Evaluation of FIFO vs. Priority vs. Logarithmic Aging
│
├── models/
│   ├── xgboost_model.json                  # Serialized XGBoost model weights
│   └── feature_columns.json                # JSON schema of the 26-feature model input
│
├── templates/
│   └── index.html                          # Flask HTML dashboard template
│
├── app.py                                  # Flask application entry point with REST APIs & loops
├── requirements.txt                        # Project dependencies
├── triage_system.duckdb                    # Local DuckDB database file (~405 MB)
└── README.md                               # This file
```

---

## 🩺 High-Level Working & Features

### 1. Data Pipeline & Modeling
- **Cohort Extraction**: Connects to the local `triage_system.duckdb` file containing MIMIC-IV clinical events. Features are aggregated from vital signs and chart events recorded within the **first 4 hours** of patient arrival.
- **Model Selection**: XGBoost was selected for production over Logistic Regression because it yields superior predictive performance:
  - **AUROC**: **0.836** (vs 0.791 for Logistic Regression)
  - **AUPRC**: **0.461** (vs 0.365 for Logistic Regression)
- **Fairness Checking**: The application includes fairness metrics APIs evaluating model performance and selection rates across demographics (age groups and gender) to minimize bias.

### 2. Live Clinician Dashboard Features
- **Real-Time Patient Intake**: Input patient name, age, gender, and vital signs to immediately view predicted severity (Critical, High Risk, Medium Risk, Low Risk).
- **Explainable Predictions**: On-demand **SHAP explanations** showing the top 5 vital signs or comorbidities that increased or decreased the patient's severity score.
- **Dynamic Re-Evaluation**: Clinicians can update a patient's vitals on-the-fly to trigger a re-prediction and re-rank the queues.
- **Doctor Simulation**: Active simulation with a configured number of doctors (default: 3). Treating a patient occupies a doctor for a set treatment time (default: 15 minutes), after which the doctor automatically becomes free via a background thread.
- **Starvation Protection**: Automatic background threads run every minute to reassess wait times and apply the logarithmic aging factor.

---

## 🚀 How to Run the Project

### Prerequisites
- Python 3.8+ installed on your system.

### Step 1: Clone & Setup Virtual Environment
Initialize a virtual environment to isolate the project dependencies:
```bash
# Clone the repository
git clone <repository-url>
cd emergency-triage-systems

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate
```

### Step 2: Install Dependencies
Install all package requirements listed in `requirements.txt`:
```bash
pip install -r requirements.txt
```

### Step 3: Run the Application
Start the Flask development server:
```bash
python app.py
```
Upon running, you should see logs showing that the doctor release and patient reassessment background loops have started:
```text
[INFO] 3 doctors | 15min treatment | α=8.0 (log aging)
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

### Step 4: Open the Dashboard
Open your web browser and navigate to:
```text
http://127.0.0.1:5000
```

---

## 📈 Running the Jupyter Notebooks
To explore the model development process, run the notebooks using:
```bash
jupyter notebook
```
Browse to the `notebooks/` directory and run them sequentially:
1. `01_Data_Extraction_and_EDA.ipynb`
2. `02_Feature_Engineering.ipynb`
3. `03_Model_Training.ipynb`
4. `04_Queue_Simulation.ipynb`
