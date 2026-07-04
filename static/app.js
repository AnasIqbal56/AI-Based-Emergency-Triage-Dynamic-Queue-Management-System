document.addEventListener("DOMContentLoaded", () => {
    
    const form = document.getElementById("triage-form");
    const queueAging = document.getElementById("queue-aging");
    const queueAge = document.getElementById("queue-age");
    const queueFifo = document.getElementById("queue-fifo");
    const queueCount = document.getElementById("queue-count");
    const submitBtn = document.getElementById("submit-btn");
    const loader = document.getElementById("loader");
    const shapPanel = document.getElementById("shap-panel");
    const shapBars = document.getElementById("shap-bars");
    const doctorText = document.getElementById("doctor-text");
    const doctorDots = document.getElementById("doctor-dots");
    
    const btnHealthy = document.getElementById("btn-healthy");
    const btnCritical = document.getElementById("btn-critical");
    const btnSimulate = document.getElementById("btn-simulate");
    
    // Tabs setup
    const tabBtns = document.querySelectorAll(".tab-btn");
    const tabPanes = document.querySelectorAll(".tab-pane");

    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => b.classList.remove("active"));
            tabPanes.forEach(p => p.classList.add("hidden"));
            btn.classList.add("active");
            const targetId = btn.getAttribute("data-target");
            document.getElementById(targetId).classList.remove("hidden");
            document.getElementById(targetId).classList.add("active");
        });
    });

    const features = [
        "age", "is_male", 
        "resp_rate_mean", "resp_rate_max", "spo2_min", "spo2_mean", 
        "heart_rate_mean", "heart_rate_max", 
        "bp_systolic_min", "bp_systolic_mean", "bp_diastolic_min", "bp_diastolic_mean", 
        "gcs_eye_min", "gcs_verbal_min", "gcs_motor_min", 
        "temp_celsius_max", "temp_celsius_min", "gcs_total_min", 
        "diabetes", "hypertension", "ckd", "heart_failure", 
        "copd", "cancer", "liver_disease", "stroke"
    ];

    // Friendly feature name mapping
    const featureNames = {
        "age": "Age", "is_male": "Gender (Male)", "resp_rate_mean": "Resp Rate (Mean)",
        "resp_rate_max": "Resp Rate (Max)", "spo2_min": "SpO₂ (Min)", "spo2_mean": "SpO₂ (Mean)",
        "heart_rate_mean": "Heart Rate (Mean)", "heart_rate_max": "Heart Rate (Max)",
        "bp_systolic_min": "Systolic BP (Min)", "bp_systolic_mean": "Systolic BP (Mean)",
        "bp_diastolic_min": "Diastolic BP (Min)", "bp_diastolic_mean": "Diastolic BP (Mean)",
        "gcs_eye_min": "GCS Eye", "gcs_verbal_min": "GCS Verbal", "gcs_motor_min": "GCS Motor",
        "temp_celsius_max": "Temperature (Max)", "temp_celsius_min": "Temperature (Min)",
        "gcs_total_min": "GCS Total", "diabetes": "Diabetes", "hypertension": "Hypertension",
        "ckd": "CKD", "heart_failure": "Heart Failure", "copd": "COPD", "cancer": "Cancer",
        "liver_disease": "Liver Disease", "stroke": "Stroke"
    };

    fetchQueue();

    // Handle Form Submission
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        submitBtn.classList.add("hidden");
        loader.classList.remove("hidden");

        const patientData = { "patient_name": document.getElementById("patient_name").value };
        features.forEach(f => {
            const el = document.getElementById(f);
            if(el) patientData[f] = parseFloat(el.value) || 0;
        });

        try {
            const response = await fetch('/api/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(patientData)
            });
            const data = await response.json();
            
            if(data.status === "success") {
                renderAllQueues(data.queues, data.available_doctors);
                renderShapPanel(data.shap_explanation);
                form.reset();
                document.getElementById("patient_name").focus();
            }
        } catch (err) {
            console.error(err);
            alert("Error connecting to Triage AI Engine.");
        } finally {
            submitBtn.classList.remove("hidden");
            loader.classList.add("hidden");
        }
    });

    // Auto-fill buttons
    btnHealthy.addEventListener("click", () => {
        document.getElementById("patient_name").value = "Healthy Patient";
        fillForm({
            age: 30, is_male: 1, resp_rate_mean: 16, resp_rate_max: 18, spo2_min: 98, spo2_mean: 99,
            heart_rate_mean: 75, heart_rate_max: 85, bp_systolic_min: 110, bp_systolic_mean: 120,
            bp_diastolic_min: 70, bp_diastolic_mean: 80, temp_celsius_min: 36.5, temp_celsius_max: 37.0,
            gcs_eye_min: 4, gcs_verbal_min: 5, gcs_motor_min: 6, gcs_total_min: 15,
            diabetes: 0, hypertension: 0, ckd: 0, heart_failure: 0, copd: 0, cancer: 0, liver_disease: 0, stroke: 0
        });
    });

    btnCritical.addEventListener("click", () => {
        document.getElementById("patient_name").value = "Critical Patient";
        fillForm({
            age: 78, is_male: 1, resp_rate_mean: 28, resp_rate_max: 35, spo2_min: 88, spo2_mean: 90,
            heart_rate_mean: 115, heart_rate_max: 130, bp_systolic_min: 80, bp_systolic_mean: 90,
            bp_diastolic_min: 50, bp_diastolic_mean: 60, temp_celsius_min: 36.0, temp_celsius_max: 39.0,
            gcs_eye_min: 2, gcs_verbal_min: 3, gcs_motor_min: 4, gcs_total_min: 9,
            diabetes: 1, hypertension: 1, ckd: 0, heart_failure: 1, copd: 0, cancer: 0, liver_disease: 0, stroke: 0
        });
    });
    
    if(btnSimulate) {
        btnSimulate.addEventListener("click", async () => {
            btnSimulate.disabled = true;
            btnSimulate.innerText = "Simulating...";
            try {
                const response = await fetch('/api/simulate', { method: 'POST' });
                const data = await response.json();
                if(data.status === "success" && data.queues) {
                    renderAllQueues(data.queues, data.available_doctors);
                }
            } catch (err) {
                console.error(err);
                alert("Simulation failed.");
            } finally {
                btnSimulate.disabled = false;
                btnSimulate.innerText = "Simulate 25 Patients";
            }
        });
    }

    function fillForm(defaults) {
        Object.keys(defaults).forEach(key => {
            const el = document.getElementById(key);
            if(el) el.value = defaults[key];
        });
    }

    async function fetchQueue() {
        try {
            const response = await fetch('/api/queue');
            const data = await response.json();
            if (data.queues) renderAllQueues(data.queues, data.available_doctors, data.total_doctors);
        } catch(e) {
            console.error("Queue fetch failed", e);
        }
    }

    document.getElementById("btn-clear").addEventListener("click", async () => {
        const response = await fetch('/api/clear', {method: 'POST'});
        const data = await response.json();
        if (data.queues) renderAllQueues(data.queues);
    });

    // Delegated event listener for Treat and Explain buttons
    document.querySelector(".queue-section").addEventListener("click", async (e) => {
        // Treat Patient
        if(e.target.classList.contains("btn-treat")) {
            const pid = e.target.dataset.id;
            const btns = document.querySelectorAll(`.btn-treat[data-id="${pid}"]`);
            btns.forEach(b => { b.innerHTML = "Discharging..."; b.disabled = true; });
            
            try {
                const response = await fetch(`/api/treat/${pid}`, {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: pid})
                });
                const data = await response.json();
                if (data.status === "error") {
                    alert(data.message);
                    btns.forEach(b => { b.innerHTML = "👩‍⚕️ Treat"; b.disabled = false; });
                } else if (data.queues) {
                    renderAllQueues(data.queues, data.available_doctors);
                }
            } catch(err) {
                console.error(err);
                btns.forEach(b => { b.innerHTML = "👩‍⚕️ Treat"; b.disabled = false; });
            }
        }

        // View Explanation
        if(e.target.classList.contains("btn-explain")) {
            const pid = e.target.dataset.id;
            const container = e.target.closest('.patient-card').querySelector('.card-shap');
            if (container && !container.classList.contains('hidden')) {
                container.classList.add('hidden');
                return;
            }
            try {
                const response = await fetch(`/api/explain/${pid}`);
                const data = await response.json();
                if (data.status === "success" && container) {
                    container.innerHTML = renderShapBarsHTML(data.shap_explanation);
                    container.classList.remove('hidden');
                }
            } catch(err) { console.error(err); }
        }
    });

    // ---- SHAP Rendering ----

    function renderShapPanel(shapData) {
        if (!shapData || shapData.length === 0) {
            shapPanel.classList.add("hidden");
            return;
        }
        shapBars.innerHTML = renderShapBarsHTML(shapData);
        shapPanel.classList.remove("hidden");
    }

    function renderShapBarsHTML(shapData) {
        if (!shapData || shapData.length === 0) return '<div class="shap-empty">No explanation available</div>';
        const maxImpact = Math.max(...shapData.map(s => s.impact));
        return shapData.map(s => {
            const pct = maxImpact > 0 ? Math.round((s.impact / maxImpact) * 100) : 0;
            const color = s.direction === "increases risk" ? "var(--critical-color)" : "var(--low-color)";
            const arrow = s.direction === "increases risk" ? "▲" : "▼";
            const name = featureNames[s.feature] || s.feature;
            return `<div class="shap-row">
                <div class="shap-label">${name} <span class="shap-value">= ${s.value}</span></div>
                <div class="shap-bar-track">
                    <div class="shap-bar-fill" style="width:${pct}%; background:${color};"></div>
                </div>
                <div class="shap-direction" style="color:${color}">${arrow} ${s.direction}</div>
            </div>`;
        }).join('');
    }

    // ---- Doctor Status ----

    function updateDoctorStatus(available, total) {
        total = total || 3;
        available = available !== undefined ? available : total;
        doctorText.textContent = `${available} / ${total} Doctors Available`;
        
        let dots = '';
        for (let i = 0; i < total; i++) {
            const cls = i < available ? 'doc-dot available' : 'doc-dot busy';
            dots += `<span class="${cls}"></span>`;
        }
        doctorDots.innerHTML = dots;

        const statusEl = document.getElementById("doctor-status");
        statusEl.className = "doctor-status";
        if (available === 0) statusEl.classList.add("doctors-none");
        else if (available < total) statusEl.classList.add("doctors-partial");
    }

    // ---- Queue Rendering ----

    function renderAllQueues(queues, availableDoctors, totalDoctors) {
        if(!queues || !queues.aging) return;
        queueCount.innerText = `${queues.aging.length} Patient${queues.aging.length !== 1 ? 's' : ''}`;
        updateDoctorStatus(availableDoctors, totalDoctors);
        renderQueueList(queues.aging, queueAging);
        renderQueueList(queues.age_based, queueAge);
        renderQueueList(queues.fifo, queueFifo);
    }

    function renderQueueList(queueData, containerEl) {
        if(queueData.length === 0) {
            containerEl.innerHTML = `<div class="empty-state">The waiting room is currently empty.</div>`;
            return;
        }

        containerEl.innerHTML = '';
        
        queueData.forEach((p, index) => {
            let catClass = "";
            if(p.category.includes("Critical")) catClass = "cat-Critical";
            else if(p.category.includes("High")) catClass = "cat-High";
            else if(p.category.includes("Medium")) catClass = "cat-Medium";
            else catClass = "cat-Low";

            const card = document.createElement("div");
            card.className = `patient-card ${catClass}`;
            
            const waitMins = parseFloat(p.wait_time_minutes).toFixed(1);
            const score = parseFloat(p.severity_score).toFixed(1);
            const effScore = parseFloat(p.effective_score).toFixed(1);
            const pAge = p.age !== undefined ? p.age : "?";
            
            let verificationHtml = "";
            if (p.ground_truth === 1) {
                verificationHtml = `<div style="font-size: 0.75rem; margin-top: 4px; color: var(--critical-color); font-weight: bold;">Verified: Patient Died</div>`;
            } else if (p.ground_truth === 0) {
                verificationHtml = `<div style="font-size: 0.75rem; margin-top: 4px; color: var(--low-color); font-weight: bold;">Verified: Patient Survived</div>`;
            }

            let reassessHtml = "";
            if (p.needs_reassessment) {
                reassessHtml = `<span class="reassess-badge">⚠ Reassessment Needed</span>`;
            }

            let revalCountHtml = "";
            if (p.reassessment_count > 0) {
                revalCountHtml = `<span class="reval-count">Re-evaluated ${p.reassessment_count}×</span>`;
            }

            card.innerHTML = `
                <div class="card-header">
                    <div>
                        <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 2px;">#${index + 1} in line (ID: ${p.id}) | Age: ${pAge}</div>
                        <div class="patient-name">${p.name} ${reassessHtml} ${revalCountHtml}</div>
                        ${verificationHtml}
                    </div>
                    <div class="severity-badge">${p.category}</div>
                </div>
                <div class="card-metrics">
                    <div class="metric">
                        <span>Base Severity</span>
                        <strong>${score} <small style="font-size:0.7em">/ 100</small></strong>
                    </div>
                    <div class="metric">
                        <span>Wait Time</span>
                        <strong>${waitMins} <small style="font-size:0.7em">min</small></strong>
                    </div>
                    <div class="metric">
                        <span style="color:var(--primary); font-weight: 600;">Effective Priority</span>
                        <strong style="color:var(--primary); font-size: 1.1rem;">${effScore}</strong>
                    </div>
                </div>
                <div class="card-shap hidden"></div>
                <div class="card-actions">
                    <button class="btn-explain" data-id="${p.id}">🔍 Explain</button>
                    <button class="btn-treat" data-id="${p.id}">👩‍⚕️ Treat</button>
                </div>
            `;
            containerEl.appendChild(card);
        });
    }

    // Auto-refresh every 10 seconds
    setInterval(() => { fetchQueue(); }, 10000);
});
