import os
import json
from flask import Flask, render_template_string, request, redirect, url_for, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import time, uuid, csv
from io import StringIO

import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.secret_key = 'cashbook_secure_secret_key_12345'

# --- FIREBASE SECURE INITIALIZATION ---
try:
    if 'FIREBASE_CREDENTIALS' in os.environ:
        cred_dict = json.loads(os.environ['FIREBASE_CREDENTIALS'], strict=False)
        cred = credentials.Certificate(cred_dict)
    elif os.path.exists('cash.json'):
        cred = credentials.Certificate('cash.json')
    else:
        raise FileNotFoundError("Missing Firebase keys. Add FIREBASE_CREDENTIALS in Vercel settings.")

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
        
    db = firestore.client()
except Exception as e:
    print(f"🔥 FIREBASE ERROR: Could not initialize. Details: {e}")

# --- HTML TEMPLATES & CSS ---

BASE_STYLE = '''
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
    :root { --primary: #4f46e5; --primary-hover: #4338ca; --success: #10b981; --success-bg: #d1fae5; --success-text: #065f46; --danger: #ef4444; --danger-bg: #fee2e2; --danger-text: #991b1b; --warning: #f59e0b; --dark: #1f2937; --gray: #f3f4f6; --text: #374151; --border: #e5e7eb; }
    body { font-family: 'Poppins', sans-serif; background-color: #f8fafc; color: var(--text); margin: 0; padding: 0; }
    .container { width: 98%; max-width: 1400px; margin: 0 auto; padding: 20px 10px; }
    h1, h2, h3 { color: var(--dark); font-weight: 600; margin-top: 0; }
    .navbar { display: flex; gap: 15px; background: linear-gradient(135deg, #4f46e5, #3b82f6); padding: 15px 30px; border-radius: 12px; margin-bottom: 25px; align-items: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); flex-wrap: wrap;}
    .navbar a { color: white; text-decoration: none; padding: 8px 16px; border-radius: 8px; font-weight: 500; transition: 0.3s; background: rgba(255,255,255,0.1); }
    .navbar a:hover { background: rgba(255,255,255,0.2); transform: translateY(-1px); }
    .navbar .active { background: rgba(255,255,255,0.25); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .navbar .logout { margin-left: auto; background: var(--danger); }
    .navbar .logout:hover { background: #dc2626; }
    .card { background: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 25px; border: 1px solid var(--border); overflow-x: auto;}
    .balance-card { background: linear-gradient(to right, #ffffff, #f8fafc); text-align: center; border-left: 6px solid var(--primary); padding: 20px; }
    .balance-amount { font-size: 2.8em; font-weight: 700; margin-top: 10px; letter-spacing: -1px; }
    .form-group { margin-bottom: 12px; display: flex; flex-direction: column; }
    label { font-weight: 600; margin-bottom: 5px; font-size: 0.85em; color: #4b5563; }
    input, select { padding: 10px 12px; font-size: 0.95em; border: 1px solid #d1d5db; border-radius: 8px; transition: all 0.2s ease; font-family: inherit; width: 100%; box-sizing: border-box; }
    input:focus, select:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15); }
    button, .btn { background-color: var(--primary); color: white; border: none; cursor: pointer; font-weight: 600; padding: 10px 18px; border-radius: 8px; transition: all 0.2s ease; font-family: inherit; text-decoration: none; display: inline-block; text-align: center; }
    button:hover, .btn:hover { background-color: var(--primary-hover); transform: translateY(-1px); }
    .btn-success { background-color: var(--success); } .btn-danger { background-color: var(--danger); }
    .btn-outline { background-color: transparent; border: 2px dashed #cbd5e1; color: var(--text); }
    .btn-sm { padding: 6px 12px; font-size: 0.85em; }
    .ledger-container { display: flex; gap: 20px; flex-wrap: wrap; align-items: flex-start; }
    .ledger-col { flex: 1; min-width: 48%; background: #fff; border-radius: 12px; border: 1px solid var(--border); overflow-x: auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    .ledger-title { margin: 0; padding: 15px; text-align: center; font-size: 1.05em; border-bottom: 1px solid var(--border); background-color: #f8fafc; text-transform: uppercase; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid var(--border); padding: 10px 12px; text-align: left; font-size: 0.88em; vertical-align: middle; }
    th { background-color: #f1f5f9; color: #475569; font-weight: 600; font-size: 0.85em; text-transform: uppercase; }
    tr:hover td { background-color: #f8fafc; }
    .badge { padding: 4px 10px; border-radius: 999px; font-weight: 600; font-size: 0.8em; display: inline-block; }
    .badge-in { background-color: var(--success-bg); color: var(--success-text); }
    .badge-out { background-color: var(--danger-bg); color: var(--danger-text); }
    .badge-memo { background-color: #e5e7eb; color: #374151; border: 1px solid #d1d5db; }
    .badge-pending { background-color: #fef08a; color: #92400e; border: 1px solid #fde047; }
    .badge-mode { background-color: #e0e7ff; color: #3730a3; font-size: 0.8em; margin-bottom: 4px; border: 1px solid #c7d2fe; }
    .flex-row { display: flex; gap: 15px; flex-wrap: wrap; align-items: flex-end; }
    .flex-1 { flex: 1; }
    .express-entry { background: #e0e7ff; border: 2px solid #818cf8; padding: 20px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .transfer-entry { background: #e0f2fe; border: 2px solid #38bdf8; padding: 20px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 25px; }
    .stat-card { background: #fff; padding: 20px; border-radius: 12px; border: 1px solid var(--border); text-align: center; }
    .stat-card h4 { color: #6b7280; margin: 0 0 8px 0; font-size: 0.85em; text-transform: uppercase; }
    .stat-card .value { font-size: 1.6em; font-weight: 700; }
    
    #splash-screen { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(135deg, #4f46e5, #3b82f6); z-index: 9999; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; transition: opacity 0.5s ease; }
    .splash-firm { font-size: 3.5em; font-weight: 700; margin-bottom: 10px; animation: popIn 0.8s ease; text-transform: uppercase; letter-spacing: 2px;}
    .splash-user { font-size: 1.5em; font-weight: 300; animation: popIn 1.2s ease; }
    @keyframes popIn { 0% { opacity: 0; transform: translateY(20px); } 100% { opacity: 1; transform: translateY(0); } }
    
    @media print { .no-print, .navbar, .card form, .express-entry, .transfer-entry, button, select { display: none !important; } body { background: white; color: black; } .card { box-shadow: none; border: none; margin: 0; padding: 0; } }
</style>
<script>
    let isDirty = false;
    function setAutoDateTime() {
        const now = new Date();
        const dateString = new Date(now.getTime() - (now.getTimezoneOffset() * 60000)).toISOString().split('T')[0];
        const timeString = now.toTimeString().slice(0,5);
        document.querySelectorAll('input[type="date"]').forEach(el => { if(!el.value) el.value = dateString; });
        document.querySelectorAll('input[type="time"]').forEach(el => { if(!el.value) el.value = timeString; });
        
        if(document.getElementById('express_date')) document.getElementById('express_date').value = dateString;
        if(document.getElementById('express_time')) document.getElementById('express_time').value = timeString;
        if(document.getElementById('transfer_date')) document.getElementById('transfer_date').value = dateString;
        if(document.getElementById('transfer_time')) document.getElementById('transfer_time').value = timeString;
    }
    function toggleNature() {
        const nature = document.getElementById('txn_nature')?.value;
        const pLabel = document.getElementById('primary_label');
        if(!pLabel) return;
        if(nature === 'slip_in') { pLabel.innerHTML = "Ledger Account <small>(- Deducts User Balance)</small>"; pLabel.style.color = "var(--danger)"; }
        else if(nature === 'advance') { pLabel.innerHTML = "Ledger Account <small>(+ Adds Positive Balance)</small>"; pLabel.style.color = "var(--primary)"; }
        else if(nature === 'receive_cash') { pLabel.innerHTML = "Ledger Account <small>(- Deducts User Balance)</small>"; pLabel.style.color = "var(--success)"; }
    }
    function checkNewAccount(sel) {
        const newAcc = document.getElementById('new_account_name');
        if(sel.value === 'new_dasti' || sel.value === 'new_person') {
            newAcc.style.display = 'block'; newAcc.required = true;
        } else { newAcc.style.display = 'none'; newAcc.required = false; }
    }
    function toggleCustomCategory(selectElem) {
        const customInput = selectElem.nextElementSibling;
        if (selectElem.value === 'Other') { customInput.style.display = 'block'; customInput.required = true; } 
        else { customInput.style.display = 'none'; customInput.required = false; }
    }
    function addRow(catOptions) {
        const html = `<tr>
            <td style="width: 25%; padding: 10px;"><select name="category[]" onchange="toggleCustomCategory(this)" required style="margin-bottom: 0;">${catOptions}<option value="Other">Other (Type Below)...</option></select><input type="text" name="custom_category[]" placeholder="Custom Category..." style="display:none; margin-top: 8px; border-color: var(--primary);"></td>
            <td style="width: 50%; padding: 10px;"><input type="text" name="description[]" placeholder="Bill No. / Detail" required></td>
            <td style="width: 20%; padding: 10px;"><input type="number" step="0.01" min="0" name="amount[]" placeholder="Amount (₹)" value="0" required></td>
            <td style="width: 5%; text-align: center; vertical-align: middle; padding: 10px;"><button type="button" onclick="this.closest('tr').remove()" style="background: var(--danger); padding: 8px 12px; font-size: 0.9em;">✕</button></td>
        </tr>`;
        if(document.getElementById('entryBody')) document.getElementById('entryBody').insertAdjacentHTML('beforeend', html);
    }
    function initForm(catOptions) {
        setAutoDateTime(); toggleNature();
        if(document.getElementById('entryBody') && document.getElementById('entryBody').children.length === 0) { addRow(catOptions); }
        document.querySelectorAll('form').forEach(f => { f.addEventListener('change', () => isDirty = true); f.addEventListener('submit', () => isDirty = false); });
        window.addEventListener('beforeunload', function(e) { if(isDirty) { e.preventDefault(); e.returnValue = 'You have unsaved entries. Exit without saving?'; } });
    }
</script>
'''

SPLASH_HTML = '''
<div id="splash-screen" class="no-print">
    <div class="splash-firm">{{ session.get('firm_name', 'FIRM') }}</div>
    <div class="splash-user">Welcome, {{ session.get('username', 'User') }}</div>
</div>
<script>
    if (sessionStorage.getItem('splashShown')) {
        document.getElementById('splash-screen').style.display = 'none';
    } else {
        window.addEventListener('load', function() {
            setTimeout(function() {
                const splash = document.getElementById('splash-screen');
                if(splash) {
                    splash.style.opacity = '0';
                    setTimeout(() => { splash.style.display = 'none'; }, 500);
                    sessionStorage.setItem('splashShown', 'true');
                }
            }, 1500);
        });
    }
</script>
'''

NAVBAR_HTML = SPLASH_HTML + '''<div class="navbar no-print">
    <a href="/" class="{% if active_page == 'home' %}active{% endif %}">⚡ Dash</a>
    <a href="/main_ledger" class="{% if active_page == 'main_ledger' %}active{% endif %}">🏢 Main</a>
    <a href="/persons" class="{% if active_page == 'persons' %}active{% endif %}">👥 Ledgers</a>
    <a href="/dasti_ledger" class="{% if active_page == 'dasti_ledger' %}active{% endif %}" style="background: rgba(14, 165, 233, 0.2);">💸 Dasti</a>
    
    {% if session.get('can_view_reports') == 1 or session.get('role') == 'superadmin' %}
    <a href="/reports" class="{% if active_page == 'reports' %}active{% endif %}" style="background: rgba(16, 185, 129, 0.2); color: #065f46;">📊 Reports</a>
    {% endif %}
    
    {% if session.get('can_approve') == 1 or session.get('role') == 'superadmin' %}
    <a href="/approvals" class="{% if active_page == 'approvals' %}active{% endif %}" style="background: var(--warning);">✅ Apprv</a>
    {% endif %}
    
    {% if session.get('can_view_trash') == 1 or session.get('role') == 'superadmin' %}
    <a href="/trash" class="{% if active_page == 'trash' %}active{% endif %}" style="background: rgba(239, 68, 68, 0.2); color: #991b1b;">🗑️ Trash</a>
    {% endif %}
    
    {% if session.get('role') == 'superadmin' %}
        <a href="/manage_users" class="{% if active_page == 'users' %}active{% endif %}" style="background: #8b5cf6;">⚙️ Users</a>
        <a href="/download_cash_json" style="background: #f97316; color: white;">🔥 Get DB</a>
    {% endif %}
    
    <span style="color: rgba(255,255,255,0.9); margin-left: auto; font-size: 0.9em; font-weight: 500;">User: <strong>{{ username }}</strong> <small>({{ session.get('role')|title }})</small></span>
    <a href="/logout" class="logout" style="padding: 6px 12px; font-size:0.9em;" onclick="sessionStorage.removeItem('splashShown');">Logout</a>
</div>'''

REGISTER_TEMPLATE = '''<!DOCTYPE html><html><head><title>Setup</title>''' + BASE_STYLE + '''</head><body><div class="container"><div class="card" style="max-width: 450px; margin: 80px auto; text-align: center;"><h2 style="color: var(--primary);">Setup Superadmin</h2><form action="/register" method="POST" style="text-align: left;"><div class="form-group"><label>Firm Name</label><input type="text" name="firm_name" required></div><div class="form-group"><label>Opening Cash Book Balance (₹)</label><input type="number" step="0.01" min="0" name="opening_balance" value="0" required></div><div class="form-group"><label>Superadmin Username</label><input type="text" name="username" required></div><div class="form-group"><label>Password</label><input type="password" name="password" required></div><button type="submit" style="width: 100%;">Initialize Firm Account</button></form></div></div></body></html>'''
LOGIN_TEMPLATE = '''<!DOCTYPE html><html><head><title>Login</title>''' + BASE_STYLE + '''</head><body><div class="container"><div class="card" style="max-width: 400px; margin: 100px auto; text-align: center;"><h2>Welcome Back</h2><form action="/login" method="POST" style="text-align: left;"><div class="form-group"><label>Username</label><input type="text" name="username" required></div><div class="form-group"><label>Password</label><input type="password" name="password" required></div><button type="submit" style="width: 100%;">Secure Login</button></form></div></div></body></html>'''
TRASH_TEMPLATE = '''<!DOCTYPE html><html><head><title>Trash / Recycle Bin</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        <div class="card" style="padding: 0;">
            <h3 style="padding: 15px 20px; margin: 0; background: #fee2e2; border-bottom: 1px solid var(--border); font-size: 1.2em; color: #991b1b;">🗑️ Deleted Vouchers & Entries (Trash)</h3>
            <table style="width: 100%; border: none;"><tr><th style="padding-left: 20px;">Date & Time</th><th>Category / Detail</th><th style="text-align: right;">Amount</th><th style="text-align: center;">Action</th></tr>
                {% for t in trashed %}<tr>
                    <td style="padding-left: 20px;"><span style="font-weight: 500;">{{ t.date }}</span><br><span style="font-size: 0.85em; color: #6b7280;">{{ t.time }}</span></td>
                    <td><span class="badge badge-mode">{{ t.category }}</span><br><span style="white-space: pre-wrap;">{{ t.description }}</span></td>
                    <td style="text-align: right;"><strong>₹{{ "{:,.2f}".format(t.amount) }}</strong></td>
                    <td style="text-align: center;">
                        <a href="/restore_voucher/{{ t.link_id }}" class="btn btn-sm btn-success" onclick="return confirm('Restore this transaction?');">♻️ Restore</a>
                        <a href="/hard_delete_voucher/{{ t.link_id }}" class="btn btn-sm" style="background:#dc2626; color:white; margin-left:5px;" onclick="return confirm('Permanently delete? This cannot be undone.');">🔥 Delete Forever</a>
                    </td>
                </tr>{% else %}<tr><td colspan="4" style="text-align:center; color:#9ca3af; padding: 40px;">Trash is empty.</td></tr>{% endfor %}
            </table>
        </div>
    </div></body></html>'''

REPORTS_TEMPLATE = '''<!DOCTYPE html><html><head><title>Dynamic Reports</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        <div class="card no-print" style="padding: 25px; margin-bottom: 25px;">
            <h3 style="margin-bottom: 15px; font-size: 1.3em;">📊 Generate Report</h3>
            <form method="GET" action="/reports" style="display: flex; gap: 15px; flex-wrap: wrap; align-items: flex-end;">
                <div class="form-group flex-1" style="min-width: 150px;"><label>From Date</label><input type="date" name="start_date" value="{{ start_date }}"></div>
                <div class="form-group flex-1" style="min-width: 150px;"><label>To Date</label><input type="date" name="end_date" value="{{ end_date }}"></div>
                <div class="form-group flex-1" style="min-width: 200px;"><label>Category Filter</label>
                    <select name="category">
                        <option value="">-- All Categories --</option>
                        {% for c in categories %}<option value="{{ c }}" {% if category == c %}selected{% endif %}>{{ c }}</option>{% endfor %}
                    </select>
                </div>
                <div class="form-group flex-1" style="min-width: 250px;"><label>Select Account / Ledger</label>
                    <select name="report_account" style="font-weight:bold; color:var(--primary);">
                        <option value="main" {% if report_account == 'main' %}selected{% endif %}>🏢 Main Cash Book</option>
                        <optgroup label="👥 Person Ledgers">
                            {% for p in persons %}<option value="person_{{ p.id }}" {% if report_account == 'person_'~p.id|string %}selected{% endif %}>👤 {{ p.name }}</option>{% endfor %}
                        </optgroup>
                        <optgroup label="💸 Dasti Ledgers">
                            {% for d in dasti_persons %}<option value="dasti_{{ d.id }}" {% if report_account == 'dasti_'~d.id|string %}selected{% endif %}>💸 {{ d.name }}</option>{% endfor %}
                        </optgroup>
                    </select>
                </div>
                <button class="btn-success" type="submit" style="padding: 10px 25px; height: 45px;">Generate</button>
            </form>
        </div>

        <div class="no-print" style="margin-bottom: 20px; display: flex; gap: 10px; justify-content: flex-end;">
            <button onclick="window.print()" class="btn btn-outline" style="background: white;">🖨️ Print Report</button>
            <a href="{{ url_for('export_reports', start_date=start_date, end_date=end_date, category=category, report_account=report_account) }}" class="btn btn-success" style="background: #10b981;">📥 Download Excel (CSV)</a>
        </div>

        <div class="stats-grid">
            <div class="stat-card" style="border-top: 4px solid var(--success);"><h4>Report Incomes / Received</h4><div class="value" style="color: var(--success);">+ ₹{{ "{:,.2f}".format(total_in) }}</div></div>
            <div class="stat-card" style="border-top: 4px solid var(--danger);"><h4>Report Expenses / Advances</h4><div class="value" style="color: var(--danger);">- ₹{{ "{:,.2f}".format(total_out) }}</div></div>
            <div class="stat-card" style="border-top: 4px solid var(--primary); background: #f8fafc;"><h4>Report Net Flow</h4><div class="value">{% if (total_in - total_out) >= 0 %}<span style="color: var(--success);">+ ₹{{ "{:,.2f}".format(total_in - total_out) }}</span>{% else %}<span style="color: var(--danger);">- ₹{{ "{:,.2f}".format((total_in - total_out)|abs) }}</span>{% endif %}</div></div>
        </div>

        <div class="card" style="padding: 0; overflow-x: auto;">
            <h3 style="padding: 18px 25px; margin: 0; background: #f8fafc; border-bottom: 1px solid var(--border);">Report Results</h3>
            <table style="width: 100%; min-width: 800px;">
                <thead><tr><th style="padding-left: 25px; width: 15%;">Date & Time</th><th style="width: 15%;">Mode/Category</th><th style="width: 50%;">Detail</th><th style="text-align: right; width: 20%;">Amount</th></tr></thead>
                <tbody>
                    {% for txn in results %}<tr>
                        <td style="padding-left: 25px;"><span style="font-weight: 500;">{{ txn.date }}</span><br><span style="color: #6b7280; font-size: 0.85em;">{{ txn.time }}</span></td>
                        <td><span class="badge badge-mode">{{ txn.payment_mode }}</span><br><span style="font-size: 0.85em; color: #4b5563;">{{ txn.category }}</span></td>
                        <td style="white-space: pre-wrap;">{{ txn.description }}
                            {% if txn.approved_by %}<br><span style="color: var(--success); font-size: 0.85em; font-weight: 600;">✓ Apprv: {{ txn.approved_by }}</span>{% endif %}
                        </td>
                        <td style="text-align: right;">
                            {% if txn.type in ['expense', 'dasti_out', 'batch_ledger_out', 'dasti_voucher_out', 'advance'] %}<span class="badge badge-out">- ₹{{ "{:,.2f}".format(txn.amount) }}</span>
                            {% else %}<span class="badge badge-in">+ ₹{{ "{:,.2f}".format(txn.amount) }}</span>{% endif %}
                        </td>
                    </tr>{% else %}<tr><td colspan="4" style="text-align:center; color:#9ca3af; padding: 40px;">No records found.</td></tr>{% endfor %}
                </tbody>
            </table>
        </div>
    </div></body></html>'''

USERS_TEMPLATE = '''<!DOCTYPE html><html><head><title>Manage Users</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        <div class="card" style="margin-bottom: 20px; padding: 20px;">
            <h3 style="font-size: 1.2em;">👤 Create New Firm User</h3>
            <form action="/add_user" method="POST" style="display:flex; gap:15px; align-items: flex-end; flex-wrap:wrap;">
                <div class="form-group flex-1"><label>Username</label><input type="text" name="new_username" required></div>
                <div class="form-group flex-1"><label>Password</label><input type="password" name="new_password" required></div>
                <div class="form-group flex-1"><label>Role</label>
                    <select name="role" required><option value="admin">Admin</option><option value="superadmin">Superadmin</option><option value="cashier">Cashier</option><option value="market">Market</option></select></div>
                
                <div class="form-group" style="padding-bottom: 10px; display: flex; flex-direction: column; gap: 5px;">
                    <label><input type="checkbox" name="can_approve" value="1"> Grant Apprv</label>
                    <label><input type="checkbox" name="can_edit" value="1"> Grant Edit/Del</label>
                </div>
                <div class="form-group" style="padding-bottom: 10px; display: flex; flex-direction: column; gap: 5px;">
                    <label><input type="checkbox" name="can_view_reports" value="1"> Grant Reports</label>
                    <label><input type="checkbox" name="can_view_trash" value="1"> Grant Trash</label>
                </div>

                <button class="btn-success" type="submit" style="padding: 10px 25px; height: 45px;">Create User</button>
            </form>
        </div>
        <div class="card" style="padding: 0;">
            <h3 style="padding: 15px 20px; margin: 0; background: #f8fafc; border-bottom: 1px solid var(--border); font-size: 1.2em;">🛡️ Registered Firm Users</h3>
            <table style="width: 100%; border: none;"><tr><th style="padding-left: 20px;">Username</th><th>Role</th><th>Rights</th><th style="text-align:center;">Action</th></tr>
                {% for u in users %}<tr>
                    <td style="padding-left: 20px; font-weight: 500;">{{ u.username }}</td>
                    <td><span class="badge badge-mode">{{ u.role|title }}</span></td>
                    <td style="font-size: 0.85em;">
                        Apprv: {% if u.can_approve %}✅{% else %}❌{% endif %} | 
                        Edit: {% if u.can_edit %}✅{% else %}❌{% endif %} | 
                        Rep: {% if u.can_view_reports %}✅{% else %}❌{% endif %} | 
                        Trash: {% if u.can_view_trash %}✅{% else %}❌{% endif %}
                    </td>
                    <td style="text-align: center;"><a href="/edit_user/{{ u.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;">✏️ Edit User</a></td>
                </tr>{% endfor %}
            </table>
        </div>
    </div></body></html>'''

EDIT_USER_TEMPLATE = '''<!DOCTYPE html><html><head><title>Edit User</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        <div class="card" style="max-width: 500px; margin: 0 auto;">
            <h2 style="color: var(--primary); margin-bottom: 20px;">⚙️ Edit User Profile</h2>
            <form action="/edit_user/{{ edit_user.id }}" method="POST">
                <div class="form-group"><label>Username</label><input type="text" name="username" value="{{ edit_user.username }}" required></div>
                <div class="form-group"><label>New Password <small>(Leave blank to keep current)</small></label><input type="password" name="password"></div>
                <div class="form-group"><label>User Role</label>
                    <select name="role" required>
                        <option value="superadmin" {% if edit_user.role == 'superadmin' %}selected{% endif %}>Superadmin</option>
                        <option value="admin" {% if edit_user.role == 'admin' %}selected{% endif %}>Admin</option>
                        <option value="cashier" {% if edit_user.role == 'cashier' %}selected{% endif %}>Cashier</option>
                        <option value="market" {% if edit_user.role == 'market' %}selected{% endif %}>Market</option>
                    </select>
                </div>
                
                <div class="form-group" style="padding-bottom: 15px; margin-top: 10px; display: flex; flex-direction: column; gap: 8px;">
                    <label style="display:flex; align-items:center; gap:10px; cursor:pointer;"><input type="checkbox" name="can_approve" value="1" {% if edit_user.can_approve %}checked{% endif %} style="width: auto;"> Grant Voucher Approval Rights</label>
                    <label style="display:flex; align-items:center; gap:10px; cursor:pointer;"><input type="checkbox" name="can_edit" value="1" {% if edit_user.can_edit %}checked{% endif %} style="width: auto;"> Grant Edit / Delete Rights</label>
                    <label style="display:flex; align-items:center; gap:10px; cursor:pointer;"><input type="checkbox" name="can_view_reports" value="1" {% if edit_user.can_view_reports %}checked{% endif %} style="width: auto;"> Grant Report Access</label>
                    <label style="display:flex; align-items:center; gap:10px; cursor:pointer;"><input type="checkbox" name="can_view_trash" value="1" {% if edit_user.can_view_trash %}checked{% endif %} style="width: auto;"> Grant Trash Bin Access</label>
                </div>
                
                <div style="display: flex; gap: 15px;">
                    <a href="/manage_users" class="btn btn-outline" style="flex:1;">Cancel</a>
                    <button class="btn-success" type="submit" style="flex:1;">Save Updates</button>
                </div>
            </form>
        </div>
    </div></body></html>'''

APPROVALS_TEMPLATE = '''<!DOCTYPE html><html><head><title>Pending Approvals</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        
        <div class="card" style="margin-bottom: 20px;">
            <h3 style="margin-top: 0; font-size: 1.2em; color: var(--primary);">✅ Bulk Approve by Date</h3>
            <form action="/bulk_approve" method="POST" style="display: flex; gap: 15px; align-items: flex-end; flex-wrap: wrap;">
                <div class="form-group flex-1" style="min-width: 150px;"><label>From Date</label><input type="date" name="start_date" required></div>
                <div class="form-group flex-1" style="min-width: 150px;"><label>To Date</label><input type="date" name="end_date" required></div>
                <button class="btn-success" type="submit" style="height: 45px; padding: 10px 25px; font-size: 1.05em;" onclick="return confirm('Approve ALL pending entries in this date range? You will be marked as the approver.');">Bulk Approve Selected Range</button>
            </form>
        </div>

        <div class="card" style="padding: 0;">
            <h3 style="padding: 15px 20px; margin: 0; background: #fef08a; border-bottom: 1px solid var(--border); font-size: 1.2em; color: #92400e;">⏳ Individual Pending Vouchers</h3>
            <table style="width: 100%; border: none;"><tr><th style="padding-left: 20px;">Date & Time</th><th>Description / Detail</th><th style="text-align: right;">Amount</th><th style="text-align: center;">Action</th></tr>
                {% for t in pending %}<tr>
                    <td style="padding-left: 20px;"><span style="font-weight: 500;">{{ t.date }}</span><br><span style="font-size: 0.85em; color: #6b7280;">{{ t.time }}</span></td>
                    <td><span class="badge badge-pending">Pending</span><br><span style="white-space: pre-wrap;">{{ t.description }}</span></td>
                    <td style="text-align: right;"><strong>₹{{ "{:,.2f}".format(t.amount) }}</strong></td>
                    <td style="text-align: center;">
                        <a href="/approve_voucher/{{ t.link_id }}" class="btn btn-sm btn-success" onclick="return confirm('Approve this transaction?');">✅ Approve</a> 
                        <a href="/reject_voucher/{{ t.link_id }}" class="btn btn-sm btn-danger" onclick="return confirm('Reject & Delete this transaction?');">❌ Reject</a>
                    </td>
                </tr>{% else %}<tr><td colspan="4" style="text-align:center; color:#9ca3af; padding: 40px;">No pending vouchers requiring approval.</td></tr>{% endfor %}
            </table>
        </div>
    </div>
    <script>document.addEventListener("DOMContentLoaded", function() { setAutoDateTime(); });</script>
    </body></html>'''

EXPRESS_ENTRY_HTML = '''<div class="express-entry no-print"><h3 style="margin-top: 0; color: #3730a3; font-size: 1.15em;">🚀 Express Direct Entry (Main Book)</h3><form action="/add_express" method="POST" style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap;"><input type="hidden" name="date" id="express_date"><input type="hidden" name="time" id="express_time"><input type="text" name="description" placeholder="Description / Reason" required style="flex: 3; min-width: 200px; border-color: #a5b4fc;"><select name="type" required style="flex: 1; min-width: 150px; font-weight: bold; border-color: #a5b4fc;"><option value="income">➕ Cash In</option><option value="expense">➖ Cash Out</option></select><input type="number" step="0.01" min="0" name="amount" placeholder="Amount (₹)" value="0" required style="flex: 1; min-width: 120px; border-color: #a5b4fc;"><button class="btn" type="submit" style="flex: 1; min-width: 150px; background: #4f46e5;">⚡ Save Instant</button></form></div>'''
ENTRY_FORM_HTML = '''<form action="/add_batch_unified" method="POST" class="no-print"><input type="hidden" name="source_page" value="{{ active_page }}"><div style="background: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid var(--border); margin-bottom: 20px;"><div class="flex-row" style="margin-bottom: 15px;"><div class="form-group flex-1" style="min-width: 140px; margin-bottom: 0;"><label>Date</label><input type="date" name="date" required></div><div class="form-group flex-1" style="min-width: 140px; margin-bottom: 0;"><label>Time</label><input type="time" name="time" required></div><div class="form-group flex-1" style="min-width: 150px; margin-bottom: 0;"><label>Payment Mode</label><select name="payment_mode" required><option value="Cash">💵 Cash</option><option value="Online">💳 Online</option></select></div></div><div class="flex-row"><div class="form-group flex-1" style="min-width: 200px; margin-bottom: 0;"><label>Transaction Nature</label><select name="txn_nature" id="txn_nature" onchange="toggleNature()" required style="border-color: var(--primary); font-weight: bold; font-size: 1.05em;"><option value="slip_in" style="color:var(--danger);">➖ Submit Slip / Bill (- Deduct from User Bal)</option><option value="advance" style="color:var(--primary);">📤 Give Advance Payment (+ Positive User Bal)</option><option value="receive_cash" style="color:var(--success);">📥 Receive Cash Settlement (- Deduct from User Bal)</option></select></div><div class="form-group flex-1" style="min-width: 250px; margin-bottom: 0; flex: 2;"><label id="primary_label" style="color: var(--primary);">Ledger Account</label><select name="primary_account" id="primary_account" onchange="checkNewAccount(this)" required style="border-color: var(--primary); font-weight: bold; background: white; font-size: 1.05em;"><option value="main" style="font-weight:bold;">🏢 Main Cash Book (Default)</option><optgroup label="👥 Person Ledgers">{% for p in persons %}<option value="person_{{ p.id }}">👤 {{ p.name }}'s Account</option>{% endfor %}</optgroup><optgroup label="💸 Dasti Accounts">{% for dp in dasti_persons %}<option value="dasti_{{ dp.id }}">💸 {{ dp.name }}'s Dasti</option>{% endfor %}</optgroup><option value="new_dasti" style="color: #0ea5e9; font-weight: bold;">➕ Create New Dasti Account...</option><option value="new_person" style="color: var(--success); font-weight: bold;">➕ Create New Person Account...</option></select><input type="text" name="new_account_name" id="new_account_name" placeholder="Type New Name Here..." style="display:none; margin-top: 8px; border-color: var(--primary); width: 100%;"></div></div></div><div style="border: 1px solid var(--border); border-radius: 8px; margin-bottom: 20px; background: #fff; overflow-x: auto;"><table style="width: 100%; min-width: 800px; margin: 0; background: transparent;"><thead style="background: #f1f5f9;"><tr><th style="width: 25%;">Category</th><th style="width: 50%;">Bill Detail / Description</th><th style="width: 20%;">Amount (₹)</th><th style="width: 5%; text-align: center;">Act</th></tr></thead><tbody id="entryBody"></tbody></table></div><div style="display: flex; gap: 15px; justify-content: space-between;"><button type="button" class="btn-outline" onclick="addRow('{% for c in categories %}<option value=\\\'{{c}}\\\'>{{c}}</option>{% endfor %}')" style="min-width: 200px; font-size: 1em;">+ Add Another Row</button><button class="btn-success" type="submit" style="min-width: 250px; font-size: 1.1em; padding: 12px;">💾 Save Batch Voucher</button></div></form><script>document.addEventListener("DOMContentLoaded", function() { initForm('{% for c in categories %}<option value="{{c}}">{{c}}</option>{% endfor %}'); });</script>'''
EDIT_TEMPLATE = '''<!DOCTYPE html><html><head><title>Edit Entry</title>''' + BASE_STYLE + '''</head><body><div class="container">''' + NAVBAR_HTML + '''<div class="card" style="max-width: 650px; margin: 0 auto;"><h2 style="color: var(--primary); margin-bottom: 20px;">✏️ Edit / Correct Transaction</h2><form action="/edit/{{ table_name }}/{{ entry.id }}" method="POST"><div class="flex-row"><div class="form-group flex-1"><label>Date</label><input type="date" name="date" value="{{ entry.date }}" required></div><div class="form-group flex-1"><label>Time</label><input type="time" name="time" value="{{ entry.time }}" required></div></div><div class="flex-row"><div class="form-group flex-1"><label>Mode</label><select name="payment_mode" required><option value="Cash" {% if entry.payment_mode == 'Cash' %}selected{% endif %}>Cash</option><option value="Online" {% if entry.payment_mode == 'Online' %}selected{% endif %}>Online</option></select></div><div class="form-group flex-1"><label>Category</label><select name="category" onchange="toggleCustomCategory(this)" required>{% for c in categories %}<option value="{{ c }}" {% if entry.category == c %}selected{% endif %}>{{ c }}</option>{% endfor %}<option value="Other" {% if entry.category not in categories %}selected{% endif %}>Other (Type Below)...</option></select><input type="text" name="custom_category" value="{% if entry.category not in categories %}{{ entry.category }}{% endif %}" placeholder="Custom Category..." style="display:{% if entry.category not in categories %}block{% else %}none{% endif %}; margin-top: 8px; border-color: var(--primary);"></div></div><div class="form-group"><label>Description / Bill Details</label><input type="text" name="description" value="{{ entry.description }}" required></div>{% if has_link %}<div style="background:#e0e7ff; border:2px solid #818cf8; padding:15px; border-radius:10px; margin-bottom: 15px;"><h4 style="margin:0 0 10px 0; color:#3730a3; font-size:0.95em;">🔧 Correct Account / Nature <small>(fixes voucher posted to wrong person or wrong type)</small></h4><div class="flex-row"><div class="form-group flex-1" style="min-width:200px; margin-bottom:0;"><label>Transaction Nature</label><select name="txn_nature" required style="border-color: var(--primary); font-weight:bold;"><option value="slip_in" {% if current_nature == 'slip_in' %}selected{% endif %}>➖ Submit Slip / Bill (- Deduct)</option><option value="advance" {% if current_nature == 'advance' %}selected{% endif %}>📤 Give Advance Payment (+ Positive)</option><option value="receive_cash" {% if current_nature == 'receive_cash' %}selected{% endif %}>📥 Receive Cash Settlement (- Deduct)</option></select></div><div class="form-group flex-1" style="min-width:220px; margin-bottom:0;"><label>Ledger Account</label><select name="primary_account" onchange="checkNewAccount(this)" required style="border-color: var(--primary); font-weight:bold; background:white;"><option value="main" {% if current_account_type == 'main' %}selected{% endif %}>🏢 Main Cash Book</option><optgroup label="👥 Person Ledgers">{% for p in persons %}<option value="person_{{ p.id }}" {% if current_account_type == 'person' and current_primary_id == p.id %}selected{% endif %}>👤 {{ p.name }}</option>{% endfor %}</optgroup><optgroup label="💸 Dasti Accounts">{% for dp in dasti_persons %}<option value="dasti_{{ dp.id }}" {% if current_account_type == 'dasti' and current_primary_id == dp.id %}selected{% endif %}>💸 {{ dp.name }}</option>{% endfor %}</optgroup><option value="new_dasti">➕ Create New Dasti Account...</option><option value="new_person">➕ Create New Person Account...</option></select><input type="text" name="new_account_name" id="new_account_name" placeholder="Type New Name Here..." style="display:none; margin-top: 8px; border-color: var(--primary);"></div></div></div>{% else %}<div class="flex-row"><div class="form-group flex-1"><label>Type</label><select name="type" required><option value="income" {% if entry.type == 'income' %}selected{% endif %}>➕ Main In</option><option value="expense" {% if entry.type == 'expense' %}selected{% endif %}>➖ Main Out</option><option value="dasti_out" {% if entry.type == 'dasti_out' %}selected{% endif %}>📤 Transfer (Main Out)</option><option value="batch_ledger_out" {% if entry.type == 'batch_ledger_out' %}selected{% endif %}>➖ Ledger Slip Out</option><option value="dasti_voucher_out" {% if entry.type == 'dasti_voucher_out' %}selected{% endif %}>💸 Dasti Voucher Out</option><option value="dasti_voucher_in" {% if entry.type == 'dasti_voucher_in' %}selected{% endif %}>💸 Dasti Settlement In</option><option value="settlement" {% if entry.type == 'settlement' %}selected{% endif %}>➖ Person Bill / Settlement</option><option value="advance" {% if entry.type == 'advance' %}selected{% endif %}>➕ Person Advance</option></select></div><div class="form-group flex-1"><label>Amount (₹)</label><input type="number" step="0.01" min="0" name="amount" value="{{ entry.amount }}" required></div></div>{% endif %}{% if has_link %}<div class="form-group"><label>Amount (₹)</label><input type="number" step="0.01" min="0" name="amount" value="{{ entry.amount }}" required></div>{% endif %}{% if session.get('can_approve') == 1 or session.get('role') in ['admin', 'superadmin'] %}<div class="form-group" style="background:#fffbeb; padding:12px; border-radius:8px; border:1px solid #fde68a; margin-top: 5px;"><label style="color:#92400e;">⏳ Approval Status <small>(Cashier/Approver Control)</small></label><select name="status" style="border-color: var(--warning); font-weight:bold;"><option value="pending" {% if entry.status == 'pending' %}selected{% endif %}>⏳ Pending</option><option value="approved" {% if entry.status == 'approved' %}selected{% endif %}>✅ Approved</option></select><label style="color:#92400e; margin-top:12px;">✅ Approved By <small>(Select who approved this voucher)</small></label><select name="approved_by_select" onchange="toggleCustomCategory(this)" style="border-color: var(--warning);"><option value="">-- Not Set --</option><optgroup label="✅ Approvers">{% for u in approvers %}{% if u.can_approve %}<option value="{{ u.username }}" {% if entry.approved_by == u.username %}selected{% endif %}>{{ u.username }}</option>{% endif %}{% endfor %}</optgroup><optgroup label="👤 Other Users">{% for u in approvers %}{% if not u.can_approve %}<option value="{{ u.username }}" {% if entry.approved_by == u.username %}selected{% endif %}>{{ u.username }}</option>{% endif %}{% endfor %}</optgroup><option value="other" {% if entry.approved_by and entry.approved_by not in approver_names %}selected{% endif %}>✏️ Other (Type Name)...</option></select><input type="text" name="approved_by_custom" value="{% if entry.approved_by and entry.approved_by not in approver_names %}{{ entry.approved_by }}{% endif %}" placeholder="Type Approver Name..." style="display:{% if entry.approved_by and entry.approved_by not in approver_names %}block{% else %}none{% endif %}; margin-top: 8px; border-color: var(--primary);"></div>{% endif %}<div style="display: flex; gap: 15px; margin-top: 20px;"><a href="javascript:history.back()" class="btn btn-outline" style="flex:1;">Cancel / Exit</a><button class="btn-success" type="submit" style="flex:1;">Save Changes</button></div></form></div></div></body></html>'''
INDEX_TEMPLATE = '''<!DOCTYPE html><html><head><title>Main Cash Book Dashboard</title>''' + BASE_STYLE + '''</head><body><div class="container">''' + NAVBAR_HTML + '''<div class="card no-print" style="padding: 20px; background: linear-gradient(to right, #ffffff, #f1f5f9);"><h3 style="margin-bottom: 15px; font-size: 1.2em; color: #475569;">📈 Account Flow Summary</h3><div class="stats-grid" style="grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 0;"><div class="stat-card" style="padding: 15px;"><h4>Today</h4><div style="color:var(--success); font-weight:bold;">+ ₹{{ "{:,.2f}".format(s_d_in) }}</div><div style="color:var(--danger); font-weight:bold;">- ₹{{ "{:,.2f}".format(s_d_out) }}</div></div><div class="stat-card" style="padding: 15px;"><h4>Last 7 Days</h4><div style="color:var(--success); font-weight:bold;">+ ₹{{ "{:,.2f}".format(s_w_in) }}</div><div style="color:var(--danger); font-weight:bold;">- ₹{{ "{:,.2f}".format(s_w_out) }}</div></div><div class="stat-card" style="padding: 15px;"><h4>This Month</h4><div style="color:var(--success); font-weight:bold;">+ ₹{{ "{:,.2f}".format(s_m_in) }}</div><div style="color:var(--danger); font-weight:bold;">- ₹{{ "{:,.2f}".format(s_m_out) }}</div></div><div class="stat-card" style="padding: 15px;"><h4>This Year</h4><div style="color:var(--success); font-weight:bold;">+ ₹{{ "{:,.2f}".format(s_y_in) }}</div><div style="color:var(--danger); font-weight:bold;">- ₹{{ "{:,.2f}".format(s_y_out) }}</div></div></div></div>''' + EXPRESS_ENTRY_HTML + '''<div class="card balance-card"><h2 style="color: #64748b; font-size: 1.1em; text-transform: uppercase; margin-bottom: 0;">🏢 Available Main Cash Book Balance</h2><div class="balance-amount" style="color: {{ 'var(--success)' if balance >= 0 else 'var(--danger)' }}">₹{{ "{:,.2f}".format(balance) }}</div><div style="display: flex; justify-content: center; gap: 30px; margin-top: 15px; flex-wrap: wrap;"><div style="color: #0369a1; background: #e0f2fe; padding: 10px 15px; border-radius: 8px; border: 1px solid #bae6fd; min-width: 250px;"><strong style="font-size: 0.85em; color: #0284c7; text-transform: uppercase;">Person Ledger Advances (Outstanding)</strong><br><span style="font-size: 1.2em; font-weight: bold;">₹{{ "{:,.2f}".format(total_dasti) }}</span>{% if dasti_breakdown %}<div style="margin-top: 8px; font-size: 0.85em; color: #0369a1; text-align: left; border-top: 1px solid #bae6fd; padding-top: 8px;">{% for d in dasti_breakdown %}<div style="display: flex; justify-content: space-between; margin-bottom: 3px;"><span>👤 {{ d.name }}</span> <strong>₹{{ "{:,.2f}".format(d.amount) }}</strong></div>{% endfor %}</div>{% endif %}</div></div></div><div class="card no-print" style="padding: 25px;"><h3 style="margin-bottom: 15px; font-size: 1.3em;">⚡ Master Advanced Batch Entry</h3>''' + ENTRY_FORM_HTML + '''</div><div class="ledger-container"><div class="ledger-col"><h3 class="ledger-title" style="color: var(--success); border-bottom: 3px solid var(--success);">Receipts (+ IN)</h3><table style="width: 100%; font-size: 0.95em;"><tr><th style="width: 5%;">Sr.</th><th>Date</th><th>Mode/Cat</th><th>Detail</th><th style="text-align: right;">Amount</th>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<th class="no-print">Act</th>{% endif %}</tr>{% for t in incomes %}<tr><td style="color: #64748b; font-weight: bold;">{{ loop.index }}</td><td><span style="font-weight: 500;">{{ t.date }}</span><br><span style="font-size: 0.85em; color: #6b7280;">{{ t.time }}</span></td><td><span class="badge badge-mode">{{ t.payment_mode }}</span><br><span style="font-size: 0.85em; color: #4b5563;">{{ t.category }}</span></td><td style="white-space: pre-wrap;">{{ t.description }}{% if t.status == 'approved' and t.approved_by %}<br><span style="color: var(--success); font-size: 0.85em; font-weight: 600;">✓ Apprv: {{ t.approved_by }}</span>{% endif %}</td><td style="text-align: right;">{% if t.status == 'pending' %}<span class="badge badge-pending">⏳ Pending</span><br>{% endif %}<span class="badge badge-in">+ ₹{{ "{:,.2f}".format(t.amount) }}</span></td>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<td style="text-align: center;" class="no-print"><a href="/edit/transactions/{{ t.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;">✏️</a> <br> <a href="/delete/transactions/{{ t.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Move to Trash?');">🗑️</a></td>{% endif %}</tr>{% else %}<tr><td colspan="6" style="text-align: center; color: #9ca3af; padding: 40px 0;">No entries yet.</td></tr>{% endfor %}</table></div><div class="ledger-col"><h3 class="ledger-title" style="color: var(--danger); border-bottom: 3px solid var(--danger);">Payments (- OUT)</h3><table style="width: 100%; font-size: 0.95em;"><tr><th style="width: 5%;">Sr.</th><th>Date</th><th>Mode/Cat</th><th>Detail</th><th style="text-align: right;">Amount</th>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<th class="no-print">Act</th>{% endif %}</tr>{% for t in expenses %}<tr><td style="color: #64748b; font-weight: bold;">{{ loop.index }}</td><td><span style="font-weight: 500;">{{ t.date }}</span><br><span style="font-size: 0.85em; color: #6b7280;">{{ t.time }}</span></td><td><span class="badge badge-mode">{{ t.payment_mode }}</span><br><span style="font-size: 0.85em; color: #4b5563;">{{ t.category }}</span></td><td style="white-space: pre-wrap;">{{ t.description }}{% if t.status == 'approved' and t.approved_by %}<br><span style="color: var(--success); font-size: 0.85em; font-weight: 600;">✓ Apprv: {{ t.approved_by }}</span>{% endif %}</td><td style="text-align: right;">{% if t.status == 'pending' %}<span class="badge badge-pending">⏳ Pending</span><br>{% endif %}<span class="badge badge-out">- ₹{{ "{:,.2f}".format(t.amount) }}</span></td>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<td style="text-align: center;" class="no-print"><a href="/edit/transactions/{{ t.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;">✏️</a> <br> <a href="/delete/transactions/{{ t.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Move to Trash?');">🗑️</a></td>{% endif %}</tr>{% else %}<tr><td colspan="6" style="text-align: center; color: #9ca3af; padding: 40px 0;">No entries yet.</td></tr>{% endfor %}</table></div></div></div><script>const accountBalances = {{ account_balances | safe }};function checkBalanceBeforeSubmit(event, deductionAmount, accountKey, customMessage) {if (accountBalances[accountKey] !== undefined) {if (accountBalances[accountKey] - deductionAmount < 0) {if (!confirm("⚠️ WARNING: This entry will cause the balance of " + (customMessage || "this account") + " to go NEGATIVE.\\n\\nCurrent Balance: ₹" + accountBalances[accountKey].toFixed(2) + "\\nDeduction: ₹" + deductionAmount.toFixed(2) + "\\n\\nDo you still want to punch this entry?")) {event.preventDefault();return false;}}}return true;}document.addEventListener("DOMContentLoaded", function() {const expressForm = document.querySelector('form[action="/add_express"]');if(expressForm) {expressForm.addEventListener('submit', function(e) {const type = this.querySelector('select[name="type"]').value;if(type === 'expense') {const amt = parseFloat(this.querySelector('input[name="amount"]').value) || 0;checkBalanceBeforeSubmit(e, amt, 'main', 'Main Cash Book');}});}const transferForm = document.querySelector('form[action="/add_transfer"]');if(transferForm) {transferForm.addEventListener('submit', function(e) {const dir = this.querySelector('select[name="direction"]').value;const amt = parseFloat(this.querySelector('input[name="amount"]').value) || 0;const personId = this.querySelector('select[name="person_id"]').value;if(dir === 'main_to_person') {checkBalanceBeforeSubmit(e, amt, 'main', 'Main Cash Book');} else if(dir === 'person_to_main' && personId) {checkBalanceBeforeSubmit(e, amt, 'person_' + personId, 'Selected Person Account');}});}const batchForm = document.querySelector('form[action="/add_batch_unified"]');if(batchForm) {batchForm.addEventListener('submit', function(e) {const nature = document.getElementById('txn_nature').value;const primaryAcc = document.getElementById('primary_account').value;let totalAmt = 0;const amtInputs = this.querySelectorAll('input[name="amount[]"]');amtInputs.forEach(inp => { totalAmt += parseFloat(inp.value) || 0; });if (primaryAcc === 'new_person' || primaryAcc === 'new_dasti') {if (nature !== 'advance') {if (!confirm("⚠️ WARNING: This is a NEW account with ₹0.00 balance. Deducting ₹" + totalAmt.toFixed(2) + " will make it NEGATIVE.\\n\\nDo you want to proceed?")) {e.preventDefault(); return false;}} else { checkBalanceBeforeSubmit(e, totalAmt, 'main', 'Main Cash Book'); }} else if (primaryAcc === 'main') {if (nature !== 'receive_cash') checkBalanceBeforeSubmit(e, totalAmt, 'main', 'Main Cash Book');} else if (primaryAcc.startsWith('person_') || primaryAcc.startsWith('dasti_')) {if (nature === 'advance') { checkBalanceBeforeSubmit(e, totalAmt, 'main', 'Main Cash Book');} else { checkBalanceBeforeSubmit(e, totalAmt, primaryAcc, 'Selected Ledger Account'); }}});}});</script></body></html>'''
MAIN_LEDGER_TEMPLATE = '''<!DOCTYPE html><html><head><title>Main Cash Book Ledger</title>''' + BASE_STYLE + '''</head><body><div class="container">''' + NAVBAR_HTML + '''<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;"><h2 style="margin: 0; font-size: 1.6em;">🏢 Main Cash Book Complete Ledger</h2></div><div class="stats-grid"><div class="stat-card" style="border-top: 4px solid var(--success);"><h4>Total Received (+ In)</h4><div class="value" style="color: var(--success);">+ ₹{{ "{:,.2f}".format(total_in) }}</div></div><div class="stat-card" style="border-top: 4px solid var(--danger);"><h4>Total Payments & Advances (- Out)</h4><div class="value" style="color: var(--danger);">- ₹{{ "{:,.2f}".format(total_out) }}</div></div><div class="stat-card" style="border-top: 4px solid var(--primary); background: #f8fafc;"><h4>Available Balance</h4><div class="value">{% if balance >= 0 %}<span style="color: var(--success);">₹{{ "{:,.2f}".format(balance) }}</span>{% else %}<span style="color: var(--danger);">₹{{ "{:,.2f}".format(balance) }}</span>{% endif %}</div></div></div><div class="card" style="padding: 0; overflow-x: auto;"><h3 style="padding: 18px 25px; margin: 0; background: #f8fafc; border-bottom: 1px solid var(--border);">Detailed Transaction History</h3><table style="width: 100%; min-width: 800px;"><thead><tr><th style="padding-left: 25px; width: 15%;">Date & Time</th><th style="width: 15%;">Mode/Category</th><th style="width: 45%;">Bill No / Details & Link</th><th style="text-align: right; width: 15%;">Amount</th>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<th style="text-align: center; width: 10%;">Act</th>{% endif %}</tr></thead><tbody>{% for txn in txns %}<tr><td style="padding-left: 25px;"><span style="font-weight: 500;">{{ txn.date }}</span><br><span style="color: #6b7280; font-size: 0.85em;">{{ txn.time }}</span></td><td><span class="badge badge-mode">{{ txn.payment_mode }}</span><br><span style="font-size: 0.85em; color: #4b5563;">{{ txn.category }}</span></td><td style="white-space: pre-wrap;">{{ txn.description }}{% if txn.status == 'approved' and txn.approved_by %}<br><span style="color: var(--success); font-size: 0.85em; font-weight: 600;">✓ Apprv: {{ txn.approved_by }}</span>{% endif %}</td><td style="text-align: right;">{% if txn.status == 'pending' %}<span class="badge badge-pending">⏳ Pending</span><br>{% endif %}{% if txn.type in ['expense', 'dasti_out', 'batch_ledger_out', 'dasti_voucher_out'] %}<span class="badge badge-out">- ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>({% if txn.type == 'dasti_out' %}Transfer Out{% elif txn.type == 'batch_ledger_out' %}Ledger Slip Out{% elif txn.type == 'dasti_voucher_out' %}Dasti Advance Out{% else %}Payment Out{% endif %})</small></span>{% else %}<span class="badge badge-in">+ ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>(Receipt/In)</small></span>{% endif %}</td>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<td style="text-align: center;"><a href="/edit/transactions/{{ txn.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;">✏️</a> <br> <a href="/delete/transactions/{{ txn.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Move to Trash?');">🗑️</a></td>{% endif %}</tr>{% else %}<tr><td colspan="5" style="text-align:center; color:#9ca3af; padding: 40px;">No entries found in Main Cash Book.</td></tr>{% endfor %}</tbody></table></div></div></body></html>'''
PERSONS_TEMPLATE = '''<!DOCTYPE html><html><head><title>Person Ledgers</title>''' + BASE_STYLE + '''</head><body><div class="container">''' + NAVBAR_HTML + '''<div class="card" style="padding: 0;"><h3 style="padding: 15px 20px; margin: 0; background: #f8fafc; border-bottom: 1px solid var(--border); font-size: 1.2em;">📊 Outstanding Balances & Person Ledgers</h3><table style="width: 100%; border: none;"><tr><th style="padding-left: 20px; font-size: 1em;">Name</th><th style="text-align: right; font-size: 1em;">Net Status</th><th style="text-align: center; width: 220px; padding-right: 20px; font-size: 1em;">Action</th></tr>{% for b in balances %}<tr><td style="padding-left: 20px; font-weight: 500; font-size: 1.1em;">{{ b.name }}</td><td style="text-align: right;">{% if b.net > 0 %}<span class="badge badge-primary" style="font-size: 1em; padding: 6px 12px; background: #e0e7ff; color: #3730a3; border-radius: 8px;">+ ₹{{ "{:,.2f}".format(b.net) }} (Owes Firm)</span>{% elif b.net < 0 %}<span class="badge badge-success" style="font-size: 1em; padding: 6px 12px; background: #d1fae5; color: #065f46; border-radius: 8px;">- ₹{{ "{:,.2f}".format(b.net|abs) }} (Firm Owes)</span>{% else %}<span style="color: #9ca3af; font-weight: 600;">✓ Settled</span>{% endif %}</td><td style="text-align: center; padding-right: 20px;"><a href="/person_account/{{ b.id }}" class="btn btn-outline btn-sm">View</a> {% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<button onclick="let n=prompt('Edit Name:', '{{ b.name }}'); if(n) window.location='/edit_person/{{ b.id }}?name='+encodeURIComponent(n);" class="btn btn-sm" style="background:#f59e0b; color:white;">✏️</button>{% endif %}</td></tr>{% else %}<tr><td colspan="3" style="text-align:center; color:#9ca3af; padding: 40px;">No active profiles. Create one from the Dashboard Batch Entry!</td></tr>{% endfor %}</table></div></div></body></html>'''
PERSON_ACCOUNT_TEMPLATE = '''<!DOCTYPE html><html><head><title>Account: {{ person.name }}</title>''' + BASE_STYLE + '''</head><body><div class="container">''' + NAVBAR_HTML + '''<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;"><a href="/persons" class="btn-outline" style="text-decoration: none; padding: 8px 15px; border-radius: 8px; font-size: 0.9em;">← Back to Ledgers</a><h2 style="margin: 0; font-size: 1.6em;">Person Ledger: <span style="color: var(--primary);">{{ person.name }}</span></h2></div><div class="stats-grid"><div class="stat-card" style="border-top: 4px solid var(--primary);"><h4>Total Advances (Received from Main)</h4><div class="value" style="color: var(--primary);">+ ₹{{ "{:,.2f}".format(advances) }}</div></div><div class="stat-card" style="border-top: 4px solid var(--success);"><h4>Total Slips / Settlements</h4><div class="value" style="color: var(--success);">- ₹{{ "{:,.2f}".format(settlements) }}</div></div><div class="stat-card" style="border-top: 4px solid #8b5cf6; background: #f8fafc;"><h4>Net Status</h4><div class="value">{% if balance > 0 %}<span style="color: var(--primary);">+ ₹{{ "{:,.2f}".format(balance) }}<br><small style="font-size: 0.5em; color: #4b5563; text-transform: uppercase;">Owes Firm</small></span>{% elif balance < 0 %}<span style="color: var(--success);">- ₹{{ "{:,.2f}".format(balance|abs) }}<br><small style="font-size: 0.5em; color: #4b5563; text-transform: uppercase;">Firm Owes</small></span>{% else %}<span style="color: #6b7280; font-size: 0.9em;">Fully Settled</span>{% endif %}</div></div></div><div class="card" style="padding: 0; overflow-x: auto;"><h3 style="padding: 18px 25px; margin: 0; background: #f8fafc; border-bottom: 1px solid var(--border);">Detailed Transaction History</h3><table style="width: 100%; min-width: 800px;"><thead><tr><th style="padding-left: 25px; width: 15%;">Date & Time</th><th style="width: 15%;">Mode/Category</th><th style="width: 45%;">Bill No / Details & Link</th><th style="text-align: right; width: 15%;">Amount</th>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<th style="text-align: center; width: 10%;">Act</th>{% endif %}</tr></thead><tbody>{% for txn in txns %}<tr><td style="padding-left: 25px;"><span style="font-weight: 500;">{{ txn.date }}</span><br><span style="color: #6b7280; font-size: 0.85em;">{{ txn.time }}</span></td><td><span class="badge badge-mode">{{ txn.payment_mode }}</span><br><span style="font-size: 0.85em; color: #4b5563;">{{ txn.category }}</span></td><td style="white-space: pre-wrap;">{{ txn.description }}{% if txn.status == 'approved' and txn.approved_by %}<br><span style="color: var(--success); font-size: 0.85em; font-weight: 600;">✓ Apprv: {{ txn.approved_by }}</span>{% endif %}</td><td style="text-align: right;">{% if txn.status == 'pending' %}<span class="badge badge-pending">⏳ Pending</span><br>{% endif %}{% if txn.type == 'advance' %}<span class="badge badge-in" style="background:#e0e7ff; color:#3730a3;">+ ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>(Advance)</small></span>{% else %}<span class="badge badge-out" style="background:#d1fae5; color:#065f46;">- ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>(Slip / Settle)</small></span>{% endif %}</td>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<td style="text-align: center;"><a href="/edit/person_ledger/{{ txn.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;">✏️</a> <br> <a href="/delete/person_ledger/{{ txn.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Move to Trash?');">🗑️</a></td>{% endif %}</tr>{% else %}<tr><td colspan="5" style="text-align:center; color:#9ca3af; padding: 40px;">No historical entries found for this person.</td></tr>{% endfor %}</tbody></table></div></div></body></html>'''
DASTI_LEDGER_TEMPLATE = '''<!DOCTYPE html><html><head><title>Dasti Ledger</title>''' + BASE_STYLE + '''</head><body><div class="container">''' + NAVBAR_HTML + '''<div class="card balance-card" style="margin-bottom: 25px;"><h2 style="color: #64748b; font-size: 1.1em; text-transform: uppercase; margin-bottom: 0;">🏢 Available Main Cash Book Balance</h2><div class="balance-amount" style="color: {{ 'var(--success)' if balance >= 0 else 'var(--danger)' }}">₹{{ "{:,.2f}".format(balance) }}</div><div style="display: flex; justify-content: center; margin-top: 15px;"><div style="color: #0369a1; background: #e0f2fe; padding: 10px 15px; border-radius: 8px; border: 1px solid #bae6fd; min-width: 250px;"><strong style="font-size: 0.85em; color: #0284c7; text-transform: uppercase;">💸 Total Dasti Balance (Outstanding)</strong><br><span style="font-size: 1.2em; font-weight: bold;">₹{{ "{:,.2f}".format(total_outstanding_dasti) }}</span></div></div></div><div class="card no-print" style="padding: 0;"><h3 style="padding: 15px 20px; margin: 0; background: #f8fafc; border-bottom: 1px solid var(--border); font-size: 1.2em;">📊 Outstanding Dasti Accounts</h3><table style="width: 100%; border: none;"><tr><th style="padding-left: 20px; font-size: 1em;">Dasti Name</th><th style="text-align: right; font-size: 1em;">Net Status</th><th style="text-align: center; width: 220px; padding-right: 20px; font-size: 1em;">Action</th></tr>{% for b in balances %}<tr><td style="padding-left: 20px; font-weight: 500; font-size: 1.1em;">{{ b.name }}</td><td style="text-align: right;">{% if b.net > 0 %}<span class="badge badge-primary" style="font-size: 1em; padding: 6px 12px; background: #e0f2fe; color: #0369a1; border-radius: 8px;">+ ₹{{ "{:,.2f}".format(b.net) }} (Owes Firm)</span>{% elif b.net < 0 %}<span class="badge badge-success" style="font-size: 1em; padding: 6px 12px; background: #d1fae5; color: #065f46; border-radius: 8px;">- ₹{{ "{:,.2f}".format(b.net|abs) }} (Firm Owes)</span>{% else %}<span style="color: #9ca3af; font-weight: 600;">✓ Settled</span>{% endif %}</td><td style="text-align: center; padding-right: 20px;"><a href="/dasti_account/{{ b.id }}" class="btn btn-outline btn-sm">View</a> {% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<button onclick="let n=prompt('Edit Name:', '{{ b.name }}'); if(n) window.location='/edit_dasti_person/{{ b.id }}?name='+encodeURIComponent(n);" class="btn btn-sm" style="background:#f59e0b; color:white;">✏️</button>{% endif %}</td></tr>{% else %}<tr><td colspan="3" style="text-align:center; color:#9ca3af; padding: 40px;">No active Dasti accounts yet. Type a name in the Master Batch voucher to create one!</td></tr>{% endfor %}</table></div></div></body></html>'''
DASTI_ACCOUNT_TEMPLATE = '''<!DOCTYPE html><html><head><title>Dasti Account: {{ person.name }}</title>''' + BASE_STYLE + '''</head><body><div class="container">''' + NAVBAR_HTML + '''<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;"><a href="/dasti_ledger" class="btn-outline" style="text-decoration: none; padding: 8px 15px; border-radius: 8px; font-size: 0.9em;">← Back to Dasti Ledgers</a><h2 style="margin: 0; font-size: 1.6em;">Dasti Ledger: <span style="color: #0ea5e9;">{{ person.name }}</span></h2></div><div class="stats-grid"><div class="stat-card" style="border-top: 4px solid #0ea5e9;"><h4>Total Advances (Given Out)</h4><div class="value" style="color: #0ea5e9;">+ ₹{{ "{:,.2f}".format(advances) }}</div></div><div class="stat-card" style="border-top: 4px solid var(--success);"><h4>Total Slips / Settlements</h4><div class="value" style="color: var(--success);">- ₹{{ "{:,.2f}".format(settlements) }}</div></div><div class="stat-card" style="border-top: 4px solid #8b5cf6; background: #f8fafc;"><h4>Net Status</h4><div class="value">{% if balance > 0 %}<span style="color: #0ea5e9;">+ ₹{{ "{:,.2f}".format(balance) }}<br><small style="font-size: 0.5em; color: #4b5563; text-transform: uppercase;">Owes Firm</small></span>{% elif balance < 0 %}<span style="color: var(--success);">- ₹{{ "{:,.2f}".format(balance|abs) }}<br><small style="font-size: 0.5em; color: #4b5563; text-transform: uppercase;">Firm Owes</small></span>{% else %}<span style="color: #6b7280; font-size: 0.9em;">Fully Settled</span>{% endif %}</div></div></div><div class="card" style="padding: 0; overflow-x: auto;"><h3 style="padding: 18px 25px; margin: 0; background: #f8fafc; border-bottom: 1px solid var(--border);">Detailed Transaction History</h3><table style="width: 100%; min-width: 800px;"><thead><tr><th style="padding-left: 25px; width: 15%;">Date & Time</th><th style="width: 15%;">Mode/Category</th><th style="width: 45%;">Dasti Detail & Link</th><th style="text-align: right; width: 15%;">Amount</th>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<th style="text-align: center; width: 10%;">Act</th>{% endif %}</tr></thead><tbody>{% for txn in txns %}<tr><td style="padding-left: 25px;"><span style="font-weight: 500;">{{ txn.date }}</span><br><span style="color: #6b7280; font-size: 0.85em;">{{ txn.time }}</span></td><td><span class="badge badge-mode">{{ txn.payment_mode }}</span><br><span style="font-size: 0.85em; color: #4b5563;">{{ txn.category }}</span></td><td style="white-space: pre-wrap;">{{ txn.description }}{% if txn.status == 'approved' and txn.approved_by %}<br><span style="color: var(--success); font-size: 0.85em; font-weight: 600;">✓ Apprv: {{ txn.approved_by }}</span>{% endif %}</td><td style="text-align: right;">{% if txn.status == 'pending' %}<span class="badge badge-pending">⏳ Pending</span><br>{% endif %}{% if txn.type == 'advance' %}<span class="badge badge-in" style="background:#e0f2fe; color:#0369a1;">+ ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>(Advance Given)</small></span>{% else %}<span class="badge badge-out" style="background:#d1fae5; color:#065f46;">- ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>(Slip / Settle)</small></span>{% endif %}</td>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<td style="text-align: center;"><a href="/edit/dasti_ledger/{{ txn.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;">✏️</a> <br> <a href="/delete/dasti_ledger/{{ txn.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Move to Trash?');">🗑️</a></td>{% endif %}</tr>{% else %}<tr><td colspan="5" style="text-align:center; color:#9ca3af; padding: 40px;">No historical entries found for this person.</td></tr>{% endfor %}</tbody></table></div></div></body></html>'''


# --- FIREBASE HELPER LOGIC ---

def has_users():
    docs = db.collection('users').limit(1).stream()
    return any(True for _ in docs)

def get_categories(firm_id):
    docs = db.collection('categories').where('firm_id', '==', firm_id).stream()
    custom = [doc.to_dict().get('name') for doc in docs]
    return ['General', 'Sales', 'Purchase', 'Salary', 'Transport'] + custom

# --- ROUTES ---

@app.route('/')
def index():
    if not has_users(): return redirect(url_for('register'))
    if 'user_id' not in session: return redirect(url_for('login'))
    firm_id = session['firm_id']
    
    persons = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('persons').where('user_id', '==', firm_id).stream()]
    persons.sort(key=lambda x: x.get('name', ''))
    
    dasti_persons = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('dasti_persons').where('user_id', '==', firm_id).stream()]
    dasti_persons.sort(key=lambda x: x.get('name', ''))
    
    all_txns = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('transactions').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    
    incomes = [t for t in all_txns if t.get('type') == 'income']
    expenses = [t for t in all_txns if t.get('type') in ('expense', 'batch_ledger_out')]
    
    incomes.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=True)
    expenses.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0))) 
    
    total_in_actual = sum(float(t.get('amount', 0)) for t in all_txns if t.get('type') in ('income', 'dasti_voucher_in') and t.get('status') == 'approved')
    total_out_actual = sum(float(t.get('amount', 0)) for t in all_txns if t.get('type') in ('expense', 'dasti_out', 'dasti_voucher_out') and t.get('status') == 'approved')
    main_balance = total_in_actual - total_out_actual

    all_person_ledger = [doc.to_dict() for doc in db.collection('person_ledger').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    all_dasti_ledger = [doc.to_dict() for doc in db.collection('dasti_ledger').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]

    acc_bals = {'main': main_balance}
    total_dasti_ledger = 0.0
    dasti_breakdown = []
    
    for p in persons:
        adv = sum(float(l.get('amount', 0)) for l in all_person_ledger if l.get('person_id') == p['id'] and l.get('type') == 'advance' and l.get('status') == 'approved')
        setl = sum(float(l.get('amount', 0)) for l in all_person_ledger if l.get('person_id') == p['id'] and l.get('type') == 'settlement' and l.get('status') == 'approved')
        owed = adv - setl
        acc_bals[f"person_{p['id']}"] = owed
        if owed > 0:
            total_dasti_ledger += owed
            dasti_breakdown.append({'name': p['name'], 'amount': owed})

    for dp in dasti_persons:
        adv = sum(float(l.get('amount', 0)) for l in all_dasti_ledger if l.get('dasti_person_id') == dp['id'] and l.get('type') == 'advance' and l.get('status') == 'approved')
        setl = sum(float(l.get('amount', 0)) for l in all_dasti_ledger if l.get('dasti_person_id') == dp['id'] and l.get('type') == 'settlement' and l.get('status') == 'approved')
        acc_bals[f"dasti_{dp['id']}"] = adv - setl
            
    summary_txns = [t for t in all_txns if t.get('status') == 'approved']
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    month_str = now.strftime('%Y-%m')
    year_str = now.strftime('%Y')
    week_ago_str = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    
    s_d_in = s_d_out = s_w_in = s_w_out = s_m_in = s_m_out = s_y_in = s_y_out = 0
    for r in summary_txns:
        amt, d, ttype = float(r.get('amount', 0)), r.get('date', ''), r.get('type', '')
        is_in = ttype in ('income', 'dasti_voucher_in')
        is_out = ttype in ('expense', 'dasti_out', 'dasti_voucher_out') 
        if d.startswith(year_str):
            if is_in: s_y_in += amt 
            elif is_out: s_y_out += amt
        if d.startswith(month_str):
            if is_in: s_m_in += amt 
            elif is_out: s_m_out += amt
        if d >= week_ago_str:
            if is_in: s_w_in += amt 
            elif is_out: s_w_out += amt
        if d == today_str:
            if is_in: s_d_in += amt 
            elif is_out: s_d_out += amt

    cats = get_categories(firm_id)
    return render_template_string(INDEX_TEMPLATE, persons=persons, dasti_persons=dasti_persons, incomes=incomes, expenses=expenses, balance=main_balance, account_balances=json.dumps(acc_bals), total_dasti=total_dasti_ledger, dasti_breakdown=dasti_breakdown, categories=cats, s_d_in=s_d_in, s_d_out=s_d_out, s_w_in=s_w_in, s_w_out=s_w_out, s_m_in=s_m_in, s_m_out=s_m_out, s_y_in=s_y_in, s_y_out=s_y_out, username=session['username'], active_page='home')

@app.route('/main_ledger')
def main_ledger():
    if 'user_id' not in session: return redirect(url_for('login'))
    firm_id = session['firm_id']
    
    all_txns = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('transactions').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    all_txns.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=True)
    
    total_in = sum(float(t.get('amount', 0)) for t in all_txns if t.get('type') in ('income', 'dasti_voucher_in') and t.get('status') == 'approved')
    total_out = sum(float(t.get('amount', 0)) for t in all_txns if t.get('type') == 'expense' and t.get('status') == 'approved')
    total_dasti = sum(float(t.get('amount', 0)) for t in all_txns if t.get('type') == 'dasti_out' and t.get('status') == 'approved')
    total_dasti_vouchers = sum(float(t.get('amount', 0)) for t in all_txns if t.get('type') == 'dasti_voucher_out' and t.get('status') == 'approved')
    
    balance = total_in - (total_out + total_dasti + total_dasti_vouchers)
    return render_template_string(MAIN_LEDGER_TEMPLATE, txns=all_txns, balance=balance, total_in=total_in, total_out=total_out, total_dasti=total_dasti, total_dasti_vouchers=total_dasti_vouchers, username=session['username'], active_page='main_ledger')

@app.route('/dasti_ledger')
def dasti_ledger():
    if 'user_id' not in session: return redirect(url_for('login'))
    firm_id = session['firm_id']
    
    all_txns = [doc.to_dict() for doc in db.collection('transactions').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    total_in = sum(float(t.get('amount', 0)) for t in all_txns if t.get('type') in ('income', 'dasti_voucher_in') and t.get('status') == 'approved')
    total_out = sum(float(t.get('amount', 0)) for t in all_txns if t.get('type') in ('expense', 'dasti_out', 'dasti_voucher_out') and t.get('status') == 'approved')
    main_balance = total_in - total_out

    dasti_persons = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('dasti_persons').where('user_id', '==', firm_id).stream()]
    dasti_persons.sort(key=lambda x: x.get('name', ''))
    
    all_dasti_ledger = [doc.to_dict() for doc in db.collection('dasti_ledger').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    
    balances = []
    total_outstanding_dasti = 0.0
    
    for p in dasti_persons:
        adv = sum(float(l.get('amount', 0)) for l in all_dasti_ledger if l.get('dasti_person_id') == p['id'] and l.get('type') == 'advance' and l.get('status') == 'approved')
        setl = sum(float(l.get('amount', 0)) for l in all_dasti_ledger if l.get('dasti_person_id') == p['id'] and l.get('type') == 'settlement' and l.get('status') == 'approved')
        net = adv - setl
        balances.append({'id': p['id'], 'name': p['name'], 'net': net})
        if net > 0:
            total_outstanding_dasti += net
            
    return render_template_string(DASTI_LEDGER_TEMPLATE, balances=balances, balance=main_balance, total_outstanding_dasti=total_outstanding_dasti, username=session['username'], active_page='dasti_ledger')

@app.route('/dasti_account/<string:person_id>')
def dasti_account(person_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    firm_id = session['firm_id']
    
    person_doc = db.collection('dasti_persons').document(person_id).get()
    if not person_doc.exists or person_doc.to_dict().get('user_id') != firm_id: return redirect(url_for('dasti_ledger'))
    person = {'id': person_doc.id, **person_doc.to_dict()}
    
    txns = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('dasti_ledger').where('dasti_person_id', '==', person_id).where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    txns.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=True)
    
    advances = sum(float(t.get('amount', 0)) for t in txns if t.get('type') == 'advance' and t.get('status') == 'approved')
    settlements = sum(float(t.get('amount', 0)) for t in txns if t.get('type') == 'settlement' and t.get('status') == 'approved')
    
    return render_template_string(DASTI_ACCOUNT_TEMPLATE, person=person, txns=txns, balance=(advances - settlements), advances=advances, settlements=settlements, username=session['username'], active_page='dasti_ledger')

@app.route('/edit_dasti_person/<string:id>')
def edit_dasti_person(id):
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): return redirect(url_for('login'))
    new_name = request.args.get('name')
    if new_name:
        doc_ref = db.collection('dasti_persons').document(id)
        if doc_ref.get().to_dict().get('user_id') == session['firm_id']:
            doc_ref.update({'name': new_name})
    return redirect(url_for('dasti_ledger'))

@app.route('/persons')
def persons():
    if 'user_id' not in session: return redirect(url_for('login'))
    firm_id = session['firm_id']
    
    person_list = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('persons').where('user_id', '==', firm_id).stream()]
    person_list.sort(key=lambda x: x.get('name', ''))
    
    all_person_ledger = [doc.to_dict() for doc in db.collection('person_ledger').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    
    balances = []
    for p in person_list:
        adv = sum(float(l.get('amount', 0)) for l in all_person_ledger if l.get('person_id') == p['id'] and l.get('type') == 'advance' and l.get('status') == 'approved')
        setl = sum(float(l.get('amount', 0)) for l in all_person_ledger if l.get('person_id') == p['id'] and l.get('type') == 'settlement' and l.get('status') == 'approved')
        balances.append({'id': p['id'], 'name': p['name'], 'net': adv - setl})
        
    return render_template_string(PERSONS_TEMPLATE, balances=balances, username=session['username'], active_page='persons')

@app.route('/person_account/<string:person_id>')
def person_account(person_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    firm_id = session['firm_id']
    
    person_doc = db.collection('persons').document(person_id).get()
    if not person_doc.exists or person_doc.to_dict().get('user_id') != firm_id: return redirect(url_for('persons'))
    person = {'id': person_doc.id, **person_doc.to_dict()}
    
    txns = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('person_ledger').where('person_id', '==', person_id).where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    txns.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=True)
    
    advances = sum(float(t.get('amount', 0)) for t in txns if t.get('type') == 'advance' and t.get('status') == 'approved')
    settlements = sum(float(t.get('amount', 0)) for t in txns if t.get('type') == 'settlement' and t.get('status') == 'approved')
    
    return render_template_string(PERSON_ACCOUNT_TEMPLATE, person=person, txns=txns, balance=(advances - settlements), advances=advances, settlements=settlements, username=session['username'], active_page='persons')

@app.route('/edit_person/<string:id>')
def edit_person(id):
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): return redirect(url_for('login'))
    new_name = request.args.get('name')
    if new_name:
        doc_ref = db.collection('persons').document(id)
        if doc_ref.get().to_dict().get('user_id') == session['firm_id']:
            doc_ref.update({'name': new_name})
    return redirect(url_for('persons'))

@app.route('/delete/<string:table_name>/<string:row_id>')
def delete_entry(table_name, row_id):
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): return redirect(url_for('index'))
    if table_name not in ['transactions', 'person_ledger', 'dasti_ledger']: return "Invalid", 400
    
    doc_ref = db.collection(table_name).document(row_id)
    doc_data = doc_ref.get().to_dict()
    
    if doc_data and doc_data.get('user_id') == session['firm_id']:
        link_id = doc_data.get('link_id', '')
        if link_id:
            for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
                linked_docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', session['firm_id']).stream()
                for d in linked_docs:
                    d.reference.update({'deleted': 1})
        else:
            doc_ref.update({'deleted': 1})
            
    return redirect(request.referrer or url_for('index'))

@app.route('/trash')
def trash():
    if 'user_id' not in session or (session.get('can_view_trash') != 1 and session.get('role') != 'superadmin'): return redirect(url_for('index'))
    trashed = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('transactions').where('user_id', '==', session['firm_id']).where('deleted', '==', 1).stream()]
    trashed.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=True)
    return render_template_string(TRASH_TEMPLATE, trashed=trashed, username=session['username'], active_page='trash')

@app.route('/restore_voucher/<string:link_id>')
def restore_voucher(link_id):
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): return redirect(url_for('index'))
    for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
        docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', session['firm_id']).stream()
        for d in docs: d.reference.update({'deleted': 0})
    return redirect(url_for('trash'))

@app.route('/hard_delete_voucher/<string:link_id>')
def hard_delete_voucher(link_id):
    if 'user_id' not in session or session.get('role') != 'superadmin': return redirect(url_for('index'))
    for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
        docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', session['firm_id']).stream()
        for d in docs: d.reference.delete()
    return redirect(url_for('trash'))

@app.route('/reports')
def reports():
    if 'user_id' not in session or (session.get('can_view_reports') != 1 and session.get('role') != 'superadmin'): return redirect(url_for('index'))
    firm_id = session['firm_id']
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    category = request.args.get('category', '')
    report_account = request.args.get('report_account', 'main')
    
    collection_name = 'transactions'
    pid_filter = None
    pid_field = None
    
    if report_account.startswith('person_'):
        collection_name = 'person_ledger'
        pid_filter = report_account.split('_')[1]
        pid_field = 'person_id'
    elif report_account.startswith('dasti_'):
        collection_name = 'dasti_ledger'
        pid_filter = report_account.split('_')[1]
        pid_field = 'dasti_person_id'
        
    query = db.collection(collection_name).where('user_id', '==', firm_id).where('deleted', '==', 0).where('status', '==', 'approved')
    if pid_filter: query = query.where(pid_field, '==', pid_filter)
    
    raw_results = [doc.to_dict() for doc in query.stream()]
    
    results = []
    for r in raw_results:
        if start_date and r.get('date', '') < start_date: continue
        if end_date and r.get('date', '') > end_date: continue
        if category and r.get('category', '') != category: continue
        results.append(r)
        
    results.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=True)
    
    total_in = sum(float(r.get('amount', 0)) for r in results if r.get('type') in ('income', 'settlement', 'dasti_voucher_in'))
    
    if report_account == 'main':
        total_out = sum(float(r.get('amount', 0)) for r in results if r.get('type') in ('expense', 'dasti_out', 'dasti_voucher_out'))
    else:
        total_out = sum(float(r.get('amount', 0)) for r in results if r.get('type') in ('expense', 'advance', 'dasti_out', 'dasti_voucher_out'))
    
    persons = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('persons').where('user_id', '==', firm_id).stream()]
    dasti_persons = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('dasti_persons').where('user_id', '==', firm_id).stream()]
    cats = get_categories(firm_id)
    
    return render_template_string(REPORTS_TEMPLATE, results=results, total_in=total_in, total_out=total_out, categories=cats, persons=persons, dasti_persons=dasti_persons, start_date=start_date, end_date=end_date, category=category, report_account=report_account, username=session['username'], active_page='reports')

@app.route('/export_reports')
def export_reports():
    if 'user_id' not in session or (session.get('can_view_reports') != 1 and session.get('role') != 'superadmin'): return redirect(url_for('index'))
    firm_id = session['firm_id']
    
    start_date, end_date, category, report_account = request.args.get('start_date', ''), request.args.get('end_date', ''), request.args.get('category', ''), request.args.get('report_account', 'main')
    
    collection_name = 'transactions'
    pid_filter = None
    pid_field = None
    
    if report_account.startswith('person_'):
        collection_name = 'person_ledger'
        pid_filter = report_account.split('_')[1]
        pid_field = 'person_id'
    elif report_account.startswith('dasti_'):
        collection_name = 'dasti_ledger'
        pid_filter = report_account.split('_')[1]
        pid_field = 'dasti_person_id'
        
    query = db.collection(collection_name).where('user_id', '==', firm_id).where('deleted', '==', 0).where('status', '==', 'approved')
    if pid_filter: query = query.where(pid_field, '==', pid_filter)
    
    raw_results = [doc.to_dict() for doc in query.stream()]
    
    results = []
    for r in raw_results:
        if start_date and r.get('date', '') < start_date: continue
        if end_date and r.get('date', '') > end_date: continue
        if category and r.get('category', '') != category: continue
        results.append(r)
        
    results.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=False)
    
    def generate():
        data = StringIO()
        writer = csv.writer(data)
        writer.writerow(('Date', 'Time', 'Mode', 'Category', 'Description', 'Type', 'Amount (INR)', 'Approved By'))
        yield data.getvalue(); data.seek(0); data.truncate(0)
        for r in results:
            writer.writerow((r.get('date', ''), r.get('time', ''), r.get('payment_mode', ''), r.get('category', ''), r.get('description', ''), r.get('type', ''), r.get('amount', 0), r.get('approved_by', '')))
            yield data.getvalue(); data.seek(0); data.truncate(0)
            
    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment; filename=Firm_Report_Export.csv"})

@app.route('/edit/<string:table_name>/<string:row_id>', methods=['GET', 'POST'])
def edit_entry(table_name, row_id):
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): return redirect(url_for('index'))
    if table_name not in ['transactions', 'person_ledger', 'dasti_ledger']: return "Invalid", 400

    firm_id = session['firm_id']
    doc_ref = db.collection(table_name).document(row_id)
    doc_data = doc_ref.get().to_dict()
    if not doc_data or doc_data.get('user_id') != firm_id: return redirect(url_for('index'))

    entry = {'id': row_id, **doc_data}
    link_id = entry.get('link_id', '')

    linked_docs = {}
    if link_id:
        for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
            found = list(db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', firm_id).stream())
            if found:
                linked_docs[collection] = (found[0].id, found[0].to_dict())

    txn_doc = linked_docs.get('transactions')
    person_doc = linked_docs.get('person_ledger')
    dasti_doc = linked_docs.get('dasti_ledger')

    if person_doc:
        current_account_type, current_primary_id = 'person', person_doc[1].get('person_id', '')
    elif dasti_doc:
        current_account_type, current_primary_id = 'dasti', dasti_doc[1].get('dasti_person_id', '')
    else:
        current_account_type, current_primary_id = 'main', ''

    nature_map = {
        'expense': 'slip_in', 'batch_ledger_out': 'slip_in', 'settlement': 'slip_in',
        'dasti_out': 'advance', 'dasti_voucher_out': 'advance', 'advance': 'advance',
        'income': 'receive_cash', 'dasti_voucher_in': 'receive_cash',
    }
    ref_type = txn_doc[1].get('type', '') if txn_doc else entry.get('type', '')
    current_nature = nature_map.get(ref_type, 'slip_in')

    has_link = bool(link_id)

    persons = [{'id': d.id, **d.to_dict()} for d in db.collection('persons').where('user_id', '==', firm_id).stream()]
    persons.sort(key=lambda x: x.get('name', ''))
    dasti_persons = [{'id': d.id, **d.to_dict()} for d in db.collection('dasti_persons').where('user_id', '==', firm_id).stream()]
    dasti_persons.sort(key=lambda x: x.get('name', ''))
    approvers = [{'id': d.id, **d.to_dict()} for d in db.collection('users').where('firm_id', '==', firm_id).stream()]
    approvers.sort(key=lambda x: x.get('username', ''))
    approver_names = [u.get('username', '') for u in approvers]

    if request.method == 'POST':
        cat_raw = request.form.get('category', entry.get('category', ''))
        custom_cat = request.form.get('custom_category', '').strip()
        category = custom_cat if cat_raw == 'Other' and custom_cat else cat_raw
        existing_cats = get_categories(firm_id)
        if category and category not in existing_cats:
            db.collection('categories').add({'firm_id': firm_id, 'name': category})

        date_val = request.form['date']
        time_val = request.form['time']
        mode = request.form['payment_mode']
        amount = float(request.form['amount'])
        desc = request.form.get('description', entry.get('description', '')).strip()

        new_status = request.form.get('status', entry.get('status'))
        approver_select = request.form.get('approved_by_select', '')
        approver_custom = request.form.get('approved_by_custom', '').strip()
        if 'status' in request.form:
            if approver_select == 'other' and approver_custom:
                chosen_approver = approver_custom
            elif approver_select and approver_select != 'other':
                chosen_approver = approver_select
            else:
                chosen_approver = entry.get('approved_by', '')
            if new_status == 'approved':
                approved_by = chosen_approver or session['username']
            else:
                approved_by = ''
        else:
            new_status = entry.get('status')
            approved_by = entry.get('approved_by', '')

        if has_link:
            new_account_raw = request.form.get('primary_account', 'main')
            new_account_name = request.form.get('new_account_name', '').strip()
            new_nature = request.form.get('txn_nature', current_nature)

            new_account_type, new_primary_id, new_person_name = 'main', None, ''
            if new_account_raw == 'new_dasti':
                ref = db.collection('dasti_persons').document()
                ref.set({'user_id': firm_id, 'name': new_account_name})
                new_primary_id, new_account_type, new_person_name = ref.id, 'dasti', new_account_name
            elif new_account_raw == 'new_person':
                ref = db.collection('persons').document()
                ref.set({'user_id': firm_id, 'name': new_account_name})
                new_primary_id, new_account_type, new_person_name = ref.id, 'person', new_account_name
            elif new_account_raw.startswith('person_'):
                new_primary_id = new_account_raw.split('_', 1)[1]
                new_account_type = 'person'
                pd = db.collection('persons').document(new_primary_id).get().to_dict()
                new_person_name = pd.get('name', '') if pd else ''
            elif new_account_raw.startswith('dasti_'):
                new_primary_id = new_account_raw.split('_', 1)[1]
                new_account_type = 'dasti'
                dd = db.collection('dasti_persons').document(new_primary_id).get().to_dict()
                new_person_name = dd.get('name', '') if dd else ''

            base_txn = {
                'user_id': firm_id, 'date': date_val, 'time': time_val, 'payment_mode': mode,
                'category': category, 'amount': amount, 'link_id': link_id,
                'status': new_status, 'approved_by': approved_by,
                'deleted': entry.get('deleted', 0), 'created_at': entry.get('created_at', time.time())
            }

            for coll, (did, _d) in linked_docs.items():
                db.collection(coll).document(did).delete()

            if new_account_type == 'main':
                db_type = 'income' if new_nature == 'receive_cash' else 'expense'
                db.collection('transactions').add({**base_txn, 'description': desc, 'type': db_type})
            elif new_account_type == 'person':
                if new_nature == 'slip_in':
                    db.collection('person_ledger').add({**base_txn, 'person_id': new_primary_id, 'description': desc, 'type': 'settlement'})
                    db.collection('transactions').add({**base_txn, 'description': f"Slip ({new_person_name}): {desc}", 'type': 'batch_ledger_out'})
                elif new_nature == 'advance':
                    db.collection('person_ledger').add({**base_txn, 'person_id': new_primary_id, 'description': desc, 'type': 'advance'})
                    db.collection('transactions').add({**base_txn, 'description': f"Transfer Out ({new_person_name}): {desc}", 'type': 'dasti_out'})
                elif new_nature == 'receive_cash':
                    db.collection('person_ledger').add({**base_txn, 'person_id': new_primary_id, 'description': desc, 'type': 'settlement'})
                    db.collection('transactions').add({**base_txn, 'description': f"Transfer In ({new_person_name}): {desc}", 'type': 'income'})
            elif new_account_type == 'dasti':
                if new_nature == 'slip_in':
                    db.collection('dasti_ledger').add({**base_txn, 'dasti_person_id': new_primary_id, 'description': desc, 'type': 'settlement'})
                    db.collection('transactions').add({**base_txn, 'description': f"Dasti Slip ({new_person_name}): {desc}", 'type': 'batch_ledger_out'})
                elif new_nature == 'advance':
                    db.collection('dasti_ledger').add({**base_txn, 'dasti_person_id': new_primary_id, 'description': desc, 'type': 'advance'})
                    db.collection('transactions').add({**base_txn, 'description': f"Dasti Out ({new_person_name}): {desc}", 'type': 'dasti_voucher_out'})
                elif new_nature == 'receive_cash':
                    db.collection('dasti_ledger').add({**base_txn, 'dasti_person_id': new_primary_id, 'description': desc, 'type': 'settlement'})
                    db.collection('transactions').add({**base_txn, 'description': f"Dasti In ({new_person_name}): {desc}", 'type': 'dasti_voucher_in'})
        else:
            update_data = {
                'date': date_val, 'time': time_val, 'payment_mode': mode, 'category': category,
                'amount': amount, 'status': new_status, 'approved_by': approved_by,
                'description': desc, 'type': request.form.get('type', entry.get('type'))
            }
            doc_ref.update(update_data)

        return redirect(request.referrer or url_for('index'))

    cats = get_categories(firm_id)
    return render_template_string(EDIT_TEMPLATE, entry=entry, table_name=table_name, categories=cats,
                                   persons=persons, dasti_persons=dasti_persons, approvers=approvers,
                                   approver_names=approver_names, has_link=has_link,
                                   current_account_type=current_account_type, current_primary_id=current_primary_id,
                                   current_nature=current_nature, username=session['username'])

@app.route('/manage_users')
def manage_users():
    if 'user_id' not in session or session.get('role') != 'superadmin': return redirect(url_for('index'))
    users = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('users').where('firm_id', '==', session['firm_id']).stream()]
    return render_template_string(USERS_TEMPLATE, users=users, username=session['username'], active_page='users')

@app.route('/edit_user/<string:uid>', methods=['GET', 'POST'])
def edit_user(uid):
    if 'user_id' not in session or session.get('role') != 'superadmin': return redirect(url_for('index'))
    
    doc_ref = db.collection('users').document(uid)
    user_data = doc_ref.get().to_dict()
    if not user_data or user_data.get('firm_id') != session['firm_id']: return redirect(url_for('manage_users'))
    
    if request.method == 'POST':
        update_data = {
            'username': request.form['username'],
            'role': request.form['role'],
            'can_approve': int(request.form.get('can_approve', 0)),
            'can_edit': int(request.form.get('can_edit', 0)),
            'can_view_reports': int(request.form.get('can_view_reports', 0)),
            'can_view_trash': int(request.form.get('can_view_trash', 0))
        }
        new_pw = request.form.get('password', '').strip()
        if new_pw: update_data['password'] = generate_password_hash(new_pw)
        
        doc_ref.update(update_data)
        return redirect(url_for('manage_users'))
        
    edit_user_obj = {'id': uid, **user_data}
    return render_template_string(EDIT_USER_TEMPLATE, edit_user=edit_user_obj, username=session['username'], active_page='users')

@app.route('/add_user', methods=['POST'])
def add_user():
    if 'user_id' not in session or session.get('role') != 'superadmin': return redirect(url_for('index'))
    db.collection('users').add({
        'username': request.form['new_username'],
        'password': generate_password_hash(request.form['new_password']),
        'firm_name': session['firm_name'],
        'firm_id': session['firm_id'],
        'role': request.form['role'],
        'can_approve': int(request.form.get('can_approve', 0)),
        'can_edit': int(request.form.get('can_edit', 0)),
        'can_view_reports': int(request.form.get('can_view_reports', 0)),
        'can_view_trash': int(request.form.get('can_view_trash', 0))
    })
    return redirect(url_for('manage_users'))

@app.route('/approvals')
def approvals():
    if 'user_id' not in session or session.get('can_approve') != 1: return redirect(url_for('index'))
    pending = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('transactions').where('user_id', '==', session['firm_id']).where('status', '==', 'pending').where('deleted', '==', 0).stream()]
    pending.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=True)
    return render_template_string(APPROVALS_TEMPLATE, pending=pending, username=session['username'], active_page='approvals')

@app.route('/approve_voucher/<string:link_id>')
def approve_voucher(link_id):
    if 'user_id' not in session or session.get('can_approve') != 1: return redirect(url_for('index'))
    for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
        docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', session['firm_id']).stream()
        for d in docs: d.reference.update({'status': 'approved', 'approved_by': session['username']})
    return redirect(request.referrer or url_for('approvals'))

@app.route('/reject_voucher/<string:link_id>')
def reject_voucher(link_id):
    if 'user_id' not in session or session.get('can_approve') != 1: return redirect(url_for('index'))
    for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
        docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', session['firm_id']).stream()
        for d in docs: d.reference.update({'deleted': 1})
    return redirect(request.referrer or url_for('approvals'))

@app.route('/bulk_approve', methods=['POST'])
def bulk_approve():
    if 'user_id' not in session or session.get('can_approve') != 1: return redirect(url_for('index'))
    start = request.form.get('start_date', '')
    end = request.form.get('end_date', '')
    
    for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
        docs = db.collection(collection).where('user_id', '==', session['firm_id']).where('status', '==', 'pending').where('deleted', '==', 0).stream()
        for d in docs:
            doc_data = d.to_dict()
            date_val = doc_data.get('date', '')
            if start <= date_val <= end:
                d.reference.update({'status': 'approved', 'approved_by': session['username']})
                
    return redirect(url_for('approvals'))

@app.route('/add_express', methods=['POST'])
def add_express():
    if 'user_id' not in session: return redirect(url_for('login'))
    txn_status = 'approved' if session.get('can_approve') == 1 else 'pending'
    approver = session['username'] if txn_status == 'approved' else ''
    
    db.collection('transactions').add({
        'user_id': session['firm_id'],
        'date': request.form['date'],
        'time': request.form['time'],
        'payment_mode': 'Cash',
        'category': 'General',
        'description': request.form['description'],
        'type': request.form['type'],
        'amount': float(request.form['amount']),
        'link_id': uuid.uuid4().hex[:12],
        'status': txn_status,
        'approved_by': approver,
        'deleted': 0,
        'created_at': time.time()
    })
    return redirect(request.referrer or url_for('index'))

@app.route('/add_transfer', methods=['POST'])
def add_transfer():
    if 'user_id' not in session: return redirect(url_for('login'))
    firm_id = session['firm_id']
    date_val, time_val, direction, person_id = request.form['date'], request.form['time'], request.form['direction'], request.form['person_id']
    desc, amt = request.form['description'].strip(), float(request.form['amount'])
    
    txn_status = 'approved' if session.get('can_approve') == 1 else 'pending'
    approver = session['username'] if txn_status == 'approved' else ''
    
    person_doc = db.collection('persons').document(person_id).get()
    if not person_doc.exists: return redirect(request.referrer)
    person_name = person_doc.to_dict().get('name', '')
    link_id = uuid.uuid4().hex[:12]
    
    if direction == 'main_to_person':
        db.collection('transactions').add({'user_id': firm_id, 'date': date_val, 'time': time_val, 'payment_mode': 'Cash', 'category': 'General', 'description': f"Transfer to {person_name}: {desc}", 'type': 'dasti_out', 'amount': amt, 'link_id': link_id, 'status': txn_status, 'approved_by': approver, 'deleted': 0, 'created_at': time.time()})
        db.collection('person_ledger').add({'user_id': firm_id, 'person_id': person_id, 'date': date_val, 'time': time_val, 'payment_mode': 'Cash', 'category': 'General', 'description': f"Rcvd from Main: {desc}", 'type': 'advance', 'amount': amt, 'link_id': link_id, 'status': txn_status, 'approved_by': approver, 'deleted': 0, 'created_at': time.time()})
    else:
        db.collection('person_ledger').add({'user_id': firm_id, 'person_id': person_id, 'date': date_val, 'time': time_val, 'payment_mode': 'Cash', 'category': 'General', 'description': f"Paid to Main: {desc}", 'type': 'settlement', 'amount': amt, 'link_id': link_id, 'status': txn_status, 'approved_by': approver, 'deleted': 0, 'created_at': time.time()})
        db.collection('transactions').add({'user_id': firm_id, 'date': date_val, 'time': time_val, 'payment_mode': 'Cash', 'category': 'General', 'description': f"Transfer from {person_name}: {desc}", 'type': 'income', 'amount': amt, 'link_id': link_id, 'status': txn_status, 'approved_by': approver, 'deleted': 0, 'created_at': time.time()})
                  
    return redirect(request.referrer or url_for('index'))

@app.route('/add_batch_unified', methods=['POST'])
def add_batch_unified():
    if 'user_id' not in session: return redirect(url_for('login'))
    firm_id = session['firm_id']
    date_val, time_val, mode, txn_nature = request.form['date'], request.form['time'], request.form['payment_mode'], request.form['txn_nature']
    primary_account_raw = request.form['primary_account']
    new_account_name = request.form.get('new_account_name', '').strip()
    
    cats, cust_cats, descs, amts = request.form.getlist('category[]'), request.form.getlist('custom_category[]'), request.form.getlist('description[]'), request.form.getlist('amount[]')
    
    txn_status = 'approved' if session.get('can_approve') == 1 else 'pending'
    approver = session['username'] if txn_status == 'approved' else ''
    
    existing_cats = get_categories(firm_id)
    account_type = 'main'
    primary_id = None
    person_name = ''
    
    if primary_account_raw == 'new_dasti':
        new_ref = db.collection('dasti_persons').document()
        new_ref.set({'user_id': firm_id, 'name': new_account_name})
        primary_id = new_ref.id
        account_type, person_name = 'dasti', new_account_name
    elif primary_account_raw == 'new_person':
        new_ref = db.collection('persons').document()
        new_ref.set({'user_id': firm_id, 'name': new_account_name})
        primary_id = new_ref.id
        account_type, person_name = 'person', new_account_name
    elif primary_account_raw.startswith('person_'):
        primary_id = primary_account_raw.split('_')[1]
        account_type = 'person'
        person_name = db.collection('persons').document(primary_id).get().to_dict().get('name', '')
    elif primary_account_raw.startswith('dasti_'):
        primary_id = primary_account_raw.split('_')[1]
        account_type = 'dasti'
        person_name = db.collection('dasti_persons').document(primary_id).get().to_dict().get('name', '')
        
    for i in range(len(descs)):
        if amts[i].strip() and float(amts[i]) >= 0:
            amt, desc = float(amts[i]), descs[i].strip()
            cat = cust_cats[i].strip() if cats[i] == 'Other' and cust_cats[i].strip() else cats[i]
            if cat not in existing_cats:
                db.collection('categories').add({'firm_id': firm_id, 'name': cat})
                existing_cats.append(cat)
                
            link_id = uuid.uuid4().hex[:12]
            
            base_txn = {'user_id': firm_id, 'date': date_val, 'time': time_val, 'payment_mode': mode, 'category': cat, 'amount': amt, 'link_id': link_id, 'status': txn_status, 'approved_by': approver, 'deleted': 0, 'created_at': time.time()}

            if account_type == 'main':
                db_type = 'income' if txn_nature == 'receive_cash' else 'expense'
                db.collection('transactions').add({**base_txn, 'description': desc, 'type': db_type})
                
            elif account_type == 'person':
                if txn_nature == 'slip_in':
                    db.collection('person_ledger').add({**base_txn, 'person_id': primary_id, 'description': desc, 'type': 'settlement'})
                    db.collection('transactions').add({**base_txn, 'description': f"Slip ({person_name}): {desc}", 'type': 'batch_ledger_out'})
                elif txn_nature == 'advance':
                    db.collection('person_ledger').add({**base_txn, 'person_id': primary_id, 'description': desc, 'type': 'advance'})
                    db.collection('transactions').add({**base_txn, 'description': f"Transfer Out ({person_name}): {desc}", 'type': 'dasti_out'})
                elif txn_nature == 'receive_cash':
                    db.collection('person_ledger').add({**base_txn, 'person_id': primary_id, 'description': desc, 'type': 'settlement'})
                    db.collection('transactions').add({**base_txn, 'description': f"Transfer In ({person_name}): {desc}", 'type': 'income'})
                    
            elif account_type == 'dasti':
                if txn_nature == 'slip_in':
                    db.collection('dasti_ledger').add({**base_txn, 'dasti_person_id': primary_id, 'description': desc, 'type': 'settlement'})
                    db.collection('transactions').add({**base_txn, 'description': f"Dasti Slip ({person_name}): {desc}", 'type': 'batch_ledger_out'})
                elif txn_nature == 'advance':
                    db.collection('dasti_ledger').add({**base_txn, 'dasti_person_id': primary_id, 'description': desc, 'type': 'advance'})
                    db.collection('transactions').add({**base_txn, 'description': f"Dasti Out ({person_name}): {desc}", 'type': 'dasti_voucher_out'})
                elif txn_nature == 'receive_cash':
                    db.collection('dasti_ledger').add({**base_txn, 'dasti_person_id': primary_id, 'description': desc, 'type': 'settlement'})
                    db.collection('transactions').add({**base_txn, 'description': f"Dasti In ({person_name}): {desc}", 'type': 'dasti_voucher_in'})
                    
    return redirect(request.referrer or url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not has_users(): return redirect(url_for('register'))
    if request.method == 'POST':
        users_stream = db.collection('users').where('username', '==', request.form['username']).stream()
        user_doc = next(users_stream, None)
        
        if user_doc:
            user = user_doc.to_dict()
            if check_password_hash(user['password'], request.form['password']):
                session['user_id'] = user_doc.id
                session['username'] = user['username']
                session['firm_name'] = user['firm_name']
                session['firm_id'] = user.get('firm_id', user_doc.id)
                session['role'] = user.get('role', 'superadmin')
                
                # Apply granular RBAC rights to the session
                session['can_approve'] = user.get('can_approve', 0)
                session['can_edit'] = user.get('can_edit', 0)
                session['can_view_reports'] = user.get('can_view_reports', 0)
                session['can_view_trash'] = user.get('can_view_trash', 0)
                
                # Superadmin override
                if session['role'] == 'superadmin':
                    session['can_approve'] = session['can_edit'] = session['can_view_reports'] = session['can_view_trash'] = 1
                    
                return redirect(url_for('index'))
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if has_users(): return "Setup complete. Ask the Superadmin to create an account for you.", 403
    if request.method == 'POST':
        new_user_ref = db.collection('users').document()
        user_id = new_user_ref.id
        
        new_user_ref.set({
            'username': request.form['username'],
            'password': generate_password_hash(request.form['password']),
            'firm_name': request.form['firm_name'],
            'firm_id': user_id,
            'role': 'superadmin',
            'can_approve': 1,
            'can_edit': 1,
            'can_view_reports': 1,
            'can_view_trash': 1
        })
        
        session['user_id'] = user_id
        session['firm_id'] = user_id
        session['username'] = request.form['username']
        session['firm_name'] = request.form['firm_name']
        session['role'] = 'superadmin'
        session['can_approve'] = 1
        session['can_edit'] = 1
        session['can_view_reports'] = 1
        session['can_view_trash'] = 1
        
        opening_balance = float(request.form.get('opening_balance', 0))
        if opening_balance > 0:
            now = datetime.now()
            db.collection('transactions').add({
                'user_id': user_id,
                'date': now.strftime('%Y-%m-%d'),
                'time': now.strftime('%H:%M'),
                'payment_mode': 'Cash',
                'category': 'General',
                'description': 'Opening Balance',
                'type': 'income',
                'amount': opening_balance,
                'link_id': uuid.uuid4().hex[:12],
                'status': 'approved',
                'approved_by': session['username'],
                'deleted': 0,
                'created_at': time.time()
            })
            
        return redirect(url_for('index'))
    return render_template_string(REGISTER_TEMPLATE)

@app.route('/download_cash_json')
def download_cash_json():
    if 'user_id' not in session or session.get('role') != 'superadmin': return redirect(url_for('index'))
    
    data = {
        "users": [dict(doc.to_dict()) for doc in db.collection('users').stream()],
        "categories": [dict(doc.to_dict()) for doc in db.collection('categories').stream()],
        "persons": [dict(doc.to_dict()) for doc in db.collection('persons').stream()],
        "dasti_persons": [dict(doc.to_dict()) for doc in db.collection('dasti_persons').stream()],
        "transactions": [dict(doc.to_dict()) for doc in db.collection('transactions').stream()],
        "person_ledger": [dict(doc.to_dict()) for doc in db.collection('person_ledger').stream()],
        "dasti_ledger": [dict(doc.to_dict()) for doc in db.collection('dasti_ledger').stream()]
    }
    return Response(json.dumps(data, indent=4), mimetype='application/json', headers={"Content-Disposition": "attachment; filename=cash.json"})

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

if __name__ == '__main__':
    # No local server startup for Vercel deployment
    pass
