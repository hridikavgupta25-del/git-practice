import os
from flask import Flask, render_template_string, request, jsonify
import mysql.connector

app = Flask(__name__)

DB_CONFIG = {
    'host': os.environ.get('DB_HOST'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME'),
    'port': int(os.environ.get('DB_PORT', 3306))
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

# Dynamic AI/Smart Tip Engine based on top emission category
def generate_smart_tip(top_category, grand_total):
    if grand_total == 0 or not top_category:
        return {
            "title": "Welcome to EcoAware!",
            "tip": "Start logging your daily transport, energy, and diet activities to unlock personalized AI sustainability insights.",
            "action": "Log your first activity above to see recommendations.",
            "icon": "fa-seedling"
        }
    
    tips = {
        'Transport': {
            "title": "High Transport Footprint Detected",
            "tip": "Transportation makes up the largest share of your carbon footprint. Switching daily short commutes to walking, cycling, or public transport can reduce emissions significantly.",
            "action": "Try carpooling twice a week or using public buses to cut petrol logs by up to 35%.",
            "icon": "fa-car-side"
        },
        'Energy': {
            "title": "High Energy Usage Identified",
            "tip": "Electricity usage is currently driving your carbon score. Switching to energy-efficient appliances and LED bulbs makes an immediate impact.",
            "action": "Unplug electronics when idle and switch to LED lighting to reduce energy logs by 15-20%.",
            "icon": "fa-bolt"
        },
        'Diet': {
            "title": "Dietary Footprint Insight",
            "tip": "Dietary choices play a massive role in footprint reduction. High-meat meals generate higher CO2 equivalent emissions per serving than plant-based options.",
            "action": "Try replacing meat-heavy meals 2-3 times a week with vegetarian options to drop dietary emissions by nearly half.",
            "icon": "fa-utensils"
        }
    }
    
    return tips.get(top_category, {
        "title": "Balanced Carbon Footprint",
        "tip": "Your emissions are spread across multiple categories. Keep tracking regularly to discover new ways to optimize.",
        "action": "Check the community chat to exchange green strategies with neighbors!",
        "icon": "fa-leaf"
    })

# --- BACKEND REST API ENDPOINTS ---

@app.route('/api/users', methods=['GET', 'POST'])
def handle_users():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        data = request.json
        name = data.get('full_name')
        email = data.get('email')
        try:
            cursor.execute("INSERT INTO users (full_name, email) VALUES (%s, %s)", (name, email))
            db.commit()
            new_id = cursor.lastrowid
            db.close()
            return jsonify({"status": "success", "user_id": new_id})
        except Exception as e:
            db.close()
            return jsonify({"error": str(e)}), 400
    else:
        cursor.execute("SELECT * FROM users ORDER BY user_id ASC")
        users = cursor.fetchall()
        db.close()
        return jsonify(users)

@app.route('/api/factors', methods=['GET'])
def get_factors():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM emission_factors")
        factors = cursor.fetchall()
        db.close()
        return jsonify(factors)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/log', methods=['POST'])
def log_activity():
    try:
        data = request.json
        user_id = int(data['user_id'])
        factor_id = int(data['factor_id'])
        quantity = float(data['quantity'])
        log_date = data['log_date']

        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        cursor.execute("SELECT co2_kg_per_unit FROM emission_factors WHERE factor_id = %s", (factor_id,))
        factor = cursor.fetchone()
        if not factor:
            db.close()
            return jsonify({"error": "Factor not found"}), 400

        total_co2 = quantity * float(factor['co2_kg_per_unit'])

        sql = "INSERT INTO activity_logs (user_id, factor_id, quantity, total_co2_kg, log_date) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (user_id, factor_id, quantity, total_co2, log_date))
        db.commit()
        db.close()

        return jsonify({"status": "success", "total_co2": total_co2})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard/<int:user_id>', methods=['GET'])
def get_dashboard(user_id):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        # Category aggregation
        query = """
            SELECT ef.category, SUM(l.total_co2_kg) as total_co2
            FROM activity_logs l
            JOIN emission_factors ef ON l.factor_id = ef.factor_id
            WHERE l.user_id = %s
            GROUP BY ef.category
            ORDER BY total_co2 DESC
        """
        cursor.execute(query, (user_id,))
        categories = cursor.fetchall()

        # Determine top emission category
        top_category = categories[0]['category'] if categories else None

        # Monthly trend line data
        trend_query = """
            SELECT DATE_FORMAT(l.log_date, '%%Y-%%m') as month, SUM(l.total_co2_kg) as total_co2
            FROM activity_logs l
            WHERE l.user_id = %s
            GROUP BY DATE_FORMAT(l.log_date, '%%Y-%%m')
            ORDER BY month ASC
        """
        cursor.execute(trend_query, (user_id,))
        monthly_trend = cursor.fetchall()

        # Overall stats
        cursor.execute("SELECT SUM(total_co2_kg) as grand_total, COUNT(*) as log_count FROM activity_logs WHERE user_id = %s", (user_id,))
        stats = cursor.fetchone()
        total = stats['grand_total'] or 0
        count = stats['log_count'] or 0

        # Recent logs
        recent_query = """
            SELECT ef.activity_name, l.quantity, ef.unit, l.total_co2_kg, l.log_date
            FROM activity_logs l
            JOIN emission_factors ef ON l.factor_id = ef.factor_id
            WHERE l.user_id = %s
            ORDER BY l.log_id DESC LIMIT 5
        """
        cursor.execute(recent_query, (user_id,))
        recent_logs = cursor.fetchall()

        # Generate smart recommendations
        smart_tip = generate_smart_tip(top_category, float(total))

        db.close()
        return jsonify({
            "categories": categories, 
            "monthly_trend": monthly_trend,
            "grand_total": round(float(total), 2),
            "log_count": count,
            "recent_logs": recent_logs,
            "top_category": top_category,
            "smart_tip": smart_tip
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT u.user_id, u.full_name, COALESCE(SUM(l.total_co2_kg), 0) AS total_co2
            FROM users u
            LEFT JOIN activity_logs l ON u.user_id = l.user_id
            GROUP BY u.user_id, u.full_name
            ORDER BY total_co2 ASC
        """
        cursor.execute(query)
        leaderboard = cursor.fetchall()
        db.close()
        return jsonify(leaderboard)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/messages', methods=['GET', 'POST'])
def handle_messages():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        if request.method == 'POST':
            data = request.json
            user_id = int(data.get('user_id'))
            message_text = data.get('message_text')
            if not message_text:
                db.close()
                return jsonify({"error": "Message cannot be empty"}), 400
            
            cursor.execute(
                "INSERT INTO community_messages (user_id, message_text) VALUES (%s, %s)",
                (user_id, message_text)
            )
            db.commit()
            db.close()
            return jsonify({"status": "success"})
        else:
            query = """
                SELECT m.message_id, m.message_text, DATE_FORMAT(m.created_at, '%%Y-%%m-%%d %%H:%%i') as created_at, u.full_name, u.user_id
                FROM community_messages m
                JOIN users u ON m.user_id = u.user_id
                ORDER BY m.created_at DESC
                LIMIT 30
            """
            cursor.execute(query)
            messages = cursor.fetchall()
            db.close()
            return jsonify(messages)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- FRONTEND UI TEMPLATE ---

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EcoAware Pro | Resident Carbon Management Platform</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-main: #f8fafc;
            --sidebar-bg: #0f172a;
            --accent-green: #10b981;
            --accent-green-hover: #059669;
            --card-border-radius: 16px;
        }
        body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg-main); color: #334155; }
        .sidebar { width: 260px; background: var(--sidebar-bg); min-height: 100vh; color: #94a3b8; }
        .sidebar .nav-link { color: #94a3b8; border-radius: 10px; padding: 12px 16px; margin-bottom: 6px; font-weight: 500; }
        .sidebar .nav-link:hover, .sidebar .nav-link.active { color: #ffffff; background: rgba(255, 255, 255, 0.08); }
        .sidebar .nav-link.active { border-left: 4px solid var(--accent-green); }
        .main-content { flex: 1; padding: 32px; }
        .custom-card { background: #ffffff; border-radius: var(--card-border-radius); border: 1px solid #e2e8f0; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02); }
        .stat-card-icon { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.25rem; }
        .btn-green { background-color: var(--accent-green); color: white; border-radius: 10px; font-weight: 600; padding: 12px; border: none; }
        .btn-green:hover { background-color: var(--accent-green-hover); color: white; }
        .leaderboard-item { border-radius: 12px; padding: 12px 16px; margin-bottom: 8px; background: #f8fafc; border: 1px solid #f1f5f9; }
        .rank-badge { width: 28px; height: 28px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem; }
        .rank-1 { background: #fef3c7; color: #d97706; }
        .rank-2 { background: #e0e7ff; color: #4f46e5; }
        .rank-3 { background: #f3e8ff; color: #9333ea; }
        .rank-default { background: #e2e8f0; color: #475569; }
        .badge-pill { font-size: 0.75rem; padding: 6px 12px; border-radius: 20px; font-weight: 600; }
        .ai-tip-card { background: linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 100%); border: 1px solid #bbf7d0; }
        @media print {
            .sidebar, .btn, #logFormCard, #userSwitchContainer, #chatForm { display: none !important; }
            .main-content { padding: 0 !important; }
        }
    </style>
</head>
<body>

<div class="d-flex">
    <div class="sidebar p-4 d-none d-md-block">
        <div class="d-flex align-items-center mb-5 gap-2">
            <div class="bg-success text-white p-2 rounded-3 fs-4"><i class="fa-solid fa-leaf"></i></div>
            <h4 class="text-white fw-bold mb-0">EcoAware</h4>
        </div>
        <nav class="nav flex-column">
            <a class="nav-link active" href="#"><i class="fa-solid fa-chart-pie me-3"></i>Dashboard</a>
            <a class="nav-link" href="#" onclick="window.print()"><i class="fa-solid fa-file-pdf me-3"></i>Print Report</a>
        </nav>
    </div>

    <div class="main-content">
        <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-3">
            <div>
                <h3 class="fw-bold mb-1">Resident Carbon Dashboard</h3>
                <p class="text-muted mb-0">Real-time carbon footprint analytics & sustainability tracking.</p>
            </div>
            <div class="d-flex align-items-center gap-2" id="userSwitchContainer">
                <select id="userSelect" class="form-select border-0 shadow-sm fw-semibold" style="width: 200px;" onchange="onUserChange()"></select>
                <button class="btn btn-outline-success btn-sm rounded-circle p-2" title="Add Resident" data-bs-toggle="modal" data-bs-target="#addUserModal">
                    <i class="fa-solid fa-plus"></i>
                </button>
                <button class="btn btn-dark btn-sm rounded-3 px-3" onclick="window.print()">
                    <i class="fa-solid fa-print me-1"></i> Export
                </button>
            </div>
        </div>

        <!-- Metric Stat Cards -->
        <div class="row g-4 mb-4">
            <div class="col-md-3">
                <div class="custom-card p-4 d-flex align-items-center justify-content-between">
                    <div>
                        <span class="text-muted fw-semibold small">TOTAL EMISSIONS</span>
                        <h3 class="fw-bold text-danger mb-0 mt-1" id="totalCo2">0 kg</h3>
                    </div>
                    <div class="stat-card-icon bg-danger-subtle text-danger"><i class="fa-solid fa-smog"></i></div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="custom-card p-4 d-flex align-items-center justify-content-between">
                    <div>
                        <span class="text-muted fw-semibold small">LOGGED ACTIONS</span>
                        <h3 class="fw-bold text-dark mb-0 mt-1" id="logCount">0</h3>
                    </div>
                    <div class="stat-card-icon bg-primary-subtle text-primary"><i class="fa-solid fa-list-check"></i></div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="custom-card p-4 d-flex align-items-center justify-content-between">
                    <div>
                        <span class="text-muted fw-semibold small">TREES TO OFFSET</span>
                        <h3 class="fw-bold text-success mb-0 mt-1" id="treesNeeded">0</h3>
                    </div>
                    <div class="stat-card-icon bg-success-subtle text-success"><i class="fa-solid fa-tree"></i></div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="custom-card p-4 d-flex align-items-center justify-content-between">
                    <div>
                        <span class="text-muted fw-semibold small">ECO STATUS</span>
                        <h5 class="fw-bold mb-0 mt-1" id="ecoBadge"><span class="badge bg-secondary">Newcomer</span></h5>
                    </div>
                    <div class="stat-card-icon bg-warning-subtle text-warning"><i class="fa-solid fa-award"></i></div>
                </div>
            </div>
        </div>

        <!-- Smart Recommendation Card -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="custom-card ai-tip-card p-4 d-flex align-items-start gap-3">
                    <div class="stat-card-icon bg-success text-white fs-4 flex-shrink-0" id="tipIcon">
                        <i class="fa-solid fa-wand-magic-sparkles"></i>
                    </div>
                    <div>
                        <div class="d-flex align-items-center gap-2 mb-1">
                            <span class="badge bg-success text-white fw-bold px-2 py-1" style="font-size: 0.7rem;">SMART RECOMMENDATION</span>
                            <h5 class="fw-bold mb-0 text-dark" id="tipTitle">Loading Eco Recommendations...</h5>
                        </div>
                        <p class="mb-2 text-secondary" id="tipBody"></p>
                        <div class="p-2 bg-white rounded border d-inline-block small fw-semibold text-success" id="tipAction"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Core Grid -->
        <div class="row g-4 mb-4">
            <div class="col-lg-4" id="logFormCard">
                <div class="custom-card p-4 h-100">
                    <h5 class="fw-bold mb-3"><i class="fa-solid fa-plus-circle text-success me-2"></i>Log Activity</h5>
                    <form id="logForm">
                        <div class="mb-3">
                            <label class="form-label text-muted small fw-semibold">Activity Type</label>
                            <select id="factorSelect" class="form-select shadow-none" required></select>
                        </div>
                        <div class="mb-3">
                            <label class="form-label text-muted small fw-semibold">Quantity</label>
                            <input type="number" step="0.1" id="quantity" class="form-control shadow-none" placeholder="e.g. 12.5" required>
                        </div>
                        <div class="mb-4">
                            <label class="form-label text-muted small fw-semibold">Date</label>
                            <input type="date" id="logDate" class="form-control shadow-none" required>
                        </div>
                        <button type="submit" class="btn btn-green w-100 shadow-sm"><i class="fa-solid fa-paper-plane me-2"></i>Record Log</button>
                    </form>
                </div>
            </div>

            <!-- Charts Section -->
            <div class="col-lg-8">
                <div class="row g-4">
                    <div class="col-md-6">
                        <div class="custom-card p-4">
                            <h6 class="fw-bold mb-3"><i class="fa-solid fa-chart-pie text-success me-2"></i>By Category</h6>
                            <div style="height: 220px;" class="d-flex justify-content-center align-items-center">
                                <canvas id="categoryChart"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="custom-card p-4">
                            <h6 class="fw-bold mb-3"><i class="fa-solid fa-chart-line text-primary me-2"></i>Monthly Trend</h6>
                            <div style="height: 220px;">
                                <canvas id="trendChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Tables & Chat Row -->
        <div class="row g-4">
            <div class="col-lg-7">
                <div class="custom-card p-4 mb-4">
                    <h5 class="fw-bold mb-3"><i class="fa-solid fa-clock-rotate-left text-success me-2"></i>Activity History</h5>
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0">
                            <thead class="table-light">
                                <tr>
                                    <th>Activity</th>
                                    <th>Quantity</th>
                                    <th>CO2</th>
                                    <th>Date</th>
                                </tr>
                            </thead>
                            <tbody id="recentLogsTable"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-lg-5">
                <div class="custom-card p-4 mb-4">
                    <h5 class="fw-bold mb-3"><i class="fa-solid fa-trophy text-warning me-2"></i>Community Ranks</h5>
                    <div id="leaderboardList"></div>
                </div>
            </div>
        </div>

        <!-- Community Chat Section -->
        <div class="row">
            <div class="col-12">
                <div class="custom-card p-4">
                    <h5 class="fw-bold mb-3"><i class="fa-solid fa-comments text-primary me-2"></i>Community Eco Chat</h5>
                    <div id="chatMessages" class="overflow-auto mb-3 p-3 bg-light rounded-3" style="max-height: 250px;"></div>
                    <form id="chatForm" class="d-flex gap-2">
                        <input type="text" id="chatInput" class="form-control shadow-none" placeholder="Share an eco-tip, question, or update..." required>
                        <button type="submit" class="btn btn-green px-4"><i class="fa-solid fa-paper-plane me-1"></i> Send</button>
                    </form>
                </div>
            </div>
        </div>

    </div>
</div>

<!-- Add Resident Modal -->
<div class="modal fade" id="addUserModal" tabindex="-1">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content border-0 custom-card">
            <div class="modal-header border-0">
                <h5 class="modal-title fw-bold">Register New Resident</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <form id="addUserForm">
                    <div class="mb-3">
                        <label class="form-label small fw-semibold">Full Name</label>
                        <input type="text" id="newUserName" class="form-control" placeholder="e.g. Ananya Rao" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small fw-semibold">Email Address</label>
                        <input type="email" id="newUserEmail" class="form-control" placeholder="ananya@example.com" required>
                    </div>
                    <button type="submit" class="btn btn-green w-100 mt-2">Create Profile</button>
                </form>
            </div>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    let categoryChart = null;
    let trendChart = null;
    let currentUserId = 1;

    document.getElementById('logDate').value = new Date().toISOString().split('T')[0];

    async function loadUsers() {
        const res = await fetch('/api/users');
        const users = await res.json();
        const select = document.getElementById('userSelect');
        select.innerHTML = users.map(u => `<option value="${u.user_id}">${u.full_name}</option>`).join('');
        if (users.length > 0) {
            select.value = currentUserId;
        }
    }

    async function loadFactors() {
        const res = await fetch('/api/factors');
        const factors = await res.json();
        const select = document.getElementById('factorSelect');
        select.innerHTML = factors.map(f => `<option value="${f.factor_id}">${f.activity_name} (${f.unit})</option>`).join('');
    }

    async function loadDashboard() {
        const res = await fetch(`/api/dashboard/${currentUserId}`);
        const data = await res.json();
        
        document.getElementById('totalCo2').innerText = `${data.grand_total} kg`;
        document.getElementById('logCount').innerText = data.log_count;
        
        const trees = Math.ceil(data.grand_total / 21);
        document.getElementById('treesNeeded').innerText = `${trees} tree${trees === 1 ? '' : 's'}`;

        // Eco Status Badges
        const badgeEl = document.getElementById('ecoBadge');
        if (data.grand_total === 0) badgeEl.innerHTML = `<span class="badge bg-secondary badge-pill">Newcomer</span>`;
        else if (data.grand_total < 25) badgeEl.innerHTML = `<span class="badge bg-success badge-pill">Eco Champion</span>`;
        else if (data.grand_total < 75) badgeEl.innerHTML = `<span class="badge bg-warning text-dark badge-pill">Moderate Saver</span>`;
        else badgeEl.innerHTML = `<span class="badge bg-danger badge-pill">High Impact</span>`;

        // Render Smart Tip Card
        if (data.smart_tip) {
            document.getElementById('tipTitle').innerText = data.smart_tip.title;
            document.getElementById('tipBody').innerText = data.smart_tip.tip;
            document.getElementById('tipAction').innerHTML = `<i class="fa-solid fa-lightbulb me-1"></i> Recommended Action: ${data.smart_tip.action}`;
            document.getElementById('tipIcon').innerHTML = `<i class="fa-solid ${data.smart_tip.icon}"></i>`;
        }

        // Populate Table
        const tableBody = document.getElementById('recentLogsTable');
        if (!data.recent_logs || data.recent_logs.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">No logs recorded yet.</td></tr>`;
        } else {
            tableBody.innerHTML = data.recent_logs.map(log => `
                <tr>
                    <td class="fw-semibold">${log.activity_name}</td>
                    <td>${log.quantity} ${log.unit}</td>
                    <td><span class="badge bg-danger-subtle text-danger fw-bold">${Number(log.total_co2_kg).toFixed(2)} kg</span></td>
                    <td class="text-muted small">${log.log_date}</td>
                </tr>
            `).join('');
        }

        // 1. Render Doughnut Category Chart
        const labels = data.categories.map(c => c.category);
        const values = data.categories.map(c => c.total_co2);

        if (categoryChart) categoryChart.destroy();
        const ctx1 = document.getElementById('categoryChart').getContext('2d');
        categoryChart = new Chart(ctx1, {
            type: 'doughnut',
            data: {
                labels: labels.length ? labels : ['No Data'],
                datasets: [{ 
                    data: values.length ? values : [1], 
                    backgroundColor: values.length ? ['#ef4444', '#3b82f6', '#10b981', '#f59e0b'] : ['#e2e8f0'],
                    borderWidth: 0
                }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } }, cutout: '65%' }
        });

        // 2. Render Line Trend Chart
        const trendLabels = data.monthly_trend.map(m => m.month);
        const trendValues = data.monthly_trend.map(m => m.total_co2);

        if (trendChart) trendChart.destroy();
        const ctx2 = document.getElementById('trendChart').getContext('2d');
        trendChart = new Chart(ctx2, {
            type: 'line',
            data: {
                labels: trendLabels.length ? trendLabels : ['Current'],
                datasets: [{
                    label: 'CO2 (kg)',
                    data: trendValues.length ? trendValues : [data.grand_total],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });
    }

    async function loadLeaderboard() {
        const res = await fetch('/api/leaderboard');
        const list = await res.json();
        const container = document.getElementById('leaderboardList');
        
        container.innerHTML = list.map((item, idx) => {
            let rankClass = idx === 0 ? 'rank-1' : idx === 1 ? 'rank-2' : idx === 2 ? 'rank-3' : 'rank-default';
            return `
                <div class="leaderboard-item d-flex align-items-center justify-content-between">
                    <div class="d-flex align-items-center gap-3">
                        <span class="rank-badge ${rankClass}">${idx + 1}</span>
                        <span class="fw-semibold text-dark">${item.full_name}</span>
                    </div>
                    <span class="badge bg-white text-dark border rounded-pill px-3 py-2 fw-semibold">
                        ${Number(item.total_co2).toFixed(2)} kg CO2
                    </span>
                </div>
            `;
        }).join('');
    }

    async function loadMessages() {
        const res = await fetch('/api/messages');
        const messages = await res.json();
        const container = document.getElementById('chatMessages');
        
        if (!messages || messages.length === 0) {
            container.innerHTML = `<p class="text-muted text-center small mb-0">No messages yet. Start the conversation!</p>`;
            return;
        }

        container.innerHTML = messages.reverse().map(msg => `
            <div class="p-2 mb-2 bg-white rounded border shadow-sm">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="fw-bold small text-success"><i class="fa-solid fa-user-circle me-1"></i>${msg.full_name}</span>
                    <span class="text-muted" style="font-size: 0.75rem;">${msg.created_at}</span>
                </div>
                <p class="mb-0 small text-secondary">${msg.message_text}</p>
            </div>
        `).join('');
        container.scrollTop = container.scrollHeight;
    }

    function onUserChange() {
        currentUserId = document.getElementById('userSelect').value;
        loadDashboard();
    }

    document.getElementById('logForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            user_id: currentUserId,
            factor_id: document.getElementById('factorSelect').value,
            quantity: document.getElementById('quantity').value,
            log_date: document.getElementById('logDate').value
        };

        await fetch('/api/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        document.getElementById('quantity').value = '';
        loadDashboard();
        loadLeaderboard();
    });

    document.getElementById('chatForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            user_id: currentUserId,
            message_text: document.getElementById('chatInput').value
        };

        await fetch('/api/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        document.getElementById('chatInput').value = '';
        loadMessages();
    });

    document.getElementById('addUserForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            full_name: document.getElementById('newUserName').value,
            email: document.getElementById('newUserEmail').value
        };

        const res = await fetch('/api/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.status === 'success') {
            currentUserId = data.user_id;
            bootstrap.Modal.getInstance(document.getElementById('addUserModal')).hide();
            document.getElementById('addUserForm').reset();
            await loadUsers();
            loadDashboard();
            loadLeaderboard();
        }
    });

    // Initial Startup
    loadUsers();
    loadFactors();
    loadDashboard();
    loadLeaderboard();
    loadMessages();
</script>
</body>
</html>"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(
    debug=False,
    host='0.0.0.0',
    port=int(os.environ.get('PORT', 5000))
)