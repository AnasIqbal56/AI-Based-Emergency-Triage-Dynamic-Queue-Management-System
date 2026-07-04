import pandas as pd

def get_demo_patients(csv_path="data/modeling_dataset.csv"):
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Error: Could not find dataset at {csv_path}")
        return

    features = [
        'age', 'is_male', 'resp_rate_mean', 'resp_rate_max', 'spo2_min', 'spo2_mean', 
        'heart_rate_mean', 'heart_rate_max', 'bp_systolic_min', 'bp_systolic_mean', 
        'bp_diastolic_min', 'bp_diastolic_mean', 'gcs_eye_min', 'gcs_verbal_min', 
        'gcs_motor_min', 'temp_celsius_max', 'temp_celsius_min', 'gcs_total_min', 
        'diabetes', 'hypertension', 'ckd', 'heart_failure', 'copd', 'cancer', 
        'liver_disease', 'stroke'
    ]

    print("Extracting 3 distinct demo patients from MIMIC-IV Data...\n")
    
    # Grab 3 distinct types of patients
    # 1. Young & Healthy (Survived)
    p1 = df[(df['mortality'] == 0) & (df['age'] < 40) & (df['diabetes'] == 0)].sample(1).iloc[0]
    
    # 2. Average Elderly (Survived)
    p2 = df[(df['mortality'] == 0) & (df['age'] > 60)].sample(1).iloc[0]
    
    # 3. Critical Elderly (Died)
    p3 = df[(df['mortality'] == 1) & (df['age'] > 60)].sample(1).iloc[0]

    labels = ['Healthy Young (Verified Survived)', 'Average Elderly (Verified Survived)', 'Critical Elderly (Verified Died)']
    
    for i, (p, label) in enumerate(zip([p1, p2, p3], labels)):
        print(f"==========================================================")
        print(f" Demo Patient {i+1}: {label}")
        print(f"==========================================================")
        
        for f in features:
            val = p[f]
            # Format cleanly
            if val.is_integer():
                print(f"{f.ljust(20)} : {int(val)}")
            else:
                print(f"{f.ljust(20)} : {round(val, 2)}")
        print("\n")

if __name__ == "__main__":
    get_demo_patients()
