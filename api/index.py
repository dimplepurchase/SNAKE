import os
import json
from flask import Flask, render_template_string, request, redirect, url_for, session, Response
from datetime import datetime, timedelta, timezone
import time, uuid, csv
from io import StringIO

import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.secret_key = 'cashbook_secure_secret_key_12345'

# --- IST TIMEZONE SETUP ---
IST = timezone(timedelta(hours=5, minutes=30))

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

# --- GLOBAL SETTINGS HELPER ---
def get_global_settings():
    try:
        doc = db.collection('settings').document('global_login').get()
        if doc.exists:
            return doc.to_dict()
    except:
        pass
    return {
        'game_enabled': 1,
        'blocks_to_eat': 4,
        'unlock_corner': 'br', 
        'game_speed': 0,
        'app_disabled': False,
        'require_delete_confirm': True,
        'balance_display_mode': 'both',
        'receipt_display_mode': 'strict',
        'edit_action_mode': 'button',
        'report_flag_mode': 'both',
        'report_pdf_format': 'standard',
        'dashboard_sort_order': 'desc',
        'dashboard_ledger_visibility': 'main_only'   # <-- ADD THIS LINE
    }

# --- KILL SWITCH INTERCEPTOR ---
@app.before_request
def check_lockdown():
    if request.endpoint not in ['login', 'demo_game', 'static', 'register']:
        settings = get_global_settings()
        if settings.get('app_disabled', False):
            session.clear()
            return redirect(url_for('login'))

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
    .btn-warning { background-color: var(--warning); color: #fff; } .btn-warning:hover { background-color: #d97706; }
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
    .badge-pending { background-color: #fef08a; color: #92400e; border: 1px solid #fde047; }
    .badge-mode { background-color: #e0e7ff; color: #3730a3; font-size: 0.8em; margin-bottom: 4px; border: 1px solid #c7d2fe; }
    .flex-row { display: flex; gap: 15px; flex-wrap: wrap; align-items: flex-end; }
    .flex-1 { flex: 1; }
    .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; margin-bottom: 25px; }
    .stat-card { background: #fff; padding: 20px; border-radius: 12px; border: 1px solid var(--border); text-align: center; transition: 0.2s; }
    .stat-card:hover.clickable { transform: translateY(-2px); box-shadow: 0 4px 10px rgba(0,0,0,0.1); border-color: var(--primary); }
    .stat-card h4 { color: #6b7280; margin: 0 0 8px 0; font-size: 0.85em; text-transform: uppercase; }
    .stat-card .value { font-size: 1.6em; font-weight: 700; }
    .pagination-controls { display: flex; justify-content: space-between; align-items: center; padding: 15px; background: #f8fafc; border-top: 1px solid var(--border); }
    
    #splash-screen { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(135deg, #4f46e5, #3b82f6); z-index: 9999; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; transition: opacity 0.5s ease; }
    .splash-firm { font-size: 3.5em; font-weight: 700; margin-bottom: 10px; animation: popIn 0.8s ease; text-transform: uppercase; letter-spacing: 2px;}
    .splash-user { font-size: 1.5em; font-weight: 300; animation: popIn 1.2s ease; }
    @keyframes popIn { 0% { opacity: 0; transform: translateY(20px); } 100% { opacity: 1; transform: translateY(0); } }
    
    @media print { .no-print, .navbar, .card form, button, select, .pagination-controls { display: none !important; } body { background: white; color: black; } .card { box-shadow: none; border: none; margin: 0; padding: 0; } table tr { display: table-row !important; } }
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
        document.querySelectorAll('.auto-date').forEach(el => { if(!el.value) el.value = dateString; });
        document.querySelectorAll('.auto-time').forEach(el => { if(!el.value) el.value = timeString; });
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
        if(!newAcc) return;
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
    
    {% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}
    <a href="/flag_entries" class="{% if active_page == 'flags' %}active{% endif %}" style="background: rgba(245, 158, 11, 0.2); color: #d97706;">🚩 Flags</a>
    <a href="/bulk_edit_date" class="{% if active_page == 'bulk_date' %}active{% endif %}" style="background: rgba(139, 92, 246, 0.2); color: #6d28d9;">📅 Bulk Date</a>
    <a href="/logs" class="{% if active_page == 'logs' %}active{% endif %}" style="background: rgba(99, 102, 241, 0.2); color: #4338ca;">📝 Logs</a>
    {% endif %}

    {% if session.get('can_view_trash') == 1 or session.get('role') == 'superadmin' %}
    <a href="/trash" class="{% if active_page == 'trash' %}active{% endif %}" style="background: rgba(239, 68, 68, 0.2); color: #991b1b;">🗑️ Trash</a>
    {% endif %}
    
    {% if session.get('role') == 'superadmin' %}
        <a href="/manage_users" class="{% if active_page == 'users' %}active{% endif %}" style="background: #8b5cf6;">⚙️ Users</a>
    {% endif %}
    
    <span style="color: rgba(255,255,255,0.9); margin-left: auto; font-size: 0.9em; font-weight: 500;">User: <strong>{{ username }}</strong> <small>({{ session.get('role')|title }})</small></span>
    <a href="/logout" class="logout" style="padding: 6px 12px; font-size:0.9em;" onclick="sessionStorage.removeItem('splashShown');">Logout</a>
</div>
<script>
    let idleTime = 0;
    const maxIdleMinutes = parseInt("{{ session.get('idle_timeout', 15) }}");
    if (maxIdleMinutes > 0) {
        const maxIdleSeconds = maxIdleMinutes * 60;
        function resetTimer() { idleTime = 0; }
        window.onload = resetTimer;
        window.onmousemove = resetTimer;
        window.onkeypress = resetTimer;
        window.ontouchstart = resetTimer;
        setInterval(() => {
            idleTime++;
            if (idleTime >= maxIdleSeconds) {
                window.location.href = '/logout';
            }
        }, 1000);
    }
</script>'''

LOGS_TEMPLATE = '''<!DOCTYPE html><html><head><title>Edit Logs</title>''' + BASE_STYLE + '''</head><body><div class="container">''' + NAVBAR_HTML + '''<div class="card" style="padding: 0;"><div style="padding: 15px 20px; background: #f8fafc; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;"><h3 style="margin: 0; font-size: 1.2em;">📝 Edit Logs {% if link_id_filter %}<span style="color:var(--primary);">(Filtered by Voucher)</span> <a href="/logs" class="btn btn-sm btn-outline" style="margin-left:10px;">❌ Clear Filter</a>{% endif %}</h3></div><table style="width: 100%; border: none;"><tr><th style="padding-left: 20px;">Date & Time</th><th>Edited By</th><th>Changes Made</th><th>Voucher Context</th><th style="text-align: center;">Action</th></tr>{% for log in logs %}<tr><td style="padding-left: 20px;"><span style="font-weight: 500;">{{ log.date_formatted }}</span></td><td><span class="badge badge-mode">{{ log.edited_by }}</span></td><td style="color: var(--danger); font-weight: 500; font-size:0.9em;">{{ log.changes }}</td><td style="font-size: 0.85em; color: #4b5563;">{{ log.details }}</td><td style="text-align: center;">{% if log.link_id and log.link_id != 'bulk_edit' %}<div style="display:flex; gap:5px; justify-content:center;"><a href="/edit_by_link/{{ log.link_id }}" class="btn btn-sm" style="background:#f59e0b;color:white;" title="Edit Voucher">✏️ Edit</a><a href="/logs?link_id={{ log.link_id }}" class="btn btn-sm btn-outline" title="Show only this voucher's history">🔍 History</a></div>{% else %}<span style="color:#9ca3af; font-size: 0.8em;">N/A</span>{% endif %}{% if session.get('can_delete_logs') == 1 or session.get('role') == 'superadmin' %}<div style="margin-top:5px;"><a href="/delete_log/{{ log.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Delete this log entry forever?');">🗑️ Delete Log</a></div>{% endif %}</td></tr>{% else %}<tr><td colspan="5" style="text-align:center; color:#9ca3af; padding: 40px;">No edit logs found.</td></tr>{% endfor %}</table></div></div></body></html>'''

FLAGS_TEMPLATE = '''<!DOCTYPE html><html><head><title>Flag Entries</title>''' + BASE_STYLE + '''</head><body><div class="container">''' + NAVBAR_HTML + '''<div class="card"><h3 style="margin-top: 0; color: var(--primary);">🚩 Search & Flag/Unflag Entries</h3><form action="/flag_entries" method="POST" style="display: flex; gap: 15px; align-items: flex-end; flex-wrap: wrap;"><input type="hidden" name="action" value="search"><div class="form-group flex-1" style="min-width: 150px;"><label>From Date</label><input type="date" name="start_date" value="{{ start_date }}" required></div><div class="form-group flex-1" style="min-width: 150px;"><label>To Date</label><input type="date" name="end_date" value="{{ end_date }}" required></div><div class="form-group flex-1" style="min-width: 200px;"><label>Filter by Flag Status</label><select name="flag_filter" required><option value="unflagged" {% if flag_filter == 'unflagged' %}selected{% endif %}>Unflagged Entries Only</option><option value="flagged" {% if flag_filter == 'flagged' %}selected{% endif %}>Flagged Entries Only 🚩</option><option value="all" {% if flag_filter == 'all' %}selected{% endif %}>All Entries</option></select></div><button class="btn" style="background:indigo; height: 45px; padding: 10px 25px;" type="submit">🔍 Search Entries</button></form></div>{% if has_searched %}<div class="card" style="padding: 0;"><form action="/flag_entries" method="POST" onsubmit="return confirm('Process Flags for selected entries?');"><input type="hidden" name="action" value="process_flags"><div style="padding: 15px 20px; background: #fffbeb; border-bottom: 1px solid var(--border); display: flex; gap: 10px; align-items: center;"><button type="submit" name="flag_action" value="1" class="btn btn-sm" style="background:orange; color:white;">🚩 Mark Selected as Flagged</button><button type="submit" name="flag_action" value="0" class="btn btn-sm" style="background:slategray; color:white;">🏳️ Remove Flag from Selected</button></div><table style="width: 100%; border: none;"><tr><th style="padding-left: 20px; width: 40px;"><input type="checkbox" onclick="let cb = document.getElementsByName('selected_links'); for(let i=0;i<cb.length;i++) cb[i].checked = this.checked;" style="width:16px; height:16px; cursor:pointer;"></th><th>Date & Time</th><th>Category / Detail</th><th style="text-align: right;">Amount</th></tr>{% for t in results %}<tr><td style="padding-left: 20px;"><input type="checkbox" name="selected_links" value="{{ t.link_id }}" style="width:16px; height:16px; cursor:pointer;"></td><td><span style="font-weight: 500;">{{ t.date }}</span><br><span style="font-size: 0.85em; color: #6b7280;">{{ t.time }}</span></td><td><span class="badge badge-mode">{{ t.category }}</span> {% if t.is_flagged == 1 %}<span style="color:orange;">🚩</span>{% endif %}<br><span style="white-space: pre-wrap;">{{ t.description }}</span></td><td style="text-align: right;">{% if t.type in ['expense', 'dasti_out', 'batch_ledger_out', 'dasti_voucher_out', 'advance'] %}<span style="color:red; font-weight:bold;">- ₹{{ "{:,.2f}".format(t.amount) }}</span>{% else %}<span style="color:green; font-weight:bold;">+ ₹{{ "{:,.2f}".format(t.amount) }}</span>{% endif %}</td></tr>{% else %}<tr><td colspan="4" style="text-align:center; color:#9ca3af; padding: 40px;">No entries found.</td></tr>{% endfor %}</table></form></div>{% endif %}</div></body></html>'''

LOGIN_TEMPLATE = '''<!DOCTYPE html><html><head><title>System Gateway</title><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"><link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet"><style>body { background-color: #111; color: #0f0; font-family: monospace; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; overflow: hidden; flex-direction: column; transition: background 0.5s ease; touch-action: none; }.hud { display: flex; justify-content: space-between; align-items: center; width: 400px; max-width: 95vw; margin-bottom: 10px; font-size: 1.2em; font-weight: bold; }canvas { border: 2px solid #333; background-color: #000; box-shadow: 0 0 15px rgba(0, 255, 0, 0.2); max-width: 95vw; max-height: 50vh; }#login-container { display: none; position: absolute; z-index: 10; background: #ffffff; padding: 30px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); font-family: 'Poppins', sans-serif; color: #333; width: 350px; max-width: 90vw; }h2 { color: #4f46e5; margin-top: 0; text-align: center; }.form-group { margin-bottom: 15px; display: flex; flex-direction: column; }label { font-weight: 600; margin-bottom: 5px; font-size: 0.85em; color: #4b5563; }input { padding: 10px; border: 1px solid #ccc; border-radius: 8px; font-size: 1em; }button { background: #4f46e5; color: white; border: none; padding: 10px; font-weight: bold; border-radius: 8px; cursor: pointer; margin-top: 10px; width: 100%; font-size: 1em;}button:hover { background: #4338ca; }.controls { display: none; grid-template-columns: 60px 60px 60px; grid-template-rows: 60px 60px; gap: 10px; margin-top: 20px; justify-content: center; }.btn-ctrl { background: rgba(0, 255, 0, 0.2); border: 2px solid #0f0; color: #0f0; border-radius: 8px; font-size: 1.5em; display: flex; justify-content: center; align-items: center; user-select: none; }.btn-ctrl:active { background: rgba(0, 255, 0, 0.5); }.btn-up { grid-column: 2; grid-row: 1; }.btn-left { grid-column: 1; grid-row: 2; }.btn-down { grid-column: 2; grid-row: 2; }.btn-right { grid-column: 3; grid-row: 2; }@media (max-width: 768px) { .controls { display: grid; } }#game-over-msg { display: none; color: red; text-align: center; margin-top: 20px; font-size: 1.2em; font-family: 'Poppins', sans-serif; font-weight: bold; }{% if settings.game_enabled == 0 and not is_demo %}#game-wrapper { display: none !important; } #login-container { display: block !important; position: static; margin: auto; }body { background-color: #f8fafc; }{% endif %}</style></head><body><div id="game-wrapper"><div class="hud"><div id="timeDisplay">Time: 0s</div><div id="scoreDisplay">Score: 0 / {{ settings.blocks_to_eat }}</div></div><canvas id="gameCanvas" width="400" height="400"></canvas><div id="game-over-msg">Game Over.<br>Refresh page to restart.</div><div class="controls"><div class="btn-ctrl btn-up" id="btnUp">▲</div><div class="btn-ctrl btn-left" id="btnLeft">◀</div><div class="btn-ctrl btn-down" id="btnDown">▼</div><div class="btn-ctrl btn-right" id="btnRight">▶</div></div></div><div id="login-container"><h2>System Access</h2><form action="/login" method="POST"><div class="form-group"><label>Username</label><input type="text" name="username" required></div><div class="form-group"><label>Password</label><input type="password" name="password" required></div><button type="submit">Secure Login</button></form></div><script>{% if settings.game_enabled != 0 or is_demo %}const canvas = document.getElementById('gameCanvas');const ctx = canvas.getContext('2d');const grid = 20; let speedMod = parseInt("{{ settings.game_speed }}") || 0; let delayMs = 100 - (speedMod * 10); if (delayMs < 20) delayMs = 20; if (delayMs > 500) delayMs = 500; let gameTimer; let snake = { x: 160, y: 160, dx: grid, dy: 0, cells: [], maxCells: 4 }; let apple = { x: 320, y: 320 }; let score = 0; let targetScore = parseInt("{{ settings.blocks_to_eat }}") || 4; let startTime = Math.floor(Date.now() / 1000); let isGameOver = false; let loginUnlocked = false; let targetX = 0, targetY = 0; const targetCorner = "{{ settings.unlock_corner }}"; if(targetCorner === 'br') { targetX = canvas.width - grid; targetY = canvas.height - grid; } else if(targetCorner === 'bl') { targetX = 0; targetY = canvas.height - grid; } else if(targetCorner === 'tr') { targetX = canvas.width - grid; targetY = 0; } else if(targetCorner === 'tl') { targetX = 0; targetY = 0; } function getRandomInt(min, max) { return Math.floor(Math.random() * (max - min)) + min; } function triggerGameOver() { isGameOver = true; clearTimeout(gameTimer); document.getElementById('game-over-msg').style.display = 'block'; } function loop() { if (isGameOver) return; gameTimer = setTimeout(loop, delayMs); ctx.clearRect(0, 0, canvas.width, canvas.height); document.getElementById('timeDisplay').innerText = 'Time: ' + (Math.floor(Date.now() / 1000) - startTime) + 's'; snake.x += snake.dx; snake.y += snake.dy; if (snake.x < 0) { snake.x = canvas.width - grid; } else if (snake.x >= canvas.width) { snake.x = 0; } if (snake.y < 0) { snake.y = canvas.height - grid; } else if (snake.y >= canvas.height) { snake.y = 0; } snake.cells.unshift({ x: snake.x, y: snake.y }); if (snake.cells.length > snake.maxCells) snake.cells.pop(); ctx.fillStyle = 'red'; ctx.fillRect(apple.x, apple.y, grid - 1, grid - 1); ctx.fillStyle = '#0f0'; snake.cells.forEach(function(cell, index) { ctx.fillRect(cell.x, cell.y, grid - 1, grid - 1); if (cell.x === apple.x && cell.y === apple.y) { snake.maxCells++; score++; document.getElementById('scoreDisplay').innerText = 'Score: ' + score + ' / ' + targetScore; if (score >= targetScore) { loginUnlocked = true; } apple.x = getRandomInt(0, 20) * grid; apple.y = getRandomInt(0, 20) * grid; } for (let i = index + 1; i < snake.cells.length; i++) { if (cell.x === snake.cells[i].x && cell.y === snake.cells[i].y) { triggerGameOver(); return; } } }); if (snake.x === targetX && snake.y === targetY) { if (loginUnlocked) { isGameOver = true; clearTimeout(gameTimer); document.getElementById('game-wrapper').style.display = 'none'; document.getElementById('login-container').style.display = 'block'; document.body.style.background = '#f8fafc'; } } } function setDir(dx, dy) { if(isGameOver) return; if (dx !== 0 && snake.dx === 0) { snake.dx = dx; snake.dy = dy; } else if (dy !== 0 && snake.dy === 0) { snake.dy = dy; snake.dx = dx; } } document.addEventListener('keydown', function(e) { if (e.which === 37) setDir(-grid, 0); else if (e.which === 38) setDir(0, -grid); else if (e.which === 39) setDir(grid, 0); else if (e.which === 40) setDir(0, grid); }); document.getElementById('btnUp').addEventListener('touchstart', (e) => { e.preventDefault(); setDir(0, -grid); }, {passive: false}); document.getElementById('btnDown').addEventListener('touchstart', (e) => { e.preventDefault(); setDir(0, grid); }, {passive: false}); document.getElementById('btnLeft').addEventListener('touchstart', (e) => { e.preventDefault(); setDir(-grid, 0); }, {passive: false}); document.getElementById('btnRight').addEventListener('touchstart', (e) => { e.preventDefault(); setDir(grid, 0); }, {passive: false}); document.getElementById('btnUp').addEventListener('mousedown', (e) => { e.preventDefault(); setDir(0, -grid); }); document.getElementById('btnDown').addEventListener('mousedown', (e) => { e.preventDefault(); setDir(0, grid); }); document.getElementById('btnLeft').addEventListener('mousedown', (e) => { e.preventDefault(); setDir(-grid, 0); }); document.getElementById('btnRight').addEventListener('mousedown', (e) => { e.preventDefault(); setDir(grid, 0); }); loop(); {% endif %}</script></body></html>'''

USERS_TEMPLATE = '''<!DOCTYPE html><html><head><title>Manage Users</title>''' + BASE_STYLE + '''</head><body><div class="container">''' + NAVBAR_HTML + '''{% if session.get('role') == 'superadmin' %}
<div class="card" style="margin-bottom: 20px; padding: 20px; background: #e0f2fe; border: 1px solid #38bdf8;">
    <h3 style="font-size: 1.2em; color: #0369a1; margin-top: 0;">🎮 Global Configuration & App Settings</h3>
    <form action="/update_settings" method="POST" style="display:flex; gap:15px; align-items: flex-end; flex-wrap:wrap;">
        <div class="form-group flex-1" style="min-width: 150px;"><label style="color:var(--danger);">🔴 App Lockdown (Kill Switch)</label><select name="app_disabled" required style="border-color:var(--danger); font-weight:bold;"><option value="0" {% if sys_settings.app_disabled == False %}selected{% endif %}>🟢 Active (Normal)</option><option value="1" {% if sys_settings.app_disabled == True %}selected{% endif %}>🔴 DISABLED (Lockdown)</option></select></div>
        <div class="form-group flex-1" style="min-width: 150px;"><label>Game Gateway?</label><select name="game_enabled" required style="border-color:#7dd3fc;"><option value="1" {% if sys_settings.game_enabled == 1 %}selected{% endif %}>✅ Enabled</option><option value="0" {% if sys_settings.game_enabled == 0 %}selected{% endif %}>❌ Disabled</option></select></div>
        <div class="form-group flex-1"><label>Blocks to Unlock</label><input type="number" name="blocks_to_eat" value="{{ sys_settings.blocks_to_eat }}" min="1" max="20" required></div>
        <div class="form-group flex-1"><label>Game Speed</label><input type="number" name="game_speed" value="{{ sys_settings.game_speed }}" min="-20" max="10" required></div>
        
        <div class="form-group flex-1" style="min-width: 200px;"><label>Balance Display Mode</label><select name="balance_display_mode" required><option value="both" {% if sys_settings.balance_display_mode == 'both' %}selected{% endif %}>Show Both Ledgers</option><option value="person_only" {% if sys_settings.balance_display_mode == 'person_only' %}selected{% endif %}>Person Only</option><option value="dasti_only" {% if sys_settings.balance_display_mode == 'dasti_only' %}selected{% endif %}>Dasti Only</option><option value="none" {% if sys_settings.balance_display_mode == 'none' %}selected{% endif %}>Hide All</option></select></div>
        <div class="form-group flex-1" style="min-width: 200px;"><label>Receipt Screen Mode</label><select name="receipt_display_mode" required><option value="strict" {% if sys_settings.receipt_display_mode == 'strict' %}selected{% endif %}>Pure Receipts Only</option><option value="all_positive" {% if sys_settings.receipt_display_mode == 'all_positive' %}selected{% endif %}>Show All Cash In (+)</option></select></div>
        <div class="form-group flex-1" style="min-width: 200px;"><label>Edit Action Mode</label><select name="edit_action_mode" required><option value="button" {% if sys_settings.edit_action_mode == 'button' %}selected{% endif %}>Visible Button</option><option value="tap" {% if sys_settings.edit_action_mode == 'tap' %}selected{% endif %}>Direct Tap</option></select></div>
        <div class="form-group flex-1" style="min-width: 200px;"><label>Report Flag Filter</label><select name="report_flag_mode" required><option value="both" {% if sys_settings.report_flag_mode == 'both' %}selected{% endif %}>Show All Entries</option><option value="flagged" {% if sys_settings.report_flag_mode == 'flagged' %}selected{% endif %}>Flagged Only</option><option value="unflagged" {% if sys_settings.report_flag_mode == 'unflagged' %}selected{% endif %}>Unflagged Only</option></select></div>
        <div class="form-group flex-1" style="min-width: 200px;"><label>Report PDF Format</label><select name="report_pdf_format" required><option value="standard" {% if sys_settings.report_pdf_format == 'standard' %}selected{% endif %}>Standard Detail</option><option value="summary_breakdown" {% if sys_settings.report_pdf_format == 'summary_breakdown' %}selected{% endif %}>Summary Breakdown</option></select></div>
        <div class="form-group flex-1" style="min-width: 200px;"><label>Dashboard Ledger Sort</label><select name="dashboard_sort_order" required style="border-color:#38bdf8; font-weight:bold;"><option value="desc" {% if sys_settings.dashboard_sort_order == 'desc' %}selected{% endif %}>Newest First (Desc) ⬇️</option><option value="asc" {% if sys_settings.dashboard_sort_order == 'asc' %}selected{% endif %}>Oldest First (Asc) ⬆️</option></select></div>
        <div class="form-group flex-1" style="min-width: 220px;"><label>Dashboard Receipts/Payments Show</label><select name="dashboard_ledger_visibility" required style="border-color:#38bdf8; font-weight:bold;"><option value="main_only" {% if sys_settings.dashboard_ledger_visibility == 'main_only' %}selected{% endif %}>🏢 Main Cash Book Only</option><option value="all" {% if sys_settings.dashboard_ledger_visibility == 'all' %}selected{% endif %}>🏢➕👥 Main + Person/Dasti Linked Entries</option></select></div>

        <button class="btn" type="submit" style="padding: 10px 25px; height: 45px; background:#0284c7; width: 100%;">💾 Save Global Settings</button>
    </form>
</div>

<div class="card" style="margin-bottom: 20px; padding: 20px; background: #fdf4ff; border: 1px solid #e879f9;">
    <h3 style="font-size: 1.2em; color: #a21caf; margin-top: 0;">🗄️ Database Maintenance (Re-Index)</h3>
    <p style="font-size: 0.9em; color: #701a75; margin-bottom: 15px;">If vouchers are appearing out of order after bulk date edits, use this tool to re-calculate their chronological index based on their assigned Date and Time.</p>
    <form action="/reindex_database" method="POST" onsubmit="return confirm('This will re-calculate the sorting index for ALL vouchers based on their dates. Proceed?');">
        <button class="btn" type="submit" style="background:#c026d3; padding: 10px 25px;">🔄 Re-Index All Vouchers by Date & Time</button>
    </form>
</div>
{% endif %}

<div class="card" style="margin-bottom: 20px; padding: 20px;"><h3 style="font-size: 1.2em;">👤 Create New Firm User</h3><form action="/add_user" method="POST" style="display:flex; gap:15px; align-items: flex-end; flex-wrap:wrap;"><div class="form-group flex-1"><label>Username</label><input type="text" name="new_username" required></div><div class="form-group flex-1"><label>Password</label><input type="password" name="new_password" required></div><div class="form-group flex-1"><label>Role</label><select name="role" required><option value="admin">Admin</option><option value="superadmin">Superadmin</option><option value="cashier">Cashier</option><option value="market">Market</option></select></div><div class="form-group flex-1"><label>Idle Auto-Logout (Mins)</label><input type="number" name="idle_timeout" value="15" min="1" required></div><div class="form-group" style="padding-bottom: 10px; display: flex; flex-direction: column; gap: 5px;"><label><input type="checkbox" name="can_approve" value="1"> Grant Apprv</label><label><input type="checkbox" name="can_edit" value="1"> Grant Edit/Del</label><label><input type="checkbox" name="can_express_cashout" value="1"> Grant Exp Cash-Out</label></div><div class="form-group" style="padding-bottom: 10px; display: flex; flex-direction: column; gap: 5px;"><label><input type="checkbox" name="can_view_reports" value="1"> Grant Reports</label><label><input type="checkbox" name="can_view_trash" value="1"> Grant Trash</label><label><input type="checkbox" name="can_delete_logs" value="1"> Grant Log Delete</label><label><input type="checkbox" name="can_view_ledger_details" value="1"> Grant Ledger Details View</label></div><button class="btn-success" type="submit" style="padding: 10px 25px; height: 45px;">Create User</button></form></div><div class="card" style="padding: 0; margin-bottom: 20px;"><h3 style="padding: 15px 20px; margin: 0; background: #f8fafc; border-bottom: 1px solid var(--border); font-size: 1.2em;">🛡️ Registered Firm Users</h3><table style="width: 100%; border: none;"><tr><th style="padding-left: 20px;">Username</th><th>Role</th><th>Rights</th><th style="text-align:center;">Action</th></tr>{% for u in users %}<tr><td style="padding-left: 20px; font-weight: 500;">{{ u.username }}</td><td><span class="badge badge-mode">{{ u.role|title }}</span></td><td style="font-size: 0.85em;">Apprv: {% if u.can_approve %}✅{% else %}❌{% endif %} | Edit: {% if u.can_edit %}✅{% else %}❌{% endif %} | Rep: {% if u.can_view_reports %}✅{% else %}❌{% endif %} | Trash: {% if u.can_view_trash %}✅{% else %}❌{% endif %} | Del Logs: {% if u.can_delete_logs %}✅{% else %}❌{% endif %} | Ledger Dtls: {% if u.can_view_ledger_details %}✅{% else %}❌{% endif %}</td><td style="text-align: center;"><a href="/edit_user/{{ u.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;">✏️ Edit User</a></td></tr>{% endfor %}</table></div><div class="card" style="padding: 0;"><h3 style="padding: 15px 20px; margin: 0; background: #f8fafc; border-bottom: 1px solid var(--border); font-size: 1.2em;">✔️ Manage Custom Approvers</h3><table style="width: 100%; border: none;"><tr><th style="padding-left: 20px;">Approver Name</th><th style="text-align:center;">Action</th></tr>{% for a in approver_list %}<tr><td style="padding-left: 20px; font-weight: 500;"><span id="appr-span-{{a.id}}">{{ a.name }}</span><form id="appr-form-{{a.id}}" action="/edit_approver/{{ a.id }}" method="POST" style="display:none; gap:10px; align-items:center; margin:0;"><input type="text" name="name" value="{{ a.name }}" required style="max-width: 200px; padding: 5px;"><button type="submit" class="btn btn-sm btn-success">Save</button></form></td><td style="text-align: center;"><button class="btn btn-sm btn-warning" onclick="document.getElementById('appr-span-{{a.id}}').style.display='none'; document.getElementById('appr-form-{{a.id}}').style.display='flex'; this.style.display='none';">✏️ Edit</button> <a href="/delete_approver/{{ a.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Delete this custom approver name?');">🗑️</a></td></tr>{% else %}<tr><td colspan="2" style="text-align:center; padding:30px; color:#9ca3af;">No custom approvers added yet.</td></tr>{% endfor %}</table></div></div></body></html>'''

EDIT_USER_TEMPLATE = '''<!DOCTYPE html><html><head><title>Edit User</title>''' + BASE_STYLE + '''</head><body><div class="container">''' + NAVBAR_HTML + '''<div class="card" style="max-width: 500px; margin: 0 auto;"><h2 style="color: var(--primary); margin-bottom: 20px;">⚙️ Edit User Profile</h2><form action="/edit_user/{{ edit_user.id }}" method="POST"><div class="form-group"><label>Username</label><input type="text" name="username" value="{{ edit_user.username }}" required></div><div class="form-group"><label>New Password <small>(Leave blank to keep current)</small></label><input type="password" name="password"></div><div class="form-group"><label>User Role</label><select name="role" required><option value="superadmin" {% if edit_user.role == 'superadmin' %}selected{% endif %}>Superadmin</option><option value="admin" {% if edit_user.role == 'admin' %}selected{% endif %}>Admin</option><option value="cashier" {% if edit_user.role == 'cashier' %}selected{% endif %}>Cashier</option><option value="market" {% if edit_user.role == 'market' %}selected{% endif %}>Market</option></select></div><div class="form-group"><label>Idle Auto-Logout (Minutes)</label><input type="number" name="idle_timeout" value="{{ edit_user.idle_timeout_minutes | default(15) }}" min="1" required></div><div class="form-group" style="padding-bottom: 15px; margin-top: 10px; display: flex; flex-direction: column; gap: 8px;"><label style="display:flex; align-items:center; gap:10px; cursor:pointer;"><input type="checkbox" name="can_approve" value="1" {% if edit_user.can_approve %}checked{% endif %} style="width: auto;"> Grant Voucher Approval Rights</label><label style="display:flex; align-items:center; gap:10px; cursor:pointer;"><input type="checkbox" name="can_edit" value="1" {% if edit_user.can_edit %}checked{% endif %} style="width: auto;"> Grant Edit / Delete Rights</label><label style="display:flex; align-items:center; gap:10px; cursor:pointer;"><input type="checkbox" name="can_express_cashout" value="1" {% if edit_user.can_express_cashout %}checked{% endif %} style="width: auto;"> Grant Express Cash-Out</label><label style="display:flex; align-items:center; gap:10px; cursor:pointer;"><input type="checkbox" name="can_view_reports" value="1" {% if edit_user.can_view_reports %}checked{% endif %} style="width: auto;"> Grant Report Access</label><label style="display:flex; align-items:center; gap:10px; cursor:pointer;"><input type="checkbox" name="can_view_trash" value="1" {% if edit_user.can_view_trash %}checked{% endif %} style="width: auto;"> Grant Trash Bin Access</label><label style="display:flex; align-items:center; gap:10px; cursor:pointer;"><input type="checkbox" name="can_delete_logs" value="1" {% if edit_user.can_delete_logs %}checked{% endif %} style="width: auto;"> Grant Log Deletion Rights</label><label style="display:flex; align-items:center; gap:10px; cursor:pointer;"><input type="checkbox" name="can_view_ledger_details" value="1" {% if edit_user.can_view_ledger_details %}checked{% endif %} style="width: auto;"> Grant Detailed Ledger View</label></div><div style="display: flex; gap: 15px;"><a href="/manage_users" class="btn btn-outline" style="flex:1;">Cancel</a><button class="btn-success" type="submit" style="flex:1;">Save Updates</button></div></form></div></div></body></html>'''

APPROVALS_TEMPLATE = '''<!DOCTYPE html><html><head><title>Approvals Dashboard</title>''' + BASE_STYLE + '''</head><body><div class="container">''' + NAVBAR_HTML + '''<div style="display:flex; gap: 10px; margin-bottom: 20px;"><button class="btn btn-warning" id="tab-pending-btn" onclick="toggleTab('pending')" style="flex:1;">⏳ Pending Vouchers</button><button class="btn btn-outline" id="tab-approved-btn" onclick="toggleTab('approved')" style="flex:1; background:#fff;">✅ Approved History</button></div><div id="section-pending"><div class="card" style="margin-bottom: 20px;"><h3 style="margin-top: 0; font-size: 1.2em; color: var(--primary);">📅 Bulk Approve by Date Range</h3><form action="/bulk_approve" method="POST" style="display: flex; gap: 15px; align-items: flex-end; flex-wrap: wrap;"><div class="form-group flex-1" style="min-width: 150px;"><label>From Date</label><input type="date" name="start_date" required></div><div class="form-group flex-1" style="min-width: 150px;"><label>To Date</label><input type="date" name="end_date" required></div><div class="form-group flex-1" style="min-width: 200px;"><label>Approved By</label><select name="approved_by_select" style="border-color: var(--warning); font-weight:bold;"><option value="">-- Set as Myself ({{ username }}) --</option><optgroup label="✅ Allowed Approvers">{% for u in approvers %}{% if u.can_approve %}<option value="{{ u.username }}">{{ u.username }}</option>{% endif %}{% endfor %}</optgroup></select></div><button class="btn-success" type="submit" style="height: 45px; padding: 10px 25px; font-size: 1.05em;" onclick="return confirm('Approve ALL pending entries in this date range?');">Bulk Approve Range</button></form></div><div class="card" style="padding: 0;"><h3 style="padding: 15px 20px; margin: 0; background: #fef08a; border-bottom: 1px solid var(--border); font-size: 1.2em; color: #92400e;">☑️ Select & Approve Specific Vouchers</h3><form action="/bulk_approve_selected" method="POST" onsubmit="return confirm('Approve selected vouchers?');"><div style="padding: 15px 20px; border-bottom: 1px solid var(--border); display: flex; gap: 15px; align-items: flex-end; background: #fffbeb;"><div class="form-group" style="margin-bottom: 0; min-width: 200px;"><label style="color:#92400e;">Set Approved By:</label><select name="approved_by_select" style="border-color: var(--warning); font-weight:bold;"><option value="">-- Set as Myself ({{ username }}) --</option><optgroup label="✅ Allowed Approvers">{% for u in approvers %}{% if u.can_approve %}<option value="{{ u.username }}">{{ u.username }}</option>{% endif %}{% endfor %}</optgroup></select></div><button type="submit" class="btn btn-success" style="height: 40px; padding: 0 25px;">✅ Approve Selected Entries</button></div><table style="width: 100%; border: none;"><tr><th style="padding-left: 20px; width: 40px;"><input type="checkbox" onclick="let cb = document.getElementsByName('selected_links'); for(let i=0;i<cb.length;i++) cb[i].checked = this.checked;" style="width:18px; height:18px; cursor:pointer;"></th><th>Date & Time</th><th>Description / Detail</th><th style="text-align: right;">Amount</th><th style="text-align: center;">Action</th></tr>{% for t in pending %}<tr><td style="padding-left: 20px;"><input type="checkbox" name="selected_links" value="{{ t.link_id }}" style="width:18px; height:18px; cursor:pointer;"></td><td><span style="font-weight: 500;">{{ t.date }}</span><br><span style="font-size: 0.85em; color: #6b7280;">{{ t.time }}</span></td><td><span class="badge badge-pending">Pending</span><br><span style="white-space: pre-wrap;">{{ t.description }}</span></td><td style="text-align: right;"><strong>₹{{ "{:,.2f}".format(t.amount) }}</strong></td><td style="text-align: center;"><a href="/approve_voucher/{{ t.link_id }}" class="btn btn-sm btn-success" onclick="return confirm('Approve this transaction?');">✅</a> <a href="/reject_voucher/{{ t.link_id }}" class="btn btn-sm btn-danger" onclick="return confirm('Reject & Delete this transaction?');">❌</a></td></tr>{% else %}<tr><td colspan="5" style="text-align:center; color:#9ca3af; padding: 40px;">No pending vouchers requiring approval.</td></tr>{% endfor %}</table></form></div></div><div id="section-approved" style="display: none;"><div class="card" style="padding: 0;"><h3 style="padding: 15px 20px; margin: 0; background: #d1fae5; border-bottom: 1px solid var(--border); font-size: 1.2em; color: #065f46;">✅ Recently Approved Vouchers</h3><table style="width: 100%; border: none;"><tr><th style="padding-left: 20px;">Date & Time</th><th>Description / Detail</th><th style="text-align: right; padding-right:20px;">Amount</th></tr>{% for t in approved %}<tr><td style="padding-left: 20px;"><span style="font-weight: 500;">{{ t.date }}</span><br><span style="font-size: 0.85em; color: #6b7280;">{{ t.time }}</span></td><td><span class="badge badge-in" style="background:#e0f2fe; color:#0369a1;">Approved by: {{ t.approved_by }}</span><br><span style="white-space: pre-wrap;">{{ t.description }}</span></td><td style="text-align: right; padding-right:20px;"><strong>₹{{ "{:,.2f}".format(t.amount) }}</strong></td></tr>{% else %}<tr><td colspan="3" style="text-align:center; color:#9ca3af; padding: 40px;">No recently approved vouchers found.</td></tr>{% endfor %}</table></div></div></div><script>document.addEventListener("DOMContentLoaded", function() { setAutoDateTime(); });function toggleTab(tab) {if(tab === 'pending') {document.getElementById('section-pending').style.display = 'block';document.getElementById('section-approved').style.display = 'none';document.getElementById('tab-pending-btn').className = 'btn btn-warning';document.getElementById('tab-approved-btn').className = 'btn btn-outline';document.getElementById('tab-approved-btn').style.background = '#fff';} else {document.getElementById('section-pending').style.display = 'none';document.getElementById('section-approved').style.display = 'block';document.getElementById('tab-pending-btn').className = 'btn btn-outline';document.getElementById('tab-pending-btn').style.background = '#fff';document.getElementById('tab-approved-btn').className = 'btn btn-success';}}</script></body></html>'''

ENTRY_FORM_HTML = '''
<form action="/add_batch_unified" method="POST" class="no-print">
    <input type="hidden" name="source_page" value="{{ active_page }}">
    <div style="background: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid var(--border); margin-bottom: 20px;">
        <div class="flex-row" style="margin-bottom: 15px;">
            <div class="form-group flex-1" style="min-width: 140px; margin-bottom: 0;"><label>Date</label><input type="date" name="date" required></div>
            <div class="form-group flex-1" style="min-width: 140px; margin-bottom: 0;"><label>Time</label><input type="time" name="time" required></div>
            <div class="form-group flex-1" style="min-width: 150px; margin-bottom: 0;"><label>Payment Mode</label><select name="payment_mode" required><option value="Cash">💵 Cash</option><option value="Online">💳 Online</option></select></div>
        </div>
        <div class="flex-row">
            <div class="form-group flex-1" style="min-width: 200px; margin-bottom: 0;">
                <label>Nature of Batch Voucher</label>
                <select name="txn_nature" id="txn_nature" onchange="toggleNature()" required style="border-color: var(--primary); font-weight: bold; font-size: 1.05em;">
                    <option value="slip_in" style="color:var(--danger);">➖ Submit Slip / Bill (- Deduct from User Bal)</option>
                    <option value="advance" style="color:var(--primary);">📤 Give Advance Payment (+ Positive User Bal)</option>
                    <option value="receive_cash" style="color:var(--success);">📥 Receive Cash Settlement (- Deduct from User Bal)</option>
                </select>
            </div>
            <div class="form-group flex-1" style="min-width: 250px; margin-bottom: 0; flex: 2;">
                <label id="primary_label" style="color: var(--primary);">Ledger Account</label>
                <select name="primary_account" id="primary_account" onchange="checkNewAccount(this)" required style="border-color: var(--primary); font-weight: bold; background: white; font-size: 1.05em;">
                    <option value="main" style="font-weight:bold;">🏢 Main Cash Book (Default)</option>
                    <optgroup label="👥 Person Ledgers">
                        {% for p in persons %}<option value="person_{{ p.id }}">👤 {{ p.name }}'s Account</option>{% endfor %}
                    </optgroup>
                    <optgroup label="💸 Dasti Accounts">
                        {% for dp in dasti_persons %}<option value="dasti_{{ dp.id }}">💸 {{ dp.name }}'s Dasti</option>{% endfor %}
                    </optgroup>
                    <option value="new_dasti" style="color: #0ea5e9; font-weight: bold;">➕ Create New Dasti Account...</option>
                    <option value="new_person" style="color: var(--success); font-weight: bold;">➕ Create New Person Account...</option>
                </select>
                <input type="text" name="new_account_name" id="new_account_name" placeholder="Type New Name Here..." style="display:none; margin-top: 8px; border-color: var(--primary); width: 100%;">
            </div>
        </div>
        
        <div class="form-group" style="margin-top: 15px; margin-bottom: 0;">
            <label style="color:#92400e;">Approved By (Printed Name)</label>
            <select name="approved_by_select" style="border-color: var(--warning); background:white;">
                <option value="">-- None / Pending --</option>
                {% for u in approver_names %}<option value="{{ u }}">{{ u }}</option>{% endfor %}
                <option value="new_approver">➕ Add New Approver...</option>
            </select>
            <input type="text" name="new_approver_name" id="new_approver_name" placeholder="Enter New Approver Name..." style="display:none; margin-top: 8px; border-color: var(--warning); width: 100%;">
        </div>
        <script>
            document.querySelector('select[name="approved_by_select"]').addEventListener('change', function() {
                const inp = document.getElementById('new_approver_name');
                if(this.value === 'new_approver') { inp.style.display = 'block'; inp.required = true; }
                else { inp.style.display = 'none'; inp.required = false; }
            });
        </script>
        
    </div>
    <div style="border: 1px solid var(--border); border-radius: 8px; margin-bottom: 20px; background: #fff; overflow-x: auto;">
        <table style="width: 100%; min-width: 800px; margin: 0; background: transparent;">
            <thead style="background: #f1f5f9;"><tr><th style="width: 25%;">Category</th><th style="width: 50%;">Bill Detail / Description</th><th style="width: 20%;">Amount (₹)</th><th style="width: 5%; text-align: center;">Act</th></tr></thead>
            <tbody id="entryBody"></tbody>
        </table>
    </div>
    <div style="display: flex; gap: 15px; justify-content: space-between;">
        <button type="button" class="btn-outline" onclick="addRow('{% for c in categories %}<option value=\\\'{{c}}\\\'>{{c}}</option>{% endfor %}')" style="min-width: 200px; font-size: 1em;">+ Add Another Row</button>
        <button class="btn-success" type="submit" style="min-width: 250px; font-size: 1.1em; padding: 12px;" onclick="return confirmSubmission(event)">💾 Save Batch Voucher</button>
    </div>
</form>
<script>
    const accountBalances = {{ account_balances | safe }};
    function confirmSubmission(event) {
        const primaryAcc = document.getElementById('primary_account').value;
        const nature = document.getElementById('txn_nature').value;
        let totalAmt = 0;
        document.querySelectorAll('input[name="amount[]"]').forEach(inp => totalAmt += (parseFloat(inp.value) || 0));
        
        let targetAcc = primaryAcc;
        let isDeduction = false;
        
        if (primaryAcc === 'main' && nature === 'advance') isDeduction = true;
        if (primaryAcc === 'main' && nature === 'slip_in') isDeduction = true;
        if (primaryAcc.startsWith('person_') || primaryAcc.startsWith('dasti_')) {
            if (nature === 'slip_in' || nature === 'receive_cash') isDeduction = true;
            if (nature === 'advance') { targetAcc = 'main'; isDeduction = true; } 
        }

        if (isDeduction && accountBalances[targetAcc] !== undefined) {
            if ((accountBalances[targetAcc] - totalAmt) < 0) {
                if(!confirm("⚠️ NEGATIVE BALANCE WARNING\\n\\nThis batch will cause the account to go negative.\\nCurrent Balance: ₹" + accountBalances[targetAcc].toFixed(2) + "\\nDeduction: ₹" + totalAmt.toFixed(2) + "\\n\\nProceed anyway?")) {
                    event.preventDefault(); return false;
                }
            }
        }
        return true;
    }
    document.addEventListener("DOMContentLoaded", function() { initForm('{% for c in categories %}<option value="{{c}}">{{c}}</option>{% endfor %}'); });
</script>
'''

EDIT_TEMPLATE = '''<!DOCTYPE html><html><head><title>Edit Entry</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        <div class="card" style="max-width: 850px; margin: 0 auto;">
            <h2 style="color: var(--primary); margin-bottom: 20px;">✏️ Edit / Correct Transaction</h2>
            <form action="/edit/{{ table_name }}/{{ entry.id }}" method="POST">
                
                <div class="flex-row" style="align-items: flex-end; margin-bottom:15px;">
                    <div class="form-group flex-1"><label>Date</label><input type="date" name="date" id="edit_date" value="{{ entry.date }}" required></div>
                    <div class="form-group flex-1"><label>Time</label><input type="time" name="time" id="edit_time" value="{{ entry.time }}" required></div>
                    <div class="form-group flex-1"><label>Mode</label>
                        <select name="payment_mode" required><option value="Cash" {% if entry.payment_mode == 'Cash' %}selected{% endif %}>Cash</option><option value="Online" {% if entry.payment_mode == 'Online' %}selected{% endif %}>Online</option></select>
                    </div>
                </div>
                
                {% if is_split %}
                    <!-- SPLIT VOUCHER EDITOR -->
                    <input type="hidden" name="is_split_edit" value="1">
                    <div style="background:#f0f9ff; border:1px solid #bae6fd; padding:15px; border-radius:8px; margin-bottom:15px;">
                        <h4 style="margin:0 0 15px 0; color:#0369a1;">🔀 Editing Split Voucher</h4>
                        <div class="flex-row">
                            <div class="form-group flex-2" style="flex:2;"><label>Master Description / Bill No.</label><input type="text" name="description" value="{{ entry.description.split(' (')[0] }}" required></div>
                            <div class="form-group flex-1">
                                <label style="color:red;">Total Amount (₹) <small>(Auto)</small></label>
                                <input type="text" id="master_amount_display" readonly value="{{ '%.2f'|format(entry.amount) }}" style="border-color:red; font-weight:bold; background:#fef2f2; color:red;">
                                <input type="hidden" id="master_amount" name="amount" value="{{ entry.amount }}">
                            </div>
                        </div>
                        
                        <div style="display:flex; justify-content:space-between; align-items:center; margin: 15px 0 10px 0;">
                            <strong style="color:#0369a1;">Allocated Accounts:</strong>
                            <div style="font-size:1em; padding:5px 10px; background:white; border-radius:5px; border:1px solid #ccc;">
                                Total (Auto): <strong id="calc_assigned" style="color:green;">₹0.00</strong>
                            </div>
                        </div>
                        
                        <table style="width: 100%; border: none; background: white;">
                            <thead style="background: #bae6fd;">
                                <tr><th>Nature</th><th>Account</th><th>Category</th><th style="text-align:right;">Amount (₹)</th><th>Act</th></tr>
                            </thead>
                            <tbody id="split-entry-body">
                                {% for sp in splits_data %}
                                <tr>
                                    <td style="padding:5px;"><select name="txn_nature[]" required style="font-size:0.9em; padding:6px; font-weight:bold;"><option value="slip_in" {% if sp.nature == 'slip_in' %}selected{% endif %} style="color:red;">➖ Slip</option><option value="advance" {% if sp.nature == 'advance' %}selected{% endif %} style="color:blue;">📤 Advance</option><option value="receive_cash" {% if sp.nature == 'receive_cash' %}selected{% endif %} style="color:green;">📥 Receive</option></select></td>
                                    <td style="padding:5px;"><select name="primary_account[]" required style="font-size:0.9em; padding:6px; font-weight:bold;"><option value="main" {% if sp.account == 'main' %}selected{% endif %}>🏢 Main Book</option><optgroup label="👥 Persons">{% for p in persons %}<option value="person_{{ p.id }}" {% if sp.account == 'person_'~p.id|string %}selected{% endif %}>👤 {{ p.name }}</option>{% endfor %}</optgroup><optgroup label="💸 Dasti">{% for dp in dasti_persons %}<option value="dasti_{{ dp.id }}" {% if sp.account == 'dasti_'~dp.id|string %}selected{% endif %}>💸 {{ dp.name }}</option>{% endfor %}</optgroup></select></td>
                                    <td style="padding:5px;"><select name="category[]" required style="font-size:0.9em; padding:6px;">{% for c in categories %}<option value="{{c}}" {% if sp.category == c %}selected{% endif %}>{{c}}</option>{% endfor %}</select></td>
                                    <td style="padding:5px;"><input type="number" step="0.01" min="0" name="split_amount[]" class="split-amt-input" value="{{ sp.amount }}" required style="font-size:0.9em; padding:6px; text-align:right;" onkeyup="updateSplitCalc()" onchange="updateSplitCalc()"></td>
                                    <td style="padding:5px; text-align:center;"><button type="button" onclick="this.closest('tr').remove(); updateSplitCalc();" style="background:var(--danger); color:white; border:none; padding:5px 10px; border-radius:4px; cursor:pointer;">X</button></td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                        <button type="button" class="btn btn-sm btn-outline" onclick="addSplitRow()" style="margin-top:10px; background:white;">+ Add Row</button>
                    </div>
                {% else %}
                    <!-- STANDARD EDIT UI -->
                    <div class="flex-row">
                        <div class="form-group flex-1"><label>Category</label><select name="category" onchange="toggleCustomCategory(this)" required>{% for c in categories %}<option value="{{ c }}" {% if entry.category == c %}selected{% endif %}>{{ c }}</option>{% endfor %}<option value="Other" {% if entry.category not in categories %}selected{% endif %}>Other (Type Below)...</option></select><input type="text" name="custom_category" value="{% if entry.category not in categories %}{{ entry.category }}{% endif %}" placeholder="Custom Category..." style="display:{% if entry.category not in categories %}block{% else %}none{% endif %}; margin-top: 8px; border-color: var(--primary);"></div>
                    </div>
                    <div class="form-group"><label>Description / Bill Details</label><input type="text" name="description" value="{{ entry.description }}" required></div>
                    
                    {% if has_link %}
                    <div style="background:#e0e7ff; border:2px solid #818cf8; padding:15px; border-radius:10px; margin-bottom: 15px;">
                        <h4 style="margin:0 0 10px 0; color:#3730a3; font-size:0.95em;">🔧 Correct Account / Nature</h4>
                        <div class="flex-row">
                            <div class="form-group flex-1" style="min-width:200px; margin-bottom:0;"><label>Transaction Nature</label><select name="txn_nature" required style="border-color: var(--primary); font-weight:bold;"><option value="slip_in" {% if current_nature == 'slip_in' %}selected{% endif %}>➖ Submit Slip / Bill (- Deduct)</option><option value="advance" {% if current_nature == 'advance' %}selected{% endif %}>📤 Give Advance Payment (+ Positive)</option><option value="receive_cash" {% if current_nature == 'receive_cash' %}selected{% endif %}>📥 Receive Cash Settlement (- Deduct)</option></select></div>
                            <div class="form-group flex-1" style="min-width:220px; margin-bottom:0;"><label>Ledger Account</label><select name="primary_account" onchange="checkNewAccount(this)" required style="border-color: var(--primary); font-weight:bold; background:white;"><option value="main" {% if current_account_type == 'main' %}selected{% endif %}>🏢 Main Cash Book</option><optgroup label="👥 Person Ledgers">{% for p in persons %}<option value="person_{{ p.id }}" {% if current_account_type == 'person' and current_primary_id == p.id %}selected{% endif %}>👤 {{ p.name }}</option>{% endfor %}</optgroup><optgroup label="💸 Dasti Accounts">{% for dp in dasti_persons %}<option value="dasti_{{ dp.id }}" {% if current_account_type == 'dasti' and current_primary_id == dp.id %}selected{% endif %}>💸 {{ dp.name }}</option>{% endfor %}</optgroup><option value="new_dasti">➕ Create New Dasti Account...</option><option value="new_person">➕ Create New Person Account...</option></select><input type="text" name="new_account_name" id="new_account_name" placeholder="Type New Name Here..." style="display:none; margin-top: 8px; border-color: var(--primary);"></div>
                        </div>
                    </div>
                    {% else %}
                    <div class="flex-row">
                        <div class="form-group flex-1"><label>Type</label>
                            <select name="type" required>
                                <option value="income" {% if entry.type == 'income' %}selected{% endif %}>➕ Main In</option><option value="expense" {% if entry.type == 'expense' %}selected{% endif %}>➖ Main Out</option>
                                <option value="dasti_out" {% if entry.type == 'dasti_out' %}selected{% endif %}>📤 Transfer (Main Out)</option><option value="batch_ledger_out" {% if entry.type == 'batch_ledger_out' %}selected{% endif %}>➖ Ledger Slip Out</option>
                                <option value="dasti_voucher_out" {% if entry.type == 'dasti_voucher_out' %}selected{% endif %}>💸 Dasti Voucher Out</option><option value="dasti_voucher_in" {% if entry.type == 'dasti_voucher_in' %}selected{% endif %}>💸 Dasti Settlement In</option>
                                <option value="settlement" {% if entry.type == 'settlement' %}selected{% endif %}>➖ Person Bill / Settlement</option><option value="advance" {% if entry.type == 'advance' %}selected{% endif %}>➕ Person Advance</option>
                            </select>
                        </div>
                    </div>
                    {% endif %}
                    <div class="form-group"><label>Amount (₹)</label><input type="number" step="0.01" min="0" name="amount" value="{{ entry.amount }}" required></div>
                {% endif %}

                {% if session.get('can_approve') == 1 or session.get('role') in ['admin', 'superadmin'] %}
                <div class="form-group" style="background:#fffbeb; padding:12px; border-radius:8px; border:1px solid #fde68a; margin-top: 5px;">
                    <label style="color:#92400e;">⏳ Approval Status</label>
                    <select name="status" style="border-color: var(--warning); font-weight:bold;"><option value="pending" {% if entry.status == 'pending' %}selected{% endif %}>⏳ Pending</option><option value="approved" {% if entry.status == 'approved' %}selected{% endif %}>✅ Approved</option></select>
                    <label style="color:#92400e; margin-top:12px;">✅ Approved By</label>
                    <select name="approved_by_select" onchange="document.getElementById('approver_custom_input').style.display = this.value === 'other' ? 'block' : 'none';" style="border-color: var(--warning);"><option value="">-- Set as Myself ({{ username }}) --</option><optgroup label="✅ Approvers">{% for u in approvers %}{% if u.can_approve %}<option value="{{ u.username }}" {% if entry.approved_by == u.username %}selected{% endif %}>{{ u.username }}</option>{% endif %}{% endfor %}</optgroup><option value="other" {% if entry.approved_by and entry.approved_by not in approver_names %}selected{% endif %}>✏️ Other (Type Name)...</option></select>
                    <input type="text" name="approved_by_custom" id="approver_custom_input" value="{% if entry.approved_by and entry.approved_by not in approver_names %}{{ entry.approved_by }}{% endif %}" placeholder="Type Approver Name..." style="display:{% if entry.approved_by and entry.approved_by not in approver_names %}block{% else %}none{% endif %}; margin-top: 8px; border-color: var(--primary);">
                </div>
                {% endif %}

                <div class="form-group" style="margin-top: 15px;">
                    <label style="display:flex; align-items:center; gap:8px; color: #d97706; cursor:pointer;"><input type="checkbox" name="is_flagged" value="1" {% if entry.is_flagged == 1 %}checked{% endif %} style="width: auto;"> 🚩 Mark this entry as Flagged</label>
                </div>

                <div style="display: flex; gap: 15px; margin-top: 20px;">
                    <a href="javascript:history.back()" class="btn btn-outline" style="flex:1;">Cancel / Exit</a>
                    <button class="btn-success" type="submit" id="saveEditBtn" style="flex:1;">Save Changes</button>
                </div>
            </form>
        </div>
        
        <script>
            {% if is_split %}
            const accountOpts = `<option value="main">🏢 Main Book</option><optgroup label="👥 Persons">{% for p in persons %}<option value="person_{{ p.id }}">👤 {{ p.name }}</option>{% endfor %}</optgroup><optgroup label="💸 Dasti">{% for dp in dasti_persons %}<option value="dasti_{{ dp.id }}">💸 {{ dp.name }}</option>{% endfor %}</optgroup>`;
            const catOpts = `{% for c in categories %}<option value="{{c}}">{{c}}</option>{% endfor %}`;
            
            function addSplitRow() {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="padding:5px;"><select name="txn_nature[]" required style="font-size:0.9em; padding:6px; font-weight:bold;"><option value="slip_in" style="color:red;">➖ Slip</option><option value="advance" style="color:blue;">📤 Advance</option><option value="receive_cash" style="color:green;">📥 Receive</option></select></td>
                    <td style="padding:5px;"><select name="primary_account[]" required style="font-size:0.9em; padding:6px; font-weight:bold;">${accountOpts}</select></td>
                    <td style="padding:5px;"><select name="category[]" required style="font-size:0.9em; padding:6px;">${catOpts}</select></td>
                    <td style="padding:5px;"><input type="number" step="0.01" min="0" name="split_amount[]" class="split-amt-input" value="0" required style="font-size:0.9em; padding:6px; text-align:right;" onkeyup="updateSplitCalc()" onchange="updateSplitCalc()"></td>
                    <td style="padding:5px; text-align:center;"><button type="button" onclick="this.closest('tr').remove(); updateSplitCalc();" style="background:var(--danger); color:white; border:none; padding:5px 10px; border-radius:4px; cursor:pointer;">X</button></td>
                `;
                document.getElementById('split-entry-body').appendChild(tr);
            }
            
            function updateSplitCalc() {
                let assigned = 0;
                document.querySelectorAll('.split-amt-input').forEach(inp => { assigned += (parseFloat(inp.value) || 0); });
                document.getElementById('calc_assigned').innerText = '₹' + assigned.toFixed(2);
                let displayEl = document.getElementById('master_amount_display');
                if (displayEl) displayEl.value = assigned.toFixed(2);
                document.getElementById('master_amount').value = assigned.toFixed(2);

                document.getElementById('saveEditBtn').disabled = assigned <= 0;
            }
            // Init calc on load
            document.addEventListener('DOMContentLoaded', updateSplitCalc);
            
            {% endif %}
            
            function toggleCustomCategory(selectElem) {
                const customInput = document.getElementsByName('custom_category')[0];
                if(customInput) { customInput.style.display = selectElem.value === 'Other' ? 'block' : 'none'; }
            }
            function checkNewAccount(sel) {
                const newAcc = document.getElementById('new_account_name');
                if(!newAcc) return;
                if(sel.value === 'new_dasti' || sel.value === 'new_person') { newAcc.style.display = 'block'; newAcc.required = true; } 
                else { newAcc.style.display = 'none'; newAcc.required = false; }
            }
        </script>
    </div></body></html>'''

INDEX_TEMPLATE = '''<!DOCTYPE html><html><head><title>Main Cash Book Dashboard</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        
        <div class="card no-print" style="padding: 20px; background: linear-gradient(to right, #ffffff, #f1f5f9);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 style="margin: 0; font-size: 1.2em; color: #475569;">📈 Account Flow Summary</h3>
                {% if active_filter != 'all' %}
                <a href="/" class="badge badge-pending" style="text-decoration:none;">❌ Clear Filter (Currently: {{ active_filter|title }})</a>
                {% endif %}
            </div>
            <div class="stats-grid" style="grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 0;">
                <div class="stat-card clickable" onclick="window.location.href='/?filter=today'" style="padding: 15px; cursor: pointer; {% if active_filter == 'today' %}border-color:var(--primary); background:#e0e7ff;{% endif %}">
                    <h4>Today</h4><div style="color:var(--success); font-weight:bold;">+ ₹{{ "{:,.2f}".format(s_d_in) }}</div><div style="color:var(--danger); font-weight:bold;">- ₹{{ "{:,.2f}".format(s_d_out) }}</div>
                </div>
                <div class="stat-card clickable" onclick="window.location.href='/?filter=yesterday'" style="padding: 15px; cursor: pointer; {% if active_filter == 'yesterday' %}border-color:var(--primary); background:#e0e7ff;{% endif %}">
                    <h4>Yesterday</h4><div style="color:var(--success); font-weight:bold;">+ ₹{{ "{:,.2f}".format(s_yest_in) }}</div><div style="color:var(--danger); font-weight:bold;">- ₹{{ "{:,.2f}".format(s_yest_out) }}</div>
                </div>
                <div class="stat-card clickable" onclick="window.location.href='/?filter=week'" style="padding: 15px; cursor: pointer; {% if active_filter == 'week' %}border-color:var(--primary); background:#e0e7ff;{% endif %}">
                    <h4>Last 7 Days</h4><div style="color:var(--success); font-weight:bold;">+ ₹{{ "{:,.2f}".format(s_w_in) }}</div><div style="color:var(--danger); font-weight:bold;">- ₹{{ "{:,.2f}".format(s_w_out) }}</div>
                </div>
                <div class="stat-card clickable" onclick="window.location.href='/?filter=month'" style="padding: 15px; cursor: pointer; {% if active_filter == 'month' %}border-color:var(--primary); background:#e0e7ff;{% endif %}">
                    <h4>This Month</h4><div style="color:var(--success); font-weight:bold;">+ ₹{{ "{:,.2f}".format(s_m_in) }}</div><div style="color:var(--danger); font-weight:bold;">- ₹{{ "{:,.2f}".format(s_m_out) }}</div>
                </div>
                <div class="stat-card clickable" onclick="window.location.href='/?filter=year'" style="padding: 15px; cursor: pointer; {% if active_filter == 'year' %}border-color:var(--primary); background:#e0e7ff;{% endif %}">
                    <h4>This Year</h4><div style="color:var(--success); font-weight:bold;">+ ₹{{ "{:,.2f}".format(s_y_in) }}</div><div style="color:var(--danger); font-weight:bold;">- ₹{{ "{:,.2f}".format(s_y_out) }}</div>
                </div>
            </div>
        </div>

        <div class="express-entry no-print">
            <h3 style="margin-top: 0; color: #3730a3; font-size: 1.15em;">🚀 Express Direct Entry (Main Book)</h3>
            <form action="/add_express" method="POST" style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                <input type="date" name="date" id="express_date" required style="flex: 1; min-width: 120px; border-color: #a5b4fc;">
                <input type="time" name="time" id="express_time" required style="flex: 1; min-width: 100px; border-color: #a5b4fc;">
                <input type="text" name="description" placeholder="Description / Reason" required style="flex: 2; min-width: 180px; border-color: #a5b4fc;">
                
                <select name="category" required style="flex: 1; min-width: 130px; border-color: #a5b4fc;">
                    {% for c in categories %}<option value="{{c}}">{{c}}</option>{% endfor %}
                </select>
                
                <select name="approved_by_select" style="flex: 1; min-width: 130px; border-color: #a5b4fc;">
                    <option value="">-- Apprv By --</option>
                    {% for u in approver_names %}<option value="{{ u }}">{{ u }}</option>{% endfor %}
                </select>

                <select name="type" required style="flex: 1; min-width: 120px; font-weight: bold; border-color: #a5b4fc;">
                    <option value="income">➕ Cash In</option>
                    {% if session.get('can_express_cashout') == 1 %}
                    <option value="expense">➖ Cash Out</option>
                    {% endif %}
                </select>
                <input type="number" step="0.01" min="0" name="amount" placeholder="Amount (₹)" value="0" required style="flex: 1; min-width: 110px; border-color: #a5b4fc;">
                <button class="btn" type="submit" style="flex: 1; min-width: 100px; background: #4f46e5;">⚡ Save</button>
            </form>
        </div>
        
        <div class="card balance-card">
            <h2 style="color: #64748b; font-size: 1.1em; text-transform: uppercase; margin-bottom: 0;">🏢 Available Main Cash Book Balance</h2>
            <div class="balance-amount" style="color: {{ 'var(--success)' if balance >= 0 else 'var(--danger)' }}">₹{{ "{:,.2f}".format(balance) }}</div>
            
            <div style="display: flex; justify-content: center; gap: 30px; margin-top: 15px; flex-wrap: wrap;">
                <div style="color: #0369a1; background: #e0f2fe; padding: 10px 15px; border-radius: 8px; border: 1px solid #bae6fd; min-width: 250px;">
                    <strong style="font-size: 0.85em; color: #0284c7; text-transform: uppercase;">Person Ledger Advances (Outstanding)</strong><br>
                    <span style="font-size: 1.2em; font-weight: bold;">₹{{ "{:,.2f}".format(total_dasti) }}</span>
                    {% if dasti_breakdown %}
                    <div style="margin-top: 8px; font-size: 0.85em; color: #0369a1; text-align: left; border-top: 1px solid #bae6fd; padding-top: 8px;">
                        {% for d in dasti_breakdown %}
                        <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                            <span>👤 {{ d.name }}</span> <strong>₹{{ "{:,.2f}".format(d.amount) }}</strong>
                        </div>
                        {% endfor %}
                    </div>
                    {% endif %}
                </div>
            </div>
        </div>
        
        <div class="card no-print" style="padding: 25px; overflow-x: auto;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 style="margin:0; font-size: 1.3em;">⚡ Cash in/ Cash out</h3>
                <button class="btn" style="background: #8b5cf6;" onclick="toggleFastMode()">🚀 Toggle Fast Mode</button>
            </div>
            
            <!-- FAST MODE FORM -->
            <div id="fast-mode-section" style="display:none; background:#e0e7ff; padding: 15px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #818cf8; overflow-x: auto;">
               <form action="/add_fast_unified" method="POST" style="min-width: 800px;">
                   <input type="hidden" name="source_page" value="{{ active_page }}">
                   <div style="display:flex; gap:10px; margin-bottom:10px;">
                       <input type="date" name="date" class="auto-date" required style="width: 150px;">
                       <input type="time" name="time" class="auto-time" required style="width: 120px;">
                       <select name="payment_mode" required style="width: 120px;"><option value="Cash">Cash</option><option value="Online">Online</option></select>
                   </div>
                   
                   <table style="width: 100%; border: none; background: white;">
                       <thead>
                           <tr style="background: #c7d2fe;">
                               <th style="font-size: 0.8em; padding: 8px;">Nature of Voucher</th>
                               <th style="font-size: 0.8em; padding: 8px;">Ledger Account (- Deduct)</th>
                               <th style="font-size: 0.8em; padding: 8px;">Approved By</th>
                               <th style="font-size: 0.8em; padding: 8px;">Category</th>
                               <th style="font-size: 0.8em; padding: 8px;">Description / Remarks</th>
                               <th style="font-size: 0.8em; padding: 8px;">Amount (₹)</th>
                               <th style="font-size: 0.8em; padding: 8px; text-align: center;">Act</th>
                           </tr>
                       </thead>
                       <tbody id="fast-entry-body">
                       </tbody>
                   </table>
                   
                   <div style="display:flex; justify-content: space-between; margin-top: 10px;">
                       <button type="button" class="btn btn-outline" onclick="addFastRow()" style="background:white;">+ Add New Row</button>
                       <button class="btn btn-success" type="submit" style="padding: 10px 25px;">💾 Save Fast Batch</button>
                   </div>
               </form>
            </div>
            
            <div id="batch-mode-section">
                ''' + ENTRY_FORM_HTML + '''
            </div>
        </div>
        
        <div class="ledger-container">
            <div class="ledger-col"><h3 class="ledger-title" style="color: var(--success); border-bottom: 3px solid var(--success);">Receipts (+ IN) {% if active_filter != 'all' %}({{active_filter|title}}){% endif %}</h3>
                <table style="width: 100%; font-size: 0.95em;">
                    <thead><tr><th style="width: 5%;">Sr.</th><th>Date</th><th>Mode/Cat</th><th>Detail</th><th style="text-align: right;">Amount</th>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<th class="no-print">Act</th>{% endif %}</tr></thead>
                    <tbody id="receipts-tbody">
                    {% for t in incomes %}<tr>
                        <td style="color: #64748b; font-weight: bold;">{{ loop.index }}</td>
                        <td><span style="font-weight: 500;">{{ t.date }}</span><br><span style="font-size: 0.85em; color: #6b7280;">{{ t.time }}</span></td>
                        <td><span class="badge badge-mode">{{ t.payment_mode }}</span><br><span style="font-size: 0.85em; color: #4b5563;">{{ t.category }}</span></td>
                        <td style="white-space: pre-wrap;">{{ t.description }}
                            {% if t.status == 'approved' and t.approved_by %}<br><span style="color: var(--success); font-size: 0.85em; font-weight: 600;">✓ Apprv: {{ t.approved_by }}</span>{% endif %}
                            {% if t.is_flagged == 1 %}<br><span style="color: #f59e0b; font-size: 0.85em; font-weight: 600;">🚩 Flagged</span>{% endif %}
                        </td>
                        <td style="text-align: right;">
                            {% if t.status == 'pending' %}<span class="badge badge-pending">⏳ Pending</span><br>{% endif %}
                            <span class="badge badge-in">+ ₹{{ "{:,.2f}".format(t.amount) }}</span>
                        </td>
                        {% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}
                        <td style="text-align: center;" class="no-print"><a href="/edit/transactions/{{ t.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;">✏️</a> <br> <a href="/delete/transactions/{{ t.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Move to Trash?');">🗑️</a></td>
                        {% endif %}
                    </tr>{% else %}<tr><td colspan="6" style="text-align: center; color: #9ca3af; padding: 40px 0;">No entries matching criteria.</td></tr>{% endfor %}
                    </tbody>
                </table>
                <div class="pagination-controls no-print">
                    <button class="btn btn-outline btn-sm" onclick="prevReceipts()">← Previous</button>
                    <span id="receipt-page-info" style="font-size: 0.9em; font-weight: 500;">Page 1</span>
                    <button class="btn btn-outline btn-sm" onclick="nextReceipts()">Next →</button>
                </div>
            </div>
            
            <div class="ledger-col"><h3 class="ledger-title" style="color: var(--danger); border-bottom: 3px solid var(--danger);">Payments (- OUT) {% if active_filter != 'all' %}({{active_filter|title}}){% endif %}</h3>
                <table style="width: 100%; font-size: 0.95em;">
                    <thead><tr><th style="width: 5%;">Sr.</th><th>Date</th><th>Mode/Cat</th><th>Detail</th><th style="text-align: right;">Amount</th>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<th class="no-print">Act</th>{% endif %}</tr></thead>
                    <tbody id="payments-tbody">
                    {% for t in expenses %}<tr>
                        <td style="color: #64748b; font-weight: bold;">{{ loop.index }}</td>
                        <td><span style="font-weight: 500;">{{ t.date }}</span><br><span style="font-size: 0.85em; color: #6b7280;">{{ t.time }}</span></td>
                        <td><span class="badge badge-mode">{{ t.payment_mode }}</span><br><span style="font-size: 0.85em; color: #4b5563;">{{ t.category }}</span></td>
                        <td style="white-space: pre-wrap;">{{ t.description }}
                            {% if t.status == 'approved' and t.approved_by %}<br><span style="color: var(--success); font-size: 0.85em; font-weight: 600;">✓ Apprv: {{ t.approved_by }}</span>{% endif %}
                            {% if t.is_flagged == 1 %}<br><span style="color: #f59e0b; font-size: 0.85em; font-weight: 600;">🚩 Flagged</span>{% endif %}
                        </td>
                        <td style="text-align: right;">
                            {% if t.status == 'pending' %}<span class="badge badge-pending">⏳ Pending</span><br>{% endif %}
                            <span class="badge badge-out">- ₹{{ "{:,.2f}".format(t.amount) }}</span>
                        </td>
                        {% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}
                        <td style="text-align: center;" class="no-print"><a href="/edit/transactions/{{ t.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;">✏️</a> <br> <a href="/delete/transactions/{{ t.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Move to Trash?');">🗑️</a></td>
                        {% endif %}
                    </tr>{% else %}<tr><td colspan="6" style="text-align: center; color: #9ca3af; padding: 40px 0;">No entries matching criteria.</td></tr>{% endfor %}
                    </tbody>
                </table>
                <div class="pagination-controls no-print">
                    <button class="btn btn-outline btn-sm" onclick="prevPayments()">← Previous</button>
                    <span id="payment-page-info" style="font-size: 0.9em; font-weight: 500;">Page 1</span>
                    <button class="btn btn-outline btn-sm" onclick="nextPayments()">Next →</button>
                </div>
            </div>
        </div>
    </div>
    <!-- SPLIT SETTLEMENT FORM -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; margin-top: 15px; border-top: 2px dashed var(--border); padding-top: 15px;">
                <h3 style="margin:0; font-size: 1.3em; color: var(--primary);">🔀 Split Voucher / Settle Multiple Accounts</h3>
                <button class="btn" style="background: #0ea5e9;" onclick="toggleSplitMode()">➕ Open Split Settlement</button>
            </div>
            
            <div id="split-mode-section" style="display:none; background:#f0f9ff; padding: 15px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #bae6fd; overflow-x: auto;">
                <form action="/add_split_voucher" method="POST" id="splitForm" onsubmit="return validateSplitTotal()" style="min-width: 800px;">
                    <input type="hidden" name="source_page" value="{{ active_page }}">
                    
                    <!-- MASTER DETAILS -->
                    <div class="flex-row" style="margin-bottom:15px; background:white; padding:15px; border-radius:8px; border:1px solid #7dd3fc; align-items: flex-end;">
                        <div class="form-group flex-1" style="margin:0;"><label>Date</label><input type="date" name="date" class="auto-date" required></div>
                        <div class="form-group flex-1" style="margin:0;"><label>Time</label><input type="time" name="time" class="auto-time" required></div>
                        <div class="form-group flex-1" style="margin:0;"><label>Mode</label><select name="payment_mode" required><option value="Cash">Cash</option><option value="Online">Online</option></select></div>
                        <div class="form-group flex-1" style="margin:0;">
                            <label style="color:#92400e;">Approved By</label>
                            <select name="approved_by_select" style="border-color: var(--warning); background:white;">
                                <option value="">-- Pending / None --</option>
                                {% for u in approver_names %}<option value="{{ u }}">{{ u }}</option>{% endfor %}
                            </select>
                        </div>
                        <div class="form-group flex-2" style="margin:0; flex:2;"><label>Master Description / Bill No.</label><input type="text" name="master_description" required placeholder="e.g. Bulk Cement Purchase"></div>
                        <div class="form-group flex-1" style="margin:0;">
                            <label style="color:var(--danger);">Total Amount (₹) <small>(Auto)</small></label>
                            <input type="text" id="master_amount_display" readonly value="0.00" style="border-color:var(--danger); font-weight:bold; font-size:1.1em; background:#fef2f2; color:var(--danger);">
                            <input type="hidden" id="master_amount" name="master_amount" value="0">
                        </div>
                    </div>
                    
                    <!-- CALCULATOR HEADER -->
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; background:#e0f2fe; padding: 10px; border-radius: 6px;">
                        <strong style="color:#0369a1;">Allocate to Accounts:</strong>
                        <div style="font-size:1.1em; padding:5px 10px; background:white; border-radius:5px; border:1px solid #ccc; display: flex; gap: 15px;">
                            <span>Total (Auto): <strong id="calc_assigned" style="color:green;">₹0.00</strong></span>
                        </div>
                    </div>

                    <!-- SPLIT ROWS TABLE -->
                    <table style="width: 100%; border: none; background: white; margin-bottom: 10px; border-radius: 6px; overflow: hidden;">
                        <thead style="background: #bae6fd;">
                            <tr>
                                <th style="font-size: 0.85em; padding: 10px;">Voucher Nature</th>
                                <th style="font-size: 0.85em; padding: 10px;">Ledger Account</th>
                                <th style="font-size: 0.85em; padding: 10px;">Category</th>
                                <th style="font-size: 0.85em; padding: 10px; text-align: right;">Amount (₹)</th>
                                <th style="font-size: 0.85em; padding: 10px; text-align: center;">Act</th>
                            </tr>
                        </thead>
                        <tbody id="split-entry-body">
                        </tbody>
                    </table>
                    
                    <div style="display:flex; justify-content: space-between; margin-top: 15px;">
                        <button type="button" class="btn btn-outline" onclick="addSplitRow()" style="background:white;">+ Add Another Account</button>
                        <button class="btn btn-success" type="submit" id="saveSplitBtn" style="padding: 12px 30px; font-size: 1.1em;" disabled>💾 Save Split Voucher</button>
                    </div>
                </form>
            </div>
    <script>
        const approverOpts = `<option value="">-- Pending --</option>{% for u in approver_names %}<option value="{{u}}">{{u}}</option>{% endfor %}`;
        const accountOpts = `<option value="main">🏢 Main Book</option><optgroup label="👥 Persons">{% for p in persons %}<option value="person_{{ p.id }}">👤 {{ p.name }}</option>{% endfor %}</optgroup><optgroup label="💸 Dasti">{% for dp in dasti_persons %}<option value="dasti_{{ dp.id }}">💸 {{ dp.name }}</option>{% endfor %}</optgroup>`;
        const catOpts = `{% for c in categories %}<option value="{{c}}">{{c}}</option>{% endfor %}`;
        
        function addFastRow() {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="padding:5px;"><select name="txn_nature[]" required style="font-size:0.85em; padding:6px; font-weight:bold;"><option value="slip_in" style="color:red;">➖ Slip/Bill</option><option value="advance" style="color:blue;">📤 Advance</option><option value="receive_cash" style="color:green;">📥 Receive Cash</option></select></td>
                <td style="padding:5px;"><select name="primary_account[]" required style="font-size:0.85em; padding:6px; font-weight:bold;">${accountOpts}</select></td>
                <td style="padding:5px;"><select name="approved_by_select[]" style="font-size:0.85em; padding:6px;">${approverOpts}</select></td>
                <td style="padding:5px;"><select name="category[]" required style="font-size:0.85em; padding:6px;">${catOpts}</select></td>
                <td style="padding:5px;"><input type="text" name="description[]" required style="font-size:0.85em; padding:6px;"></td>
                <td style="padding:5px;"><input type="number" step="0.01" min="0" name="amount[]" value="0" required style="font-size:0.85em; padding:6px;"></td>
                <td style="padding:5px; text-align:center;"><button type="button" onclick="this.closest('tr').remove()" style="background:var(--danger); padding:4px 8px;">X</button></td>
            `;
            document.getElementById('fast-entry-body').appendChild(tr);
        }

        function toggleFastMode() {
            const fm = document.getElementById('fast-mode-section');
            const bm = document.getElementById('batch-mode-section');
            if(fm.style.display === 'none') {
                fm.style.display = 'block';
                bm.style.display = 'none';
                setAutoDateTime();
                if(document.getElementById('fast-entry-body').children.length === 0) addFastRow();
            } else {
                fm.style.display = 'none';
                bm.style.display = 'block';
            }
        }
        
        let currentReceiptPage = 1;
        let currentPaymentPage = 1;
        const rowsPerPage = 10;

        function renderTable(tableId, page, spanId) {
            const tbody = document.getElementById(tableId);
            if(!tbody) return page;
            const rows = Array.from(tbody.getElementsByTagName('tr'));
            
            const totalPages = Math.max(1, Math.ceil(rows.length / rowsPerPage));
            if(page < 1) page = 1;
            if(page > totalPages) page = totalPages;
            
            rows.forEach((row, index) => {
                if(index >= (page-1)*rowsPerPage && index < page*rowsPerPage) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
            const infoSpan = document.getElementById(spanId);
            if(infoSpan) infoSpan.innerText = `Page ${page} of ${totalPages}`;
            return page;
        }

        function prevReceipts() { currentReceiptPage = renderTable('receipts-tbody', currentReceiptPage - 1, 'receipt-page-info'); }
        function nextReceipts() { currentReceiptPage = renderTable('receipts-tbody', currentReceiptPage + 1, 'receipt-page-info'); }
        function prevPayments() { currentPaymentPage = renderTable('payments-tbody', currentPaymentPage - 1, 'payment-page-info'); }
        function nextPayments() { currentPaymentPage = renderTable('payments-tbody', currentPaymentPage + 1, 'payment-page-info'); }

        document.addEventListener("DOMContentLoaded", function() {
            renderTable('receipts-tbody', 1, 'receipt-page-info');
            renderTable('payments-tbody', 1, 'payment-page-info');
            setAutoDateTime();
        });
        function toggleSplitMode() {
            const sm = document.getElementById('split-mode-section');
            const bm = document.getElementById('batch-mode-section');
            if(sm.style.display === 'none') {
                sm.style.display = 'block';
                bm.style.display = 'none';
                setAutoDateTime();
                // Add 2 blank rows by default
                if(document.getElementById('split-entry-body').children.length === 0) { addSplitRow(); addSplitRow(); }
            } else {
                sm.style.display = 'none';
                bm.style.display = 'block';
            }
        }

        function addSplitRow() {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="padding:8px;"><select name="txn_nature[]" required style="font-size:0.9em; padding:8px; font-weight:bold;"><option value="slip_in" style="color:red;">➖ Slip/Bill (Debit)</option><option value="advance" style="color:blue;">📤 Advance (Credit)</option><option value="receive_cash" style="color:green;">📥 Receive Cash (Credit)</option></select></td>
                <td style="padding:8px;"><select name="primary_account[]" required style="font-size:0.9em; padding:8px; font-weight:bold;">${accountOpts}</select></td>
                <td style="padding:8px;"><select name="category[]" required style="font-size:0.9em; padding:8px;">${catOpts}</select></td>
                <td style="padding:8px;"><input type="number" step="0.01" min="0" name="split_amount[]" class="split-amt-input" value="0" required style="font-size:0.9em; padding:8px; font-weight:bold; text-align:right;" onkeyup="updateSplitCalc()" onchange="updateSplitCalc()"></td>
                <td style="padding:8px; text-align:center;"><button type="button" onclick="this.closest('tr').remove(); updateSplitCalc();" style="background:var(--danger); color:white; padding:6px 12px; border:none; border-radius:4px; cursor:pointer; font-weight:bold;">X</button></td>
            `;
            document.getElementById('split-entry-body').appendChild(tr);
        }

        function updateSplitCalc() {
            let assigned = 0;
            document.querySelectorAll('.split-amt-input').forEach(inp => {
                assigned += (parseFloat(inp.value) || 0);
            });
            document.getElementById('calc_assigned').innerText = '₹' + assigned.toFixed(2);
            let displayEl = document.getElementById('master_amount_display');
            if (displayEl) displayEl.value = assigned.toFixed(2);
            document.getElementById('master_amount').value = assigned.toFixed(2);

            document.getElementById('saveSplitBtn').disabled = assigned <= 0;
        }

        function validateSplitTotal() {
            let assigned = 0;
            document.querySelectorAll('.split-amt-input').forEach(inp => { assigned += (parseFloat(inp.value) || 0); });
            if (assigned <= 0) {
                alert("Please enter at least one account amount greater than zero.");
                return false;
            }
            return true;
        }

        function validateSplitTotal() {
            let masterAmt = parseFloat(document.getElementById('master_amount').value) || 0;
            let assigned = 0;
            document.querySelectorAll('.split-amt-input').forEach(inp => { assigned += (parseFloat(inp.value) || 0); });
            if (Math.abs(masterAmt - assigned) > 0.01) {
                alert("Cannot Save! The sum of individual accounts must exactly match the Total Master Amount.");
                return false;
            }
            return true;
        }
    </script>
    
</body></html>'''

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

        {% if session.get('can_view_ledger_details') == 1 or session.get('role') == 'superadmin' %}
        {% if show_ledger_entries %}
        <div class="card" style="padding: 0; overflow-x: auto;">
          
        </div>
        {% else %}
        <div class="card" style="padding: 40px; text-align: center; color: #6b7280; font-style: italic;">
            <div style="font-size: 2em; margin-bottom: 10px;"></div>
            
        </div>
        {% endif %}
        <div class="card" style="padding: 0; overflow-x: auto;">
            <div style="padding: 15px 25px; background: #f8fafc; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                <h3 style="margin: 0;">Detailed Transaction History</h3>
                <div style="display: flex; gap: 10px;">
                    <button type="button" class="btn btn-sm btn-outline" onclick="filterLedger('all')">📜 All Entries</button>
                    <button type="button" class="btn btn-sm" style="background: #e0e7ff; color: #3730a3;" onclick="filterLedger('in')">📥 Advance Given (+)</button>
                    <button type="button" class="btn btn-sm" style="background: #d1fae5; color: #065f46;" onclick="filterLedger('out')">📤 Slip Settled (-)</button>
                </div>
            </div>
            
            <form action="/bulk_delete" method="POST" onsubmit="return confirm('Are you sure you want to delete the selected entries?');">
                <div style="padding: 10px 25px; background: #fffbeb; border-bottom: 1px solid var(--border);">
                    <button type="submit" class="btn btn-danger btn-sm">🗑️ Delete Selected Entries</button>
                </div>
                <table style="width: 100%; min-width: 900px;">
                    <thead><tr>
                        <th style="padding-left: 25px; width: 40px;"><input type="checkbox" onclick="let cb = document.getElementsByName('selected_links'); for(let i=0;i<cb.length;i++) cb[i].checked = this.checked;" style="width:16px; height:16px; cursor:pointer;"></th>
                        <th style="width: 5%;">Sr.</th>
                        <th style="width: 15%;">Date & Time</th><th style="width: 15%;">Mode/Category</th><th style="width: 40%;">Bill No / Details & Link</th><th style="text-align: right; width: 10%;">Amount</th>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<th style="text-align: center; width: 10%;">Act</th>{% endif %}
                    </tr></thead>
                    <tbody>
                        {% for txn in txns %}
                        <tr class="ledger-row" data-type="{% if txn.type == 'advance' %}in{% else %}out{% endif %}">
                            <td style="padding-left: 25px;"><input type="checkbox" name="selected_links" value="{{ txn.link_id }}" style="width:16px; height:16px; cursor:pointer;"></td>
                            <td style="font-weight: bold; color: #64748b;">{{ loop.index }}</td>
                            <td><span style="font-weight: 500;">{{ txn.date }}</span><br><span style="color: #6b7280; font-size: 0.85em;">{{ txn.time }}</span></td>
                            <td><span class="badge badge-mode">{{ txn.payment_mode }}</span><br><span style="font-size: 0.85em; color: #4b5563;">{{ txn.category }}</span></td>
                            <td style="white-space: pre-wrap;">{{ txn.description }}
                                {% if txn.status == 'approved' and txn.approved_by %}<br><span style="color: var(--success); font-size: 0.85em; font-weight: 600;">✓ Apprv: {{ txn.approved_by }}</span>{% endif %}
                            </td>
                            <td style="text-align: right;">
                                {% if txn.status == 'pending' %}<span class="badge badge-pending">⏳ Pending</span><br>{% endif %}
                                {% if txn.type == 'advance' %}<span class="badge badge-in" style="background:#e0e7ff; color:#3730a3;">+ ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>(Advance)</small></span>
                                {% else %}<span class="badge badge-out" style="background:#d1fae5; color:#065f46;">- ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>(Slip / Settle)</small></span>{% endif %}
                            </td>
                            {% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}
                            <td style="text-align: center;"><a href="/edit/person_ledger/{{ txn.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;">✏️</a> <br> <a href="/delete/person_ledger/{{ txn.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Move to Trash?');">🗑️</a></td>
                            {% endif %}
                        </tr>{% else %}<tr><td colspan="7" style="text-align:center; color:#9ca3af; padding: 40px;">No historical entries found for this person.</td></tr>{% endfor %}
                    </tbody>
                </table>
            </form>
        </div>
        {% else %}
        <div class="card" style="padding: 40px; text-align: center; color: #6b7280; font-style: italic;">
            <div style="font-size: 2em; margin-bottom: 10px;">🔒</div>
            Detailed ledger entries are hidden.<br>Your account only has permission to view overall balances.<br>Contact your Administrator to request detailed access.
        </div>
        {% endif %}

    </div></body></html>'''


TRASH_TEMPLATE = '''<!DOCTYPE html><html><head><title>Trash / Recycle Bin</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        <div class="card" style="padding: 0;">
            <h3 style="padding: 15px 20px; margin: 0; background: #fee2e2; border-bottom: 1px solid var(--border); font-size: 1.2em; color: #991b1b;">🗑️ Deleted Vouchers & Entries (Trash)</h3>
            <form method="POST">
                <div style="padding: 10px 25px; background: #fffbeb; border-bottom: 1px solid var(--border); display: flex; gap: 10px;">
                    <button type="submit" formaction="/bulk_restore_trash" class="btn btn-success btn-sm" onclick="return confirm('Restore selected entries?');">♻️ Restore Selected</button>
                    <button type="submit" formaction="/bulk_hard_delete_trash" class="btn btn-sm" style="background:#dc2626; color:white;" onclick="return confirm('Permanently delete selected? This cannot be undone.');">🔥 Delete Selected Forever</button>
                </div>
                <table style="width: 100%; border: none;"><tr><th style="padding-left: 20px; width: 40px;"><input type="checkbox" onclick="let cb = document.getElementsByName('selected_links'); for(let i=0;i<cb.length;i++) cb[i].checked = this.checked;" style="width:16px; height:16px; cursor:pointer;"></th><th>Date & Time</th><th>Category / Detail</th><th style="text-align: right;">Amount</th><th style="text-align: center;">Action</th></tr>
                    {% for t in trashed %}<tr>
                        <td style="padding-left: 20px;"><input type="checkbox" name="selected_links" value="{{ t.link_id }}" style="width:16px; height:16px; cursor:pointer;"></td>
                        <td><span style="font-weight: 500;">{{ t.date }}</span><br><span style="font-size: 0.85em; color: #6b7280;">{{ t.time }}</span></td>
                        <td><span class="badge badge-mode">{{ t.category }}</span><br><span style="white-space: pre-wrap;">{{ t.description }}</span></td>
                        <td style="text-align: right;"><strong>₹{{ "{:,.2f}".format(t.amount) }}</strong></td>
                        <td style="text-align: center;">
                            <a href="/restore_voucher/{{ t.link_id }}" class="btn btn-sm btn-success" onclick="return confirm('Restore this transaction?');">♻️</a>
                            <a href="/hard_delete_voucher/{{ t.link_id }}" class="btn btn-sm" style="background:#dc2626; color:white; margin-left:5px;" onclick="return confirm('Permanently delete? This cannot be undone.');">🔥</a>
                        </td>
                    </tr>{% else %}<tr><td colspan="5" style="text-align:center; color:#9ca3af; padding: 40px;">Trash is empty.</td></tr>{% endfor %}
                </table>
            </form>
        </div>
    </div></body></html>'''

BULK_EDIT_DATE_TEMPLATE = '''<!DOCTYPE html><html><head><title>Bulk Date Correction</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        <div class="card">
            <h3 style="margin-top: 0; color: var(--primary);">📅 Search & Bulk Update Dates</h3>
            <form action="/bulk_edit_date" method="POST" style="display: flex; gap: 15px; align-items: flex-end; flex-wrap: wrap;">
                <input type="hidden" name="action" value="search">
                <div class="form-group flex-1" style="min-width: 130px;"><label>From Date</label><input type="date" name="start_date" value="{{ start_date }}" required></div>
                <div class="form-group flex-1" style="min-width: 130px;"><label>To Date</label><input type="date" name="end_date" value="{{ end_date }}" required></div>
                <div class="form-group flex-1" style="min-width: 130px;"><label>Amount (Opt)</label><input type="number" step="0.01" name="search_amount" value="{{ search_amount }}" placeholder="Exact ₹"></div>
                <div class="form-group flex-2" style="min-width: 180px; flex: 2;"><label>Detail / Desc (Opt)</label><input type="text" name="search_desc" value="{{ search_desc }}" placeholder="Search text..."></div>
                <button class="btn" style="background:indigo; height: 45px; padding: 10px 25px;" type="submit">🔍 Search</button>
            </form>
        </div>
        
        {% if has_searched %}
        <div class="card" style="padding: 0;">
            <form action="/bulk_edit_date" method="POST" onsubmit="return confirm('Are you sure you want to change the date for ALL selected entries?');">
                <input type="hidden" name="action" value="update_dates">
                
                <div style="padding: 15px 20px; background: #fffbeb; border-bottom: 1px solid var(--border); display: flex; flex-direction: column; gap: 15px;">
                    <div style="display: flex; gap: 15px; align-items: flex-end; flex-wrap: wrap;">
                        <div class="form-group" style="margin-bottom: 0; min-width: 250px;">
                            <label style="color:#92400e;">Set New Date For Selected Entries:</label>
                            <input type="date" name="new_date" required style="border-color: var(--warning); font-weight:bold; background: white;">
                        </div>
                        <button type="submit" class="btn btn-warning" style="height: 43px; padding: 0 25px;">✏️ Update Selected Dates</button>
                    </div>

                    <!-- DYNAMIC SUMMARY BAR -->
                    <div style="display: flex; flex-wrap: wrap; gap: 20px; align-items: center; background: #fef3c7; padding: 10px 15px; border-radius: 8px; border: 1px solid #fde68a;">
                        <div style="display: flex; flex-direction: column; min-width: 150px;">
                            <span style="color:#92400e; font-weight:bold; font-size: 0.9em;">Entries Selected</span>
                            <strong id="calc-count" style="font-size: 1.3em;">0</strong>
                        </div>
                        <div style="display: flex; flex-direction: column; min-width: 150px;">
                            <span style="color: var(--success); font-weight:bold; font-size: 0.9em;">Total Positive (+)</span>
                            <strong id="calc-positive" style="font-size: 1.3em;">₹0.00</strong>
                        </div>
                        <div style="display: flex; flex-direction: column; min-width: 150px;">
                            <span style="color: var(--danger); font-weight:bold; font-size: 0.9em;">Total Negative (-)</span>
                            <strong id="calc-negative" style="font-size: 1.3em;">₹0.00</strong>
                        </div>

                        <!-- TARGET MATCH INPUTS -->
                        <div style="display: flex; gap: 10px; margin-left: auto; background: white; padding: 8px; border-radius: 6px; border: 1px dashed #d1d5db;">
                            <div class="form-group" style="margin: 0;">
                                <label style="font-size: 0.75em; color: var(--success);">Target Match (+)</label>
                                <input type="number" id="target-pos" placeholder="e.g. 5000" onkeyup="calculateSelection()" onchange="calculateSelection()" style="padding: 4px; width: 100px; font-size: 0.9em; border-color: var(--success);">
                            </div>
                            <div class="form-group" style="margin: 0;">
                                <label style="font-size: 0.75em; color: var(--danger);">Target Match (-)</label>
                                <input type="number" id="target-neg" placeholder="e.g. 1200" onkeyup="calculateSelection()" onchange="calculateSelection()" style="padding: 4px; width: 100px; font-size: 0.9em; border-color: var(--danger);">
                            </div>
                        </div>
                    </div>
                </div>
                
                <table style="width: 100%; border: none;">
                    <tr>
                        <th style="padding-left: 20px; width: 40px;">
                            <input type="checkbox" id="master-checkbox" onclick="toggleAllCheckboxes(this)" style="width:16px; height:16px; cursor:pointer;">
                        </th>
                        <th>Current Date & Time</th>
                        <th>Category / Detail</th>
                        <th style="text-align: right; padding-right: 20px;">Amount</th>
                        <th style="text-align: center;">Act</th>
                    </tr>
                    {% for t in results %}
                    <tr>
                        <td style="padding-left: 20px;">
                            <input type="checkbox" name="selected_links" class="row-checkbox" value="{{ t.link_id }}" 
                                   data-amount="{{ t.amount }}" 
                                   data-txn-type="{% if t.type in ['expense', 'dasti_out', 'batch_ledger_out', 'dasti_voucher_out', 'advance'] %}out{% else %}in{% endif %}" 
                                   data-desc="{{ t.get('description', '') | replace('\"', '&quot;') | replace('\n', ' ') }}"
                                   onchange="calculateSelection()" 
                                   style="width:16px; height:16px; cursor:pointer;">
                        </td>
                        <td><span style="font-weight: 500;">{{ t.date }}</span><br><span style="font-size: 0.85em; color: #6b7280;">{{ t.time }}</span></td>
                        <td><span class="badge badge-mode">{{ t.category }}</span><br><span style="white-space: pre-wrap;">{{ t.get('description', '') }}</span></td>
                        <td style="text-align: right; padding-right: 20px;">
                            {% if t.type in ['expense', 'dasti_out', 'batch_ledger_out', 'dasti_voucher_out', 'advance'] %}
                                <strong style="color:red;">- ₹{{ "{:,.2f}".format(t.amount | default(0)) }}</strong>
                            {% else %}
                                <strong style="color:green;">+ ₹{{ "{:,.2f}".format(t.amount | default(0)) }}</strong>
                            {% endif %}
                        </td>
                        <td style="text-align: center;">
                            <a href="/edit/transactions/{{ t.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;" title="Edit this entry">✏️</a>
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="5" style="text-align:center; color:#9ca3af; padding: 40px;">No entries found matching criteria.</td></tr>
                    {% endfor %}
                </table>
                
                <!-- AI RECONCILIATION SUGGESTION PANEL -->
                <div id="suggestion-panel" style="margin: 20px; padding: 15px; background: #f0fdf4; border: 2px solid #86efac; border-radius: 8px; display: none;">
                    <h4 style="margin-top: 0; color: #166534; display: flex; align-items: center; gap: 8px;">🤖 Match Diagnostics</h4>
                    <div id="pos-suggestion" style="margin-bottom: 8px; font-size: 0.95em; color: #065f46;"></div>
                    <div id="neg-suggestion" style="font-size: 0.95em; color: #991b1b;"></div>
                </div>

            </form>
        </div>
        
        <script>
            function toggleAllCheckboxes(masterCheckbox) {
                let checkboxes = document.querySelectorAll('.row-checkbox');
                checkboxes.forEach(cb => cb.checked = masterCheckbox.checked);
                calculateSelection();
            }

            function calculateSelection() {
                let checkboxes = document.querySelectorAll('.row-checkbox');
                let count = 0;
                let totalPositive = 0;
                let totalNegative = 0;

                let selectedPos = []; let unselectedPos = [];
                let selectedNeg = []; let unselectedNeg = [];

                checkboxes.forEach(cb => {
                    let amount = parseFloat(cb.getAttribute('data-amount')) || 0;
                    let type = cb.getAttribute('data-txn-type');
                    
                    if (cb.checked) {
                        count++;
                        if (type === 'in') { totalPositive += amount; selectedPos.push(cb); }
                        else { totalNegative += amount; selectedNeg.push(cb); }
                    } else {
                        if (type === 'in') { unselectedPos.push(cb); }
                        else { unselectedNeg.push(cb); }
                    }
                });

                let fmt = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' });
                document.getElementById('calc-count').innerText = count;
                document.getElementById('calc-positive').innerText = fmt.format(totalPositive).replace('₹', '₹');
                document.getElementById('calc-negative').innerText = fmt.format(totalNegative).replace('₹', '₹');

                let targetPosRaw = document.getElementById('target-pos').value;
                let targetNegRaw = document.getElementById('target-neg').value;
                let targetPos = parseFloat(targetPosRaw) || 0;
                let targetNeg = parseFloat(targetNegRaw) || 0;
                
                let panel = document.getElementById('suggestion-panel');
                let pSugg = document.getElementById('pos-suggestion');
                let nSugg = document.getElementById('neg-suggestion');
                
                pSugg.innerHTML = "";
                nSugg.innerHTML = "";

                if (targetPosRaw !== "" || targetNegRaw !== "") {
                    panel.style.display = 'block';

                    if (targetPosRaw !== "") {
                        let diffPos = totalPositive - targetPos;
                        if (Math.abs(diffPos) < 0.01) {
                            pSugg.innerHTML = "<strong>Positive (+):</strong> ✅ Balances match perfectly!";
                        } else if (diffPos > 0) {
                            let matches = selectedPos.filter(cb => Math.abs(parseFloat(cb.dataset.amount) - diffPos) < 0.01);
                            if (matches.length > 0) {
                                pSugg.innerHTML = `<strong>Positive (+):</strong> You selected ₹${diffPos.toFixed(2)} too much. <br>💡 <strong>Suggestion: UNCHECK</strong> ➔ "${matches[0].dataset.desc}" (₹${diffPos.toFixed(2)})`;
                            } else {
                                pSugg.innerHTML = `<strong>Positive (+):</strong> You selected ₹${diffPos.toFixed(2)} too much. (No single selected voucher matches this exact amount).`;
                            }
                        } else {
                            let need = Math.abs(diffPos);
                            let matches = unselectedPos.filter(cb => Math.abs(parseFloat(cb.dataset.amount) - need) < 0.01);
                            if (matches.length > 0) {
                                pSugg.innerHTML = `<strong>Positive (+):</strong> You are short by ₹${need.toFixed(2)}. <br>💡 <strong>Suggestion: CHECK</strong> ➔ "${matches[0].dataset.desc}" (₹${need.toFixed(2)})`;
                            } else {
                                pSugg.innerHTML = `<strong>Positive (+):</strong> You are short by ₹${need.toFixed(2)}. (Consider creating a new entry for this exact amount).`;
                            }
                        }
                    }

                    if (targetNegRaw !== "") {
                        let diffNeg = totalNegative - targetNeg;
                        if (Math.abs(diffNeg) < 0.01) {
                            nSugg.innerHTML = "<strong>Negative (-):</strong> ✅ Balances match perfectly!";
                        } else if (diffNeg > 0) {
                            let matches = selectedNeg.filter(cb => Math.abs(parseFloat(cb.dataset.amount) - diffNeg) < 0.01);
                            if (matches.length > 0) {
                                nSugg.innerHTML = `<strong>Negative (-):</strong> You selected ₹${diffNeg.toFixed(2)} too much. <br>💡 <strong>Suggestion: UNCHECK</strong> ➔ "${matches[0].dataset.desc}" (₹${diffNeg.toFixed(2)})`;
                            } else {
                                nSugg.innerHTML = `<strong>Negative (-):</strong> You selected ₹${diffNeg.toFixed(2)} too much. (No single selected voucher matches this exact amount).`;
                            }
                        } else {
                            let need = Math.abs(diffNeg);
                            let matches = unselectedNeg.filter(cb => Math.abs(parseFloat(cb.dataset.amount) - need) < 0.01);
                            if (matches.length > 0) {
                                nSugg.innerHTML = `<strong>Negative (-):</strong> You are short by ₹${need.toFixed(2)}. <br>💡 <strong>Suggestion: CHECK</strong> ➔ "${matches[0].dataset.desc}" (₹${need.toFixed(2)})`;
                            } else {
                                nSugg.innerHTML = `<strong>Negative (-):</strong> You are short by ₹${need.toFixed(2)}. (Consider creating a new entry for this exact amount).`;
                            }
                        }
                    }
                } else {
                    panel.style.display = 'none';
                }
            }
        </script>
        {% endif %}
    </div>
</body></html>'''

MAIN_LEDGER_TEMPLATE = '''<!DOCTYPE html><html><head><title>Main Cash Book Ledger</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h2 style="margin: 0; font-size: 1.6em;">🏢 Main Cash Book Complete Ledger</h2>
        </div>
        <div class="stats-grid">
            <div class="stat-card" style="border-top: 4px solid var(--success);"><h4>Total Received (+ In)</h4><div class="value" style="color: var(--success);">+ ₹{{ "{:,.2f}".format(total_in) }}</div></div>
            <div class="stat-card" style="border-top: 4px solid var(--danger);"><h4>Total Payments & Advances (- Out)</h4><div class="value" style="color: var(--danger);">- ₹{{ "{:,.2f}".format(total_out + total_dasti + total_dasti_vouchers) }}</div></div>
            <div class="stat-card" style="border-top: 4px solid var(--primary); background: #f8fafc;"><h4>Available Balance</h4><div class="value">
                {% if balance >= 0 %}<span style="color: var(--success);">₹{{ "{:,.2f}".format(balance) }}</span>
                {% else %}<span style="color: var(--danger);">₹{{ "{:,.2f}".format(balance) }}</span>{% endif %}
            </div></div>
        </div>
        
        <div class="card" style="padding: 0; overflow-x: auto;">
            <div style="padding: 15px 25px; background: #f8fafc; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                <h3 style="margin: 0;">Detailed Transaction History</h3>
                <div style="display: flex; gap: 10px;">
                    <button type="button" class="btn btn-sm btn-outline" onclick="filterLedger('all')">📜 All Entries</button>
                    <button type="button" class="btn btn-sm" style="background: #d1fae5; color: #065f46;" onclick="filterLedger('in')">📥 Credit (In)</button>
                    <button type="button" class="btn btn-sm" style="background: #fee2e2; color: #991b1b;" onclick="filterLedger('out')">📤 Debit (Out)</button>
                </div>
            </div>
            
            <form action="/bulk_delete" method="POST" onsubmit="return confirm('Are you sure you want to delete the selected entries?');">
                <div style="padding: 10px 25px; background: #fffbeb; border-bottom: 1px solid var(--border);">
                    <button type="submit" class="btn btn-danger btn-sm">🗑️ Delete Selected Entries</button>
                </div>
                <table style="width: 100%; min-width: 900px;">
                    <thead><tr>
                        <th style="padding-left: 25px; width: 40px;"><input type="checkbox" onclick="let cb = document.getElementsByName('selected_links'); for(let i=0;i<cb.length;i++) cb[i].checked = this.checked;" style="width:16px; height:16px; cursor:pointer;"></th>
                        <th style="width: 5%;">Sr.</th>
                        <th style="width: 15%;">Date & Time</th><th style="width: 15%;">Mode/Category</th><th style="width: 40%;">Bill No / Details & Link</th><th style="text-align: right; width: 10%;">Amount</th>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<th style="text-align: center; width: 10%;">Act</th>{% endif %}
                    </tr></thead>
                    <tbody>
                        {% for txn in txns %}
                        <tr class="ledger-row" data-type="{% if txn.type in ['expense', 'dasti_out', 'batch_ledger_out', 'dasti_voucher_out'] %}out{% else %}in{% endif %}">
                            <td style="padding-left: 25px;"><input type="checkbox" name="selected_links" value="{{ txn.link_id }}" style="width:16px; height:16px; cursor:pointer;"></td>
                            <td style="font-weight: bold; color: #64748b;">{{ loop.index }}</td>
                            <td><span style="font-weight: 500;">{{ txn.date }}</span><br><span style="color: #6b7280; font-size: 0.85em;">{{ txn.time }}</span></td>
                            <td><span class="badge badge-mode">{{ txn.payment_mode }}</span><br><span style="font-size: 0.85em; color: #4b5563;">{{ txn.category }}</span></td>
                            <td style="white-space: pre-wrap;">{{ txn.description }}
                                {% if txn.status == 'approved' and txn.approved_by %}<br><span style="color: var(--success); font-size: 0.85em; font-weight: 600;">✓ Apprv: {{ txn.approved_by }}</span>{% endif %}
                            </td>
                            <td style="text-align: right;">
                                {% if txn.status == 'pending' %}<span class="badge badge-pending">⏳ Pending</span><br>{% endif %}
                                {% if txn.type in ['expense', 'dasti_out', 'batch_ledger_out', 'dasti_voucher_out'] %}<span class="badge badge-out">- ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>({% if txn.type == 'dasti_out' %}Transfer Out{% elif txn.type == 'batch_ledger_out' %}Ledger Slip Out{% elif txn.type == 'dasti_voucher_out' %}Dasti Advance Out{% else %}Payment Out{% endif %})</small></span>
                                {% else %}<span class="badge badge-in">+ ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>(Receipt/In)</small></span>{% endif %}
                            </td>
                            {% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}
                            <td style="text-align: center;"><a href="/edit/transactions/{{ txn.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;">✏️</a> <br> <a href="/delete/transactions/{{ txn.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Move to Trash?');">🗑️</a></td>
                            {% endif %}
                        </tr>{% else %}<tr><td colspan="7" style="text-align:center; color:#9ca3af; padding: 40px;">No entries found in Main Cash Book.</td></tr>{% endfor %}
                    </tbody>
                </table>
            </form>
        </div>
    </div>
    <script>
        function filterLedger(type) {
            const rows = document.querySelectorAll('.ledger-row');
            rows.forEach(row => {
                if (type === 'all' || row.dataset.type === type) row.style.display = '';
                else row.style.display = 'none';
            });
        }
    </script>
</body></html>'''


PERSONS_TEMPLATE = '''<!DOCTYPE html><html><head><title>Person Ledgers</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        <div class="card balance-card" style="margin-bottom: 25px;">
            <h2 style="color: #64748b; font-size: 1.1em; text-transform: uppercase; margin-bottom: 0;">🏢 Available Main Cash Book Balance</h2>
            <div class="balance-amount" style="color: {{ 'var(--success)' if balance >= 0 else 'var(--danger)' }}">₹{{ "{:,.2f}".format(balance) }}</div>
            
            <div style="display: flex; justify-content: center; gap: 20px; margin-top: 15px; flex-wrap: wrap;">
                <div style="color: #3730a3; background: #e0e7ff; padding: 10px 15px; border-radius: 8px; border: 1px solid #c7d2fe; min-width: 250px;">
                    <strong style="font-size: 0.85em; color: #4338ca; text-transform: uppercase;">👥 Total Person Balance (Outstanding)</strong><br>
                    <span style="font-size: 1.2em; font-weight: bold;">₹{{ "{:,.2f}".format(total_person_ledger) }}</span>
                </div>
            </div>
        </div>

        <div class="card" style="padding: 0;">

            <h3 style="padding: 15px 20px; margin: 0; background: #f8fafc; border-bottom: 1px solid var(--border); font-size: 1.2em;">📊 Outstanding Balances & Person Ledgers</h3>
            <table style="width: 100%; border: none;"><tr><th style="padding-left: 20px; font-size: 1em;">Name</th><th style="text-align: right; font-size: 1em;">Net Status</th><th style="text-align: center; width: 220px; padding-right: 20px; font-size: 1em;">Action</th></tr>
                {% for b in balances %}<tr>
                    <td style="padding-left: 20px; font-weight: 500; font-size: 1.1em;">{{ b.name }}</td>
                    <td style="text-align: right;">{% if b.net > 0 %}<span class="badge badge-primary" style="font-size: 1em; padding: 6px 12px; background: #e0e7ff; color: #3730a3; border-radius: 8px;">+ ₹{{ "{:,.2f}".format(b.net) }} (Owes Firm)</span>{% elif b.net < 0 %}<span class="badge badge-success" style="font-size: 1em; padding: 6px 12px; background: #d1fae5; color: #065f46; border-radius: 8px;">- ₹{{ "{:,.2f}".format(b.net|abs) }} (Firm Owes)</span>{% else %}<span style="color: #9ca3af; font-weight: 600;">✓ Settled</span>{% endif %}</td>
                    <td style="text-align: center; padding-right: 20px;">
                        <a href="/person_account/{{ b.id }}" class="btn btn-outline btn-sm">View</a>
                        {% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}
                        <button onclick="let n=prompt('Edit Name:', '{{ b.name }}'); if(n) window.location='/edit_person/{{ b.id }}?name='+encodeURIComponent(n);" class="btn btn-sm" style="background:#f59e0b; color:white;">✏️</button>
                        <a href="/delete_person/{{ b.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Delete this person account?{% if b.net != 0 %}\n\n⚠️ This account has an outstanding balance of ₹{{ "{:,.2f}".format(b.net) }}. The account will be hidden but its transaction history is kept.{% endif %}');">🗑️</a>
                        {% endif %}
                    </td>
                </tr>{% else %}<tr><td colspan="3" style="text-align:center; color:#9ca3af; padding: 40px;">No active profiles. Create one from the Dashboard Batch Entry!</td></tr>{% endfor %}
            </table>
        </div>
    </div></body></html>'''
PERSON_ACCOUNT_TEMPLATE = '''<!DOCTYPE html><html><head><title>Account: {{ person.name }}</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;"><a href="/persons" class="btn-outline" style="text-decoration: none; padding: 8px 15px; border-radius: 8px; font-size: 0.9em;">← Back to Ledgers</a><h2 style="margin: 0; font-size: 1.6em;">Person Ledger: <span style="color: var(--primary);">{{ person.name }}</span></h2></div>
        <div class="stats-grid">
            <div class="stat-card" style="border-top: 4px solid var(--primary);"><h4>Total Advances (Received from Main)</h4><div class="value" style="color: var(--primary);">+ ₹{{ "{:,.2f}".format(advances) }}</div></div>
            <div class="stat-card" style="border-top: 4px solid var(--success);"><h4>Total Slips / Settlements</h4><div class="value" style="color: var(--success);">- ₹{{ "{:,.2f}".format(settlements) }}</div></div>
            <div class="stat-card" style="border-top: 4px solid #8b5cf6; background: #f8fafc;"><h4>Net Status</h4><div class="value">{% if balance > 0 %}<span style="color: var(--primary);">+ ₹{{ "{:,.2f}".format(balance) }}<br><small style="font-size: 0.5em; color: #4b5563; text-transform: uppercase;">Owes Firm</small></span>{% elif balance < 0 %}<span style="color: var(--success);">- ₹{{ "{:,.2f}".format(balance|abs) }}<br><small style="font-size: 0.5em; color: #4b5563; text-transform: uppercase;">Firm Owes</small></span>{% else %}<span style="color: #6b7280; font-size: 0.9em;">Fully Settled</span>{% endif %}</div></div>
        </div>

        {% if show_ledger_entries %}
        <div class="card" style="padding: 0; overflow-x: auto;">
            <div style="padding: 15px 25px; background: #f8fafc; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                <h3 style="margin: 0;">Detailed Transaction History</h3>
                <div style="display: flex; gap: 10px;">
                    <button type="button" class="btn btn-sm btn-outline" onclick="filterLedger('all')">📜 All Entries</button>
                    <button type="button" class="btn btn-sm" style="background: #e0e7ff; color: #3730a3;" onclick="filterLedger('in')">📥 Advance Given (+)</button>
                    <button type="button" class="btn btn-sm" style="background: #d1fae5; color: #065f46;" onclick="filterLedger('out')">📤 Slip Settled (-)</button>
                </div>
            </div>

            <form action="/bulk_delete" method="POST" onsubmit="return confirm('Are you sure you want to delete the selected entries?');">
                <div style="padding: 10px 25px; background: #fffbeb; border-bottom: 1px solid var(--border);">
                    <button type="submit" class="btn btn-danger btn-sm">🗑️ Delete Selected Entries</button>
                </div>
                <table style="width: 100%; min-width: 900px;">
                    <thead><tr>
                        <th style="padding-left: 25px; width: 40px;"><input type="checkbox" onclick="let cb = document.getElementsByName('selected_links'); for(let i=0;i<cb.length;i++) cb[i].checked = this.checked;" style="width:16px; height:16px; cursor:pointer;"></th>
                        <th style="width: 5%;">Sr.</th>
                        <th style="width: 15%;">Date & Time</th><th style="width: 15%;">Mode/Category</th><th style="width: 40%;">Bill No / Details & Link</th><th style="text-align: right; width: 10%;">Amount</th>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<th style="text-align: center; width: 10%;">Act</th>{% endif %}
                    </tr></thead>
                    <tbody>
                        {% for txn in txns %}
                        <tr class="ledger-row" data-type="{% if txn.type == 'advance' %}in{% else %}out{% endif %}">
                            <td style="padding-left: 25px;"><input type="checkbox" name="selected_links" value="{{ txn.link_id }}" style="width:16px; height:16px; cursor:pointer;"></td>
                            <td style="font-weight: bold; color: #64748b;">{{ loop.index }}</td>
                            <td><span style="font-weight: 500;">{{ txn.date }}</span><br><span style="color: #6b7280; font-size: 0.85em;">{{ txn.time }}</span></td>
                            <td><span class="badge badge-mode">{{ txn.payment_mode }}</span><br><span style="font-size: 0.85em; color: #4b5563;">{{ txn.category }}</span></td>
                            <td style="white-space: pre-wrap;">{{ txn.description }}
                                {% if txn.status == 'approved' and txn.approved_by %}<br><span style="color: var(--success); font-size: 0.85em; font-weight: 600;">✓ Apprv: {{ txn.approved_by }}</span>{% endif %}
                            </td>
                            <td style="text-align: right;">
                                {% if txn.status == 'pending' %}<span class="badge badge-pending">⏳ Pending</span><br>{% endif %}
                                {% if txn.type == 'advance' %}<span class="badge badge-in" style="background:#e0e7ff; color:#3730a3;">+ ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>(Advance)</small></span>
                                {% else %}<span class="badge badge-out" style="background:#d1fae5; color:#065f46;">- ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>(Slip / Settle)</small></span>{% endif %}
                            </td>
                            {% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}
                            <td style="text-align: center;"><a href="/edit/person_ledger/{{ txn.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;">✏️</a> <br> <a href="/delete/person_ledger/{{ txn.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Move to Trash?');">🗑️</a></td>
                            {% endif %}
                        </tr>{% else %}<tr><td colspan="7" style="text-align:center; color:#9ca3af; padding: 40px;">No historical entries found for this person.</td></tr>{% endfor %}
                    </tbody>
                </table>
            </form>
        </div>
        {% else %}
        <div class="card" style="padding: 40px; text-align: center; color: #6b7280; font-style: italic;">
            <div style="font-size: 2em; margin-bottom: 10px;"></div>
            
        {% endif %}
    </div>
    <script>
        function filterLedger(type) {
            const rows = document.querySelectorAll('.ledger-row');
            rows.forEach(row => {
                if (type === 'all' || row.dataset.type === type) row.style.display = '';
                else row.style.display = 'none';
            });
        }
    </script>
</body></html>'''


DASTI_LEDGER_TEMPLATE = '''<!DOCTYPE html><html><head><title>Dasti Ledger</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        
        <div class="card balance-card" style="margin-bottom: 25px;">
            <h2 style="color: #64748b; font-size: 1.1em; text-transform: uppercase; margin-bottom: 0;">🏢 Available Main Cash Book Balance</h2>
            <div class="balance-amount" style="color: {{ 'var(--success)' if balance >= 0 else 'var(--danger)' }}">₹{{ "{:,.2f}".format(balance) }}</div>
            
            <div style="display: flex; justify-content: center; gap: 20px; margin-top: 15px; flex-wrap: wrap;">
                <div style="color: #0369a1; background: #e0f2fe; padding: 10px 15px; border-radius: 8px; border: 1px solid #bae6fd; min-width: 250px;">
                    <strong style="font-size: 0.85em; color: #0284c7; text-transform: uppercase;">💸 Total Dasti Balance (Outstanding)</strong><br>
                    <span style="font-size: 1.2em; font-weight: bold;">₹{{ "{:,.2f}".format(total_outstanding_dasti) }}</span>
                </div>
            </div>
        </div>

        <div class="card no-print" style="padding: 0;">
            <h3 style="padding: 15px 20px; margin: 0; background: #f8fafc; border-bottom: 1px solid var(--border); font-size: 1.2em;">📊 Outstanding Dasti Accounts</h3>
            <table style="width: 100%; border: none;"><tr><th style="padding-left: 20px; font-size: 1em;">Dasti Name</th><th style="text-align: right; font-size: 1em;">Net Status</th><th style="text-align: center; width: 220px; padding-right: 20px; font-size: 1em;">Action</th></tr>
                {% for b in balances %}<tr>
                    <td style="padding-left: 20px; font-weight: 500; font-size: 1.1em;">{{ b.name }}</td>
                    <td style="text-align: right;">{% if b.net > 0 %}<span class="badge badge-primary" style="font-size: 1em; padding: 6px 12px; background: #e0f2fe; color: #0369a1; border-radius: 8px;">+ ₹{{ "{:,.2f}".format(b.net) }} (Owes Firm)</span>{% elif b.net < 0 %}<span class="badge badge-success" style="font-size: 1em; padding: 6px 12px; background: #d1fae5; color: #065f46; border-radius: 8px;">- ₹{{ "{:,.2f}".format(b.net|abs) }} (Firm Owes)</span>{% else %}<span style="color: #9ca3af; font-weight: 600;">✓ Settled</span>{% endif %}</td>
                    <td style="text-align: center; padding-right: 20px;">
                        <a href="/dasti_account/{{ b.id }}" class="btn btn-outline btn-sm">View</a>
                        {% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}
                        <button onclick="let n=prompt('Edit Name:', '{{ b.name }}'); if(n) window.location='/edit_dasti_person/{{ b.id }}?name='+encodeURIComponent(n);" class="btn btn-sm" style="background:#f59e0b; color:white;">✏️</button>
                        <a href="/delete_dasti_person/{{ b.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Delete this Dasti account?{% if b.net != 0 %}\n\n⚠️ This account has an outstanding balance of ₹{{ "{:,.2f}".format(b.net) }}. The account will be hidden but its transaction history is kept.{% endif %}');">🗑️</a>
                        {% endif %}
                    </td>
                </tr>{% else %}<tr><td colspan="3" style="text-align:center; color:#9ca3af; padding: 40px;">No active Dasti accounts yet. Type a name in the Master Batch voucher to create one!</td></tr>{% endfor %}
            </table>
        </div>
    </div></body></html>'''
DASTI_ACCOUNT_TEMPLATE = '''<!DOCTYPE html><html><head><title>Dasti Account: {{ person.name }}</title>''' + BASE_STYLE + '''</head><body>
    <div class="container">''' + NAVBAR_HTML + '''
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;"><a href="/dasti_ledger" class="btn-outline" style="text-decoration: none; padding: 8px 15px; border-radius: 8px; font-size: 0.9em;">← Back to Dasti Ledgers</a><h2 style="margin: 0; font-size: 1.6em;">Dasti Ledger: <span style="color: #0ea5e9;">{{ person.name }}</span></h2></div>
        <div class="stats-grid">
            <div class="stat-card" style="border-top: 4px solid #0ea5e9;"><h4>Total Advances (Given Out)</h4><div class="value" style="color: #0ea5e9;">+ ₹{{ "{:,.2f}".format(advances) }}</div></div>
            <div class="stat-card" style="border-top: 4px solid var(--success);"><h4>Total Slips / Settlements</h4><div class="value" style="color: var(--success);">- ₹{{ "{:,.2f}".format(settlements) }}</div></div>
            <div class="stat-card" style="border-top: 4px solid #8b5cf6; background: #f8fafc;"><h4>Net Status</h4><div class="value">{% if balance > 0 %}<span style="color: #0ea5e9;">+ ₹{{ "{:,.2f}".format(balance) }}<br><small style="font-size: 0.5em; color: #4b5563; text-transform: uppercase;">Owes Firm</small></span>{% elif balance < 0 %}<span style="color: var(--success);">- ₹{{ "{:,.2f}".format(balance|abs) }}<br><small style="font-size: 0.5em; color: #4b5563; text-transform: uppercase;">Firm Owes</small></span>{% else %}<span style="color: #6b7280; font-size: 0.9em;">Fully Settled</span>{% endif %}</div></div>
        </div>

        {% if show_ledger_entries %}
        <div class="card" style="padding: 0; overflow-x: auto;">
            <div style="padding: 15px 25px; background: #f8fafc; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                <h3 style="margin: 0;">Detailed Transaction History</h3>
                <div style="display: flex; gap: 10px;">
                    <button type="button" class="btn btn-sm btn-outline" onclick="filterLedger('all')">📜 All Entries</button>
                    <button type="button" class="btn btn-sm" style="background: #e0f2fe; color: #0369a1;" onclick="filterLedger('in')">📥 Advance Given (+)</button>
                    <button type="button" class="btn btn-sm" style="background: #d1fae5; color: #065f46;" onclick="filterLedger('out')">📤 Slip Settled (-)</button>
                </div>
            </div>

            <form action="/bulk_delete" method="POST" onsubmit="return confirm('Are you sure you want to delete the selected entries?');">
                <div style="padding: 10px 25px; background: #fffbeb; border-bottom: 1px solid var(--border);">
                    <button type="submit" class="btn btn-danger btn-sm">🗑️ Delete Selected Entries</button>
                </div>
                <table style="width: 100%; min-width: 900px;">
                    <thead><tr>
                        <th style="padding-left: 25px; width: 40px;"><input type="checkbox" onclick="let cb = document.getElementsByName('selected_links'); for(let i=0;i<cb.length;i++) cb[i].checked = this.checked;" style="width:16px; height:16px; cursor:pointer;"></th>
                        <th style="width: 5%;">Sr.</th>
                        <th style="width: 15%;">Date & Time</th><th style="width: 15%;">Mode/Category</th><th style="width: 40%;">Dasti Detail & Link</th><th style="text-align: right; width: 10%;">Amount</th>{% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}<th style="text-align: center; width: 10%;">Act</th>{% endif %}
                    </tr></thead>
                    <tbody>
                        {% for txn in txns %}
                        <tr class="ledger-row" data-type="{% if txn.type == 'advance' %}in{% else %}out{% endif %}">
                            <td style="padding-left: 25px;"><input type="checkbox" name="selected_links" value="{{ txn.link_id }}" style="width:16px; height:16px; cursor:pointer;"></td>
                            <td style="font-weight: bold; color: #64748b;">{{ loop.index }}</td>
                            <td><span style="font-weight: 500;">{{ txn.date }}</span><br><span style="color: #6b7280; font-size: 0.85em;">{{ txn.time }}</span></td>
                            <td><span class="badge badge-mode">{{ txn.payment_mode }}</span><br><span style="font-size: 0.85em; color: #4b5563;">{{ txn.category }}</span></td>
                            <td style="white-space: pre-wrap;">{{ txn.description }}
                                {% if txn.status == 'approved' and txn.approved_by %}<br><span style="color: var(--success); font-size: 0.85em; font-weight: 600;">✓ Apprv: {{ txn.approved_by }}</span>{% endif %}
                            </td>
                            <td style="text-align: right;">
                                {% if txn.status == 'pending' %}<span class="badge badge-pending">⏳ Pending</span><br>{% endif %}
                                {% if txn.type == 'advance' %}<span class="badge badge-in" style="background:#e0f2fe; color:#0369a1;">+ ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>(Advance Given)</small></span>
                                {% else %}<span class="badge badge-out" style="background:#d1fae5; color:#065f46;">- ₹{{ "{:,.2f}".format(txn.amount) }} <br><small>(Slip / Settle)</small></span>{% endif %}
                            </td>
                            {% if session.get('can_edit') == 1 or session.get('role') == 'superadmin' %}
                            <td style="text-align: center;"><a href="/edit/dasti_ledger/{{ txn.id }}" class="btn btn-sm" style="background:#f59e0b;color:white;">✏️</a> <br> <a href="/delete/dasti_ledger/{{ txn.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Move to Trash?');">🗑️</a></td>
                            {% endif %}
                        </tr>{% else %}<tr><td colspan="7" style="text-align:center; color:#9ca3af; padding: 40px;">No historical entries found for this person.</td></tr>{% endfor %}
                    </tbody>
                </table>
            </form>
        </div>
        {% else %}
        <div class="card" style="padding: 40px; text-align: center; color: #6b7280; font-style: italic;">
            <div style="font-size: 2em; margin-bottom: 10px;">🔒</div>
            Individual entries are hidden by the admin's dashboard setting.<br>Totals above are still accurate.
        </div>
        {% endif %}
    </div>
    <script>
        function filterLedger(type) {
            const rows = document.querySelectorAll('.ledger-row');
            rows.forEach(row => {
                if (type === 'all' || row.dataset.type === type) row.style.display = '';
                else row.style.display = 'none';
            });
        }
    </script>
</body></html>'''


REGISTER_TEMPLATE = '''<!DOCTYPE html><html><head><title>Setup</title>''' + BASE_STYLE + '''</head><body><div class="container"><div class="card" style="max-width: 450px; margin: 80px auto; text-align: center;"><h2 style="color: var(--primary);">Setup Superadmin</h2><form action="/register" method="POST" style="text-align: left;"><div class="form-group"><label>Firm Name</label><input type="text" name="firm_name" required></div><div class="form-group"><label>Opening Cash Book Balance (₹)</label><input type="number" step="0.01" min="0" name="opening_balance" value="0" required></div><div class="form-group"><label>Superadmin Username</label><input type="text" name="username" required></div><div class="form-group"><label>Password</label><input type="password" name="password" required></div><button type="submit" style="width: 100%;">Initialize Firm Account</button></form></div></div></body></html>'''

LOGIN_TEMPLATE = '''<!DOCTYPE html><html><head><title>System 404</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
    body { background-color: #111; color: #0f0; font-family: monospace; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; overflow: hidden; flex-direction: column; transition: background 0.5s ease; touch-action: none; }
    .hud { display: flex; justify-content: space-between; align-items: center; width: 400px; max-width: 95vw; margin-bottom: 10px; font-size: 1.2em; font-weight: bold; }
    canvas { border: 2px solid #333; background-color: #000; box-shadow: 0 0 15px rgba(0, 255, 0, 0.2); max-width: 95vw; max-height: 50vh; }
    #login-container { display: none; position: absolute; z-index: 10; background: #ffffff; padding: 30px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); font-family: 'Poppins', sans-serif; color: #333; width: 350px; max-width: 90vw; }
    h2 { color: #4f46e5; margin-top: 0; text-align: center; }
    .form-group { margin-bottom: 15px; display: flex; flex-direction: column; }
    label { font-weight: 600; margin-bottom: 5px; font-size: 0.85em; color: #4b5563; }
    input { padding: 10px; border: 1px solid #ccc; border-radius: 8px; font-size: 1em; }
    button { background: #4f46e5; color: white; border: none; padding: 10px; font-weight: bold; border-radius: 8px; cursor: pointer; margin-top: 10px; width: 100%; font-size: 1em;}
    button:hover { background: #4338ca; }
    
    .controls { display: none; grid-template-columns: 60px 60px 60px; grid-template-rows: 60px 60px; gap: 10px; margin-top: 20px; justify-content: center; }
    .btn-ctrl { background: rgba(0, 255, 0, 0.2); border: 2px solid #0f0; color: #0f0; border-radius: 8px; font-size: 1.5em; display: flex; justify-content: center; align-items: center; user-select: none; }
    .btn-ctrl:active { background: rgba(0, 255, 0, 0.5); }
    .btn-up { grid-column: 2; grid-row: 1; }
    .btn-left { grid-column: 1; grid-row: 2; }
    .btn-down { grid-column: 2; grid-row: 2; }
    .btn-right { grid-column: 3; grid-row: 2; }
    @media (max-width: 768px) { .controls { display: grid; } }
    #game-over-msg { display: none; color: red; text-align: center; margin-top: 20px; font-size: 1.2em; font-family: 'Poppins', sans-serif; font-weight: bold; }
    
    {% if settings.game_enabled == 0 and not is_demo %}
    #game-wrapper { display: none !important; } 
    #login-container { display: block !important; position: static; margin: auto; }
    body { background-color: #f8fafc; }
    {% endif %}
</style>
</head><body>
    <div id="game-wrapper">
        {% if is_demo %}
        <div style="text-align:center; color:#fff; font-family:'Poppins', sans-serif; margin-bottom:10px;">
            <h3>🎮 Admin Demo Mode</h3>
            <p style="font-size: 0.8em; margin-top:-10px;">Test speed and unlock settings.</p>
        </div>
        {% endif %}
        <div class="hud">
            <div id="timeDisplay">Time: 0s</div>
            <div id="scoreDisplay">Score: 0 / {{ settings.blocks_to_eat }}</div>
        </div>
        <canvas id="gameCanvas" width="400" height="400"></canvas>
        <div id="game-over-msg">Game Over.<br>Refresh page to restart.</div>
        <div class="controls">
            <div class="btn-ctrl btn-up" id="btnUp">▲</div>
            <div class="btn-ctrl btn-left" id="btnLeft">◀</div>
            <div class="btn-ctrl btn-down" id="btnDown">▼</div>
            <div class="btn-ctrl btn-right" id="btnRight">▶</div>
        </div>
    </div>

    <div id="login-container">
        {% if is_demo %}
        <h2 style="color:var(--success);">✅ Demo Passed!</h2>
        <p style="text-align:center;">The game unlocked successfully with current settings.</p>
        <button onclick="window.close()" style="background:var(--success);">Close Demo</button>
        {% else %}
        <h2>System Access</h2>
        <form action="/login" method="POST">
            <div class="form-group"><label>Username</label><input type="text" name="username" required></div>
            <div class="form-group"><label>Password</label><input type="password" name="password" required></div>
            <button type="submit">Secure Login</button>
        </form>
        {% endif %}
    </div>

    <script>
        {% if settings.game_enabled != 0 or is_demo %}
        const canvas = document.getElementById('gameCanvas');
        const ctx = canvas.getContext('2d');
        const grid = 20;
        
        let speedMod = parseInt("{{ settings.game_speed }}") || 0;
        let delayMs = 100 - (speedMod * 10);
        if (delayMs < 20) delayMs = 20;
        if (delayMs > 500) delayMs = 500;
        let gameTimer;
        
        let snake = { x: 160, y: 160, dx: grid, dy: 0, cells: [], maxCells: 4 };
        let apple = { x: 320, y: 320 };
        
        let score = 0;
        let targetScore = parseInt("{{ settings.blocks_to_eat }}") || 4;
        let startTime = Math.floor(Date.now() / 1000);
        let isGameOver = false;
        let loginUnlocked = false;
        let loginLockedForever = false;
        
        let targetX = 0, targetY = 0;
        const targetCorner = "{{ settings.unlock_corner }}";
        if(targetCorner === 'br') { targetX = canvas.width - grid; targetY = canvas.height - grid; }
        else if(targetCorner === 'bl') { targetX = 0; targetY = canvas.height - grid; }
        else if(targetCorner === 'tr') { targetX = canvas.width - grid; targetY = 0; }
        else if(targetCorner === 'tl') { targetX = 0; targetY = 0; }

        function getRandomInt(min, max) { return Math.floor(Math.random() * (max - min)) + min; }

        function triggerGameOver() {
            isGameOver = true;
            clearTimeout(gameTimer);
            document.getElementById('game-over-msg').style.display = 'block';
        }

        function loop() {
            if (isGameOver) return; 
            gameTimer = setTimeout(loop, delayMs);
            
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            document.getElementById('timeDisplay').innerText = 'Time: ' + (Math.floor(Date.now() / 1000) - startTime) + 's';

            snake.x += snake.dx;
            snake.y += snake.dy;

            if (snake.x < 0) { snake.x = canvas.width - grid; } 
            else if (snake.x >= canvas.width) { snake.x = 0; }
            if (snake.y < 0) { snake.y = canvas.height - grid; } 
            else if (snake.y >= canvas.height) { snake.y = 0; }

            snake.cells.unshift({ x: snake.x, y: snake.y });
            if (snake.cells.length > snake.maxCells) snake.cells.pop();

            ctx.fillStyle = 'red';
            ctx.fillRect(apple.x, apple.y, grid - 1, grid - 1);

            ctx.fillStyle = '#0f0';
            snake.cells.forEach(function(cell, index) {
                ctx.fillRect(cell.x, cell.y, grid - 1, grid - 1);
                
                if (cell.x === apple.x && cell.y === apple.y) {
                    snake.maxCells++;
                    score++;
                    document.getElementById('scoreDisplay').innerText = 'Score: ' + score + ' / ' + targetScore;
                    
                    if (score === targetScore) { 
                        loginUnlocked = true; 
                    } else if (score === targetScore + 1) { 
                        loginUnlocked = false; 
                        loginLockedForever = true; 
                    }

                    apple.x = getRandomInt(0, 20) * grid;
                    apple.y = getRandomInt(0, 20) * grid;
                }
                
                for (let i = index + 1; i < snake.cells.length; i++) {
                    if (cell.x === snake.cells[i].x && cell.y === snake.cells[i].y) {
                        triggerGameOver(); return;
                    }
                }
            });

            if (snake.x === targetX && snake.y === targetY) {
                if (loginUnlocked && !loginLockedForever) {
                    isGameOver = true;
                    clearTimeout(gameTimer);
                    document.getElementById('game-wrapper').style.display = 'none';
                    document.getElementById('login-container').style.display = 'block';
                    document.body.style.background = '#f8fafc';
                }
            }
        }

        function setDir(dx, dy) {
            if(isGameOver) return;
            if (dx !== 0 && snake.dx === 0) { snake.dx = dx; snake.dy = dy; }
            else if (dy !== 0 && snake.dy === 0) { snake.dy = dy; snake.dx = dx; }
        }

        document.addEventListener('keydown', function(e) {
            if (e.which === 37) setDir(-grid, 0);
            else if (e.which === 38) setDir(0, -grid);
            else if (e.which === 39) setDir(grid, 0);
            else if (e.which === 40) setDir(0, grid);
        });

        document.getElementById('btnUp').addEventListener('touchstart', (e) => { e.preventDefault(); setDir(0, -grid); }, {passive: false});
        document.getElementById('btnDown').addEventListener('touchstart', (e) => { e.preventDefault(); setDir(0, grid); }, {passive: false});
        document.getElementById('btnLeft').addEventListener('touchstart', (e) => { e.preventDefault(); setDir(-grid, 0); }, {passive: false});
        document.getElementById('btnRight').addEventListener('touchstart', (e) => { e.preventDefault(); setDir(grid, 0); }, {passive: false});
        
        document.getElementById('btnUp').addEventListener('mousedown', (e) => { e.preventDefault(); setDir(0, -grid); });
        document.getElementById('btnDown').addEventListener('mousedown', (e) => { e.preventDefault(); setDir(0, grid); });
        document.getElementById('btnLeft').addEventListener('mousedown', (e) => { e.preventDefault(); setDir(-grid, 0); });
        document.getElementById('btnRight').addEventListener('mousedown', (e) => { e.preventDefault(); setDir(grid, 0); });

        loop();
        {% endif %}
    </script>
</body></html>'''

# --- FIREBASE HELPER LOGIC ---
def has_users():
    docs = db.collection('users').limit(1).stream()
    return any(True for _ in docs)

def get_categories(firm_id):
    docs = db.collection('categories').where('firm_id', '==', firm_id).stream()
    custom = [doc.to_dict().get('name') for doc in docs]
    return ['General', 'Sales', 'Purchase', 'Salary', 'Transport', 'Cleaning Expense', 'Computer goods', 'Electric goods', 'Food/Groceries', 'Hardware', 'Labour food', 'Repair Expense'] + custom

def get_approvers(firm_id):
    docs = db.collection('approvers').where('firm_id', '==', firm_id).stream()
    return [doc.to_dict().get('name') for doc in docs]

# --- ROUTES ---

@app.route('/')
def index():
    if not has_users(): return redirect(url_for('register'))
    if 'user_id' not in session: return redirect(url_for('login'))
    firm_id = session['firm_id']
    
    # Get active dashboard filter ('all', 'today', 'yesterday', 'week', 'month', 'year')
    time_filter = request.args.get('filter', 'all')
    
    persons = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('persons').where('user_id', '==', firm_id).stream()]
    persons.sort(key=lambda x: x.get('name', ''))
    
    dasti_persons = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('dasti_persons').where('user_id', '==', firm_id).stream()]
    dasti_persons.sort(key=lambda x: x.get('name', ''))
    
    all_txns = []
    for doc in db.collection('transactions').where('user_id', '==', firm_id).where('deleted', '==', 0).stream():
        data = doc.to_dict()
        if data.get('type') in ('split_expense', 'split_income'):
            continue
        all_txns.append({'id': doc.id, **data})
    # Apply Dashboard Sort Order from Global Settings
    settings = get_global_settings()
    is_desc = (settings.get('dashboard_sort_order', 'desc') == 'desc')
    all_txns.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=is_desc)

    # Summary calculations using proper IST timezone
    summary_txns = [t for t in all_txns if t.get('status') == 'approved']
    now = datetime.now(IST)
    today_str = now.strftime('%Y-%m-%d')
    yesterday_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    month_str = now.strftime('%Y-%m')
    year_str = now.strftime('%Y')
    week_ago_str = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    
    s_d_in = s_d_out = s_yest_in = s_yest_out = s_w_in = s_w_out = s_m_in = s_m_out = s_y_in = s_y_out = 0
    total_in_actual = 0
    total_out_actual = 0
    
    for r in summary_txns:
        amt, d, ttype = float(r.get('amount', 0)), r.get('date', ''), r.get('type', '')
        is_in = ttype in ('income', 'dasti_voucher_in')
        is_out = ttype in ('expense', 'dasti_out', 'dasti_voucher_out', 'batch_ledger_out')
        
        if is_in: total_in_actual += amt
        if is_out: total_out_actual += amt
            
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
        if d == yesterday_str:
            if is_in: s_yest_in += amt 
            elif is_out: s_yest_out += amt

    # --- PLACE THE PRINT STATEMENT HERE ---
    print(f"DEBUGGING BALANCE -> Total In: {total_in_actual}, Total Out: {total_out_actual}")

    main_balance = total_in_actual - total_out_actual

    
    # Filter Tables (Receipts/Payments) based on user selection
    # Filter Tables (Receipts/Payments) based on user selection
    # Filter Tables (Receipts/Payments) based on user selection
    # Filter Tables (Receipts/Payments) based on user selection
    incomes = []
    expenses = []
    
    for t in all_txns:
        d = t.get('date', '')
        if time_filter == 'today' and d != today_str: continue
        if time_filter == 'yesterday' and d != yesterday_str: continue
        if time_filter == 'week' and d < week_ago_str: continue
        if time_filter == 'month' and not d.startswith(month_str): continue
        if time_filter == 'year' and not d.startswith(year_str): continue
        
        t_type = t.get('type')
        show_all_linked = (settings.get('dashboard_ledger_visibility', 'main_only') == 'all')
        if t_type in ('income', 'direct_in'):
            incomes.append(t)
        elif show_all_linked and t_type in ('dasti_voucher_in',):
            incomes.append(t)
        elif t_type in ('expense', 'direct_out'):
            expenses.append(t)
        elif show_all_linked and t_type in ('batch_ledger_out', 'dasti_out', 'dasti_voucher_out', 'advance'):
            expenses.append(t)

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

    cats = get_categories(firm_id)
    approver_names = get_approvers(firm_id)
    
    return render_template_string(INDEX_TEMPLATE, persons=persons, dasti_persons=dasti_persons, incomes=incomes, expenses=expenses, balance=main_balance, account_balances=json.dumps(acc_bals), total_dasti=total_dasti_ledger, dasti_breakdown=dasti_breakdown, categories=cats, approver_names=approver_names, s_d_in=s_d_in, s_d_out=s_d_out, s_yest_in=s_yest_in, s_yest_out=s_yest_out, s_w_in=s_w_in, s_w_out=s_w_out, s_m_in=s_m_in, s_m_out=s_m_out, s_y_in=s_y_in, s_y_out=s_y_out, active_filter=time_filter, username=session['username'], active_page='home')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not has_users(): return redirect(url_for('register'))
    if request.method == 'POST':
        username_lower = request.form['username'].strip().lower()
        password_lower = request.form['password'].strip().lower()
        
        users_stream = db.collection('users').where('username_lower', '==', username_lower).stream()
        user_doc = next(users_stream, None)
        
        if user_doc:
            user = user_doc.to_dict()
            if user.get('password') == password_lower:
                session['user_id'] = user_doc.id
                session['username'] = user['username']
                session['firm_name'] = user['firm_name']
                session['firm_id'] = user.get('firm_id', user_doc.id)
                session['role'] = user.get('role', 'superadmin')
                session['can_approve'] = user.get('can_approve', 0)
                session['can_edit'] = user.get('can_edit', 0)
                session['can_express_cashout'] = user.get('can_express_cashout', 0)
                session['can_view_reports'] = user.get('can_view_reports', 0)
                session['can_view_trash'] = user.get('can_view_trash', 0)
                session['can_delete_logs'] = user.get('can_delete_logs', 0)
                session['can_view_ledger_details'] = user.get('can_view_ledger_details', 0) # ADD THIS LINE
                
                if session['role'] == 'superadmin':
                    session['can_approve'] = session['can_edit'] = session['can_view_reports'] = session['can_view_trash'] = session['can_delete_logs'] = session['can_view_ledger_details'] = 1 # UPDATE THIS LINE
                         
                return redirect(url_for('index'))
                
    settings = get_global_settings()
    return render_template_string(LOGIN_TEMPLATE, settings=settings, is_demo=False)

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if session.get('role') != 'superadmin': return redirect(url_for('index'))
    db.collection('settings').document('global_login').set({
        'game_enabled': int(request.form.get('game_enabled', 1)),
        'blocks_to_eat': int(request.form.get('blocks_to_eat', 4)),
        'unlock_corner': request.form.get('unlock_corner', 'br'),
        'game_speed': int(request.form.get('game_speed', 0)),
        'app_disabled': True if request.form.get('app_disabled') == '1' else False,
        'require_delete_confirm': True if request.form.get('require_delete_confirm') == '1' else False,
        'balance_display_mode': request.form.get('balance_display_mode', 'both'),
        'receipt_display_mode': request.form.get('receipt_display_mode', 'strict'),
        'edit_action_mode': request.form.get('edit_action_mode', 'button'),
        'report_flag_mode': request.form.get('report_flag_mode', 'both'),
        'report_pdf_format': request.form.get('report_pdf_format', 'standard'),
        'dashboard_sort_order': request.form.get('dashboard_sort_order', 'desc'),
        'dashboard_ledger_visibility': request.form.get('dashboard_ledger_visibility', 'main_only')  # <-- ADD THIS LINE
    }, merge=True)
    return redirect(url_for('manage_users'))


@app.route('/reindex_database', methods=['POST'])
def reindex_database():
    if 'user_id' not in session or session.get('role') != 'superadmin': 
        return redirect(url_for('index'))
    
    firm_id = session['firm_id']
    batch = db.batch()
    update_count = 0
    
    # Process all ledgers
    for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
        docs = db.collection(collection).where('user_id', '==', firm_id).stream()
        for d in docs:
            data = d.to_dict()
            date_val = data.get('date', '')
            time_val = data.get('time', '00:00')
            
            # Reconstruct an actual Unix timestamp from the date and time strings
            try:
                dt_obj = datetime.strptime(f"{date_val} {time_val}", "%Y-%m-%d %H:%M")
                new_created_at = dt_obj.timestamp()
                
                # Only update if it actually needs fixing to save writes
                if data.get('created_at') != new_created_at:
                    batch.update(d.reference, {'created_at': new_created_at})
                    update_count += 1
                
                # Firestore batches hold max 500 operations. Execute and open a new batch if we hit 450.
                if update_count >= 450:
                    batch.commit()
                    batch = db.batch()
                    update_count = 0
            except Exception:
                pass # Skip if date format is severely malformed
                
    if update_count > 0:
        batch.commit()
        
    return redirect(url_for('manage_users'))

@app.route('/add_fast_unified', methods=['POST'])
def add_fast_unified():
    if 'user_id' not in session: return redirect(url_for('login'))
    firm_id = session['firm_id']
    date_val, time_val, mode = request.form['date'], request.form['time'], request.form['payment_mode']
    
    natures = request.form.getlist('txn_nature[]')
    accounts = request.form.getlist('primary_account[]')
    approvers = request.form.getlist('approved_by_select[]')
    cats = request.form.getlist('category[]')
    descs = request.form.getlist('description[]')
    amts = request.form.getlist('amount[]')
    
    existing_cats = get_categories(firm_id)
    batch = db.batch()
    
    for i in range(len(descs)):
        if amts[i].strip() and float(amts[i]) >= 0:
            amt, desc = float(amts[i]), descs[i].strip()
            cat = cats[i]
            if cat not in existing_cats:
                db.collection('categories').add({'firm_id': firm_id, 'name': cat})
                existing_cats.append(cat)
                
            txn_nature = natures[i]
            account_raw = accounts[i]
            approver = approvers[i]
            txn_status = 'approved' if approver else 'pending'
            
            account_type = 'main'
            primary_id = None
            person_name = ''
            
            if account_raw.startswith('person_'):
                primary_id = account_raw.split('_')[1]
                account_type = 'person'
                person_name = db.collection('persons').document(primary_id).get().to_dict().get('name', '')
            elif account_raw.startswith('dasti_'):
                primary_id = account_raw.split('_')[1]
                account_type = 'dasti'
                person_name = db.collection('dasti_persons').document(primary_id).get().to_dict().get('name', '')
                
            link_id = uuid.uuid4().hex[:12]
            final_nature = txn_nature
            if account_type == 'main':
                final_nature = 'direct_in' if txn_nature == 'receive_cash' else 'direct_out'
                
            base_txn = {
                'user_id': firm_id, 'date': date_val, 'time': time_val, 'payment_mode': mode, 
                'category': cat, 'amount': amt, 'link_id': link_id, 'status': txn_status, 
                'approved_by': approver, 'deleted': 0, 'created_at': time.time(),
                'voucher_nature': final_nature, 'is_flagged': 0 
            }

            if account_type == 'main':
                db_type = 'income' if txn_nature == 'receive_cash' else 'expense'
                batch.set(db.collection('transactions').document(), {**base_txn, 'description': desc, 'type': db_type})
                
            elif account_type == 'person':
                if txn_nature == 'slip_in':
                    batch.set(db.collection('person_ledger').document(), {**base_txn, 'person_id': primary_id, 'description': desc, 'type': 'settlement'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Slip ({person_name}): {desc}", 'type': 'batch_ledger_out'})
                elif txn_nature == 'advance':
                    batch.set(db.collection('person_ledger').document(), {**base_txn, 'person_id': primary_id, 'description': desc, 'type': 'advance'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Transfer Out ({person_name}): {desc}", 'type': 'dasti_out'})
                elif txn_nature == 'receive_cash':
                    batch.set(db.collection('person_ledger').document(), {**base_txn, 'person_id': primary_id, 'description': desc, 'type': 'settlement', 'voucher_nature': 'receive_cash'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Transfer In ({person_name}): {desc}", 'type': 'income', 'voucher_nature': 'receive_cash'})
                    
            elif account_type == 'dasti':
                if txn_nature == 'slip_in':
                    batch.set(db.collection('dasti_ledger').document(), {**base_txn, 'dasti_person_id': primary_id, 'description': desc, 'type': 'settlement'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Dasti Slip ({person_name}): {desc}", 'type': 'batch_ledger_out'})
                elif txn_nature == 'advance':
                    batch.set(db.collection('dasti_ledger').document(), {**base_txn, 'dasti_person_id': primary_id, 'description': desc, 'type': 'advance'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Dasti Out ({person_name}): {desc}", 'type': 'dasti_voucher_out'})
                elif txn_nature == 'receive_cash':
                    batch.set(db.collection('dasti_ledger').document(), {**base_txn, 'dasti_person_id': primary_id, 'description': desc, 'type': 'settlement', 'voucher_nature': 'receive_cash'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Dasti In ({person_name}): {desc}", 'type': 'dasti_voucher_in', 'voucher_nature': 'receive_cash'})

    batch.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/add_batch_unified', methods=['POST'])
def add_batch_unified():
    if 'user_id' not in session: return redirect(url_for('login'))
    firm_id = session['firm_id']
    date_val, time_val, mode, txn_nature = request.form['date'], request.form['time'], request.form['payment_mode'], request.form['txn_nature']
    primary_account_raw = request.form['primary_account']
    new_account_name = request.form.get('new_account_name', '').strip()
    
    approver_select = request.form.get('approved_by_select', '')
    approver_custom = request.form.get('new_approver_name', '').strip()
    
    cats, cust_cats, descs, amts = request.form.getlist('category[]'), request.form.getlist('custom_category[]'), request.form.getlist('description[]'), request.form.getlist('amount[]')
    
    final_approver = ''
    if approver_select == 'new_approver' and approver_custom:
        final_approver = approver_custom
        check = db.collection('approvers').where('firm_id', '==', firm_id).where('name', '==', final_approver).get()
        if not check:
            db.collection('approvers').add({'firm_id': firm_id, 'name': final_approver})
    elif approver_select and approver_select != 'new_approver':
        final_approver = approver_select
        
    txn_status = 'approved' if final_approver else 'pending'
    existing_cats = get_categories(firm_id)
    
    account_type = 'main'
    primary_id = None
    person_name = ''
    
    if primary_account_raw == 'new_dasti':
        new_ref = db.collection('dasti_persons').document()
        new_ref.set({'user_id': firm_id, 'name': new_account_name, 'deleted': 0})
        primary_id = new_ref.id
        account_type, person_name = 'dasti', new_account_name
    elif primary_account_raw == 'new_person':
        new_ref = db.collection('persons').document()
        new_ref.set({'user_id': firm_id, 'name': new_account_name, 'deleted': 0})
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
        
    batch = db.batch()
    
    for i in range(len(descs)):
        if amts[i].strip() and float(amts[i]) >= 0:
            amt, desc = float(amts[i]), descs[i].strip()
            custom_cat_val = cust_cats[i].strip() if i < len(cust_cats) and cust_cats[i] else ''
            cat = custom_cat_val if cats[i] == 'Other' and custom_cat_val else cats[i]
            if cat not in existing_cats:
                db.collection('categories').add({'firm_id': firm_id, 'name': cat})
                existing_cats.append(cat)
                
            link_id = uuid.uuid4().hex[:12]
            final_nature = txn_nature
            if account_type == 'main':
                final_nature = 'direct_in' if txn_nature == 'receive_cash' else 'direct_out'
                
            base_txn = {
                'user_id': firm_id, 'date': date_val, 'time': time_val, 'payment_mode': mode, 
                'category': cat, 'amount': amt, 'link_id': link_id, 'status': txn_status, 
                'approved_by': final_approver, 'deleted': 0, 'created_at': time.time(),
                'voucher_nature': final_nature, 'is_flagged': 0 
            }

            if account_type == 'main':
                db_type = 'income' if txn_nature == 'receive_cash' else 'expense'
                batch.set(db.collection('transactions').document(), {**base_txn, 'description': desc, 'type': db_type})
                
            elif account_type == 'person':
                if txn_nature == 'slip_in':
                    batch.set(db.collection('person_ledger').document(), {**base_txn, 'person_id': primary_id, 'description': desc, 'type': 'settlement'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Slip ({person_name}): {desc}", 'type': 'batch_ledger_out'})
                elif txn_nature == 'advance':
                    batch.set(db.collection('person_ledger').document(), {**base_txn, 'person_id': primary_id, 'description': desc, 'type': 'advance'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Transfer Out ({person_name}): {desc}", 'type': 'dasti_out'})
                elif txn_nature == 'receive_cash':
                    batch.set(db.collection('person_ledger').document(), {**base_txn, 'person_id': primary_id, 'description': desc, 'type': 'settlement', 'voucher_nature': 'receive_cash'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Transfer In ({person_name}): {desc}", 'type': 'income', 'voucher_nature': 'receive_cash'})
                    
            elif account_type == 'dasti':
                if txn_nature == 'slip_in':
                    batch.set(db.collection('dasti_ledger').document(), {**base_txn, 'dasti_person_id': primary_id, 'description': desc, 'type': 'settlement'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Dasti Slip ({person_name}): {desc}", 'type': 'batch_ledger_out'})
                elif txn_nature == 'advance':
                    batch.set(db.collection('dasti_ledger').document(), {**base_txn, 'dasti_person_id': primary_id, 'description': desc, 'type': 'advance'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Dasti Out ({person_name}): {desc}", 'type': 'dasti_voucher_out'})
                elif txn_nature == 'receive_cash':
                    batch.set(db.collection('dasti_ledger').document(), {**base_txn, 'dasti_person_id': primary_id, 'description': desc, 'type': 'settlement', 'voucher_nature': 'receive_cash'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Dasti In ({person_name}): {desc}", 'type': 'dasti_voucher_in', 'voucher_nature': 'receive_cash'})

    batch.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/logs')
def logs():
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): 
        return redirect(url_for('index'))
    
    firm_id = session['firm_id']
    link_id_filter = request.args.get('link_id')
    
    query = db.collection('edit_logs').where('firm_id', '==', firm_id)
    if link_id_filter:
        query = query.where('link_id', '==', link_id_filter)
        
    logs_data = [{'id': doc.id, **doc.to_dict()} for doc in query.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(100).stream()]
    return render_template_string(LOGS_TEMPLATE, logs=logs_data, username=session['username'], active_page='logs', link_id_filter=link_id_filter)

@app.route('/delete_log/<string:log_id>')
def delete_log(log_id):
    if 'user_id' not in session or (session.get('can_delete_logs') != 1 and session.get('role') != 'superadmin'): 
        return redirect(url_for('logs'))
        
    doc_ref = db.collection('edit_logs').document(log_id)
    if doc_ref.get().to_dict().get('firm_id') == session['firm_id']:
        doc_ref.delete()
        
    return redirect(request.referrer or url_for('logs'))

@app.route('/flag_entries', methods=['GET', 'POST'])
def flag_entries():
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): return redirect(url_for('index'))
    firm_id = session['firm_id']
    
    results = []
    has_searched = False
    now = datetime.now(IST)
    start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    flag_filter = 'unflagged'
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'search':
            start_date = request.form.get('start_date', start_date)
            end_date = request.form.get('end_date', end_date)
            flag_filter = request.form.get('flag_filter', 'unflagged')
            
            docs = db.collection('transactions').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()
            for d in docs:
                data = d.to_dict()
                date_val = data.get('date', '')
                if start_date <= date_val <= end_date:
                    is_flagged = data.get('is_flagged', 0)
                    if flag_filter == 'flagged' and is_flagged != 1: continue
                    if flag_filter == 'unflagged' and is_flagged == 1: continue
                    results.append(data)
                    
            results.sort(key=lambda x: (x.get('created_at', 0)), reverse=True)
            has_searched = True
            
        elif action == 'process_flags':
            flag_action = int(request.form.get('flag_action', 0))
            selected_links = request.form.getlist('selected_links')
            if selected_links:
                batch = db.batch()
                for link_id in selected_links:
                    for col in ['transactions', 'person_ledger', 'dasti_ledger']:
                        for doc in db.collection(col).where('link_id', '==', link_id).where('user_id', '==', firm_id).stream():
                            batch.update(doc.reference, {'is_flagged': flag_action})
                batch.commit()
            return redirect(url_for('flag_entries'))
            
    return render_template_string(FLAGS_TEMPLATE, results=results, has_searched=has_searched, start_date=start_date, end_date=end_date, flag_filter=flag_filter, username=session['username'], active_page='flags')

@app.route('/bulk_edit_date', methods=['GET', 'POST'])
def bulk_edit_date():
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): 
        return redirect(url_for('index'))
    
    firm_id = session['firm_id']
    results = []
    has_searched = False
    
    now = datetime.now(IST)
    start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    search_amount = ''
    search_desc = ''
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'search':
            start_date = request.form.get('start_date', start_date)
            end_date = request.form.get('end_date', end_date)
            search_amount = request.form.get('search_amount', '').strip()
            search_desc = request.form.get('search_desc', '').strip().lower()
            
            docs = db.collection('transactions').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()
            for d in docs:
                data = d.to_dict()
                data['id'] = d.id  # Ensure ID is included for the Edit button link
                date_val = data.get('date', '')
                
                if start_date <= date_val <= end_date:
                    # Apply Amount Filter if provided
                    if search_amount:
                        try:
                            if float(data.get('amount', 0)) != float(search_amount):
                                continue
                        except ValueError:
                            pass
                            
                    # Apply Description/Category Filter if provided
                    if search_desc:
                        desc_text = data.get('description', '').lower()
                        cat_text = data.get('category', '').lower()
                        if search_desc not in desc_text and search_desc not in cat_text:
                            continue
                            
                    results.append(data)
                    
            results.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=True)
            has_searched = True
            
        elif action == 'update_dates':
            selected_links = request.form.getlist('selected_links')
            new_date = request.form.get('new_date')
            
            if selected_links and new_date:
                batch = db.batch()
                updated_count = 0
                
                for link_id in selected_links:
                    for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
                        docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', firm_id).stream()
                        for d in docs:
                            batch.update(d.reference, {'date': new_date})
                            updated_count += 1
                            
                if updated_count > 0:
                    batch.set(db.collection('edit_logs').document(), {
                        'firm_id': firm_id,
                        'link_id': 'bulk_edit',
                        'edited_by': session['username'],
                        'changes': f"Bulk changed date to {new_date} for {len(selected_links)} distinct vouchers.",
                        'details': "Bulk Date Correction Tool",
                        'timestamp': int(time.time() * 1000),
                        'date_formatted': datetime.now(IST).strftime('%d-%b-%Y %I:%M %p')
                    })
                    
                batch.commit()
            
            return redirect(url_for('bulk_edit_date'))

    return render_template_string(BULK_EDIT_DATE_TEMPLATE, results=results, has_searched=has_searched, start_date=start_date, end_date=end_date, search_amount=search_amount, search_desc=search_desc, username=session['username'], active_page='bulk_date')

@app.route('/delete/<string:table_name>/<string:row_id>')
def delete_entry(table_name, row_id):
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): return redirect(url_for('index'))
    doc_ref = db.collection(table_name).document(row_id)
    doc_data = doc_ref.get().to_dict()
    
    if doc_data and doc_data.get('user_id') == session['firm_id']:
        link_id = doc_data.get('link_id', '')
        batch = db.batch()
        if link_id:
            for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
                linked_docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', session['firm_id']).stream()
                for d in linked_docs:
                    batch.update(d.reference, {'deleted': 1})
        else:
            batch.update(doc_ref, {'deleted': 1})
        batch.commit()
            
    return redirect(request.referrer or url_for('index'))

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/main_ledger')
def main_ledger():
    if 'user_id' not in session: return redirect(url_for('login'))
    firm_id = session['firm_id']
    
    all_txns = []
    for doc in db.collection('transactions').where('user_id', '==', firm_id).where('deleted', '==', 0).stream():
        data = doc.to_dict()
        if data.get('type') in ('split_expense', 'split_income'):
            continue  # internal memo leg for a split-voucher "Main Book" row - not a real ledger line
        all_txns.append({'id': doc.id, **data})
    
    # Apply Dashboard Sort Order from Global Settings
    
    # Apply Dashboard Sort Order from Global Settings
    # Ensure this is at the top of your routes to capture the user's preference
    settings = get_global_settings()
    is_desc = (settings.get('dashboard_sort_order', 'desc') == 'desc')

    # Force the sort immediately after fetching from Firebase
    all_txns.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=is_desc)

    total_in = sum(float(t.get('amount', 0)) for t in all_txns if t.get('type') in ('income', 'dasti_voucher_in') and t.get('status') == 'approved')
    # Only count 'expense' and 'direct_out', ignore 'split_expense'
    total_out = sum(float(t.get('amount', 0)) for t in all_txns if t.get('type') in ('expense', 'direct_out', 'batch_ledger_out') and t.get('status') == 'approved')
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
    total_out = sum(float(t.get('amount', 0)) for t in all_txns if t.get('type') in ('expense', 'dasti_out', 'dasti_voucher_out', 'batch_ledger_out') and t.get('status') == 'approved')
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

    # NEW: Person Ledger outstanding total, same math as index()
    persons = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('persons').where('user_id', '==', firm_id).stream()]
    all_person_ledger = [doc.to_dict() for doc in db.collection('person_ledger').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    total_person_ledger = 0.0
    for p in persons:
        adv = sum(float(l.get('amount', 0)) for l in all_person_ledger if l.get('person_id') == p['id'] and l.get('type') == 'advance' and l.get('status') == 'approved')
        setl = sum(float(l.get('amount', 0)) for l in all_person_ledger if l.get('person_id') == p['id'] and l.get('type') == 'settlement' and l.get('status') == 'approved')
        owed = adv - setl
        if owed > 0:
            total_person_ledger += owed

    total_ledger_outstanding = total_outstanding_dasti + total_person_ledger

    return render_template_string(DASTI_LEDGER_TEMPLATE, balances=balances, balance=main_balance,
        total_outstanding_dasti=total_outstanding_dasti,
        total_ledger_outstanding=total_ledger_outstanding,
        username=session['username'], active_page='dasti_ledger')

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
    
    settings = get_global_settings()
    show_ledger_entries = (settings.get('dashboard_ledger_visibility', 'main_only') == 'all')
    return render_template_string(DASTI_ACCOUNT_TEMPLATE, person=person, txns=txns, balance=(advances - settlements), advances=advances, settlements=settlements, username=session['username'], active_page='dasti_ledger', show_ledger_entries=show_ledger_entries)


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
    
    person_list = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('persons').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    person_list.sort(key=lambda x: x.get('name', ''))
    
    all_person_ledger = [doc.to_dict() for doc in db.collection('person_ledger').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    
    balances = []
    total_person_ledger = 0.0
    for p in person_list:
        adv = sum(float(l.get('amount', 0)) for l in all_person_ledger if l.get('person_id') == p['id'] and l.get('type') == 'advance' and l.get('status') == 'approved')
        setl = sum(float(l.get('amount', 0)) for l in all_person_ledger if l.get('person_id') == p['id'] and l.get('type') == 'settlement' and l.get('status') == 'approved')
        net = adv - setl
        balances.append({'id': p['id'], 'name': p['name'], 'net': net})
        if net > 0:
            total_person_ledger += net

    # Main Cash Book balance - same formula as index()/main_ledger()/dasti_ledger()
    all_txns = [doc.to_dict() for doc in db.collection('transactions').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    total_in = sum(float(t.get('amount', 0)) for t in all_txns if t.get('type') in ('income', 'dasti_voucher_in') and t.get('status') == 'approved')
    total_out = sum(float(t.get('amount', 0)) for t in all_txns if t.get('type') in ('expense', 'dasti_out', 'dasti_voucher_out', 'batch_ledger_out') and t.get('status') == 'approved')
    main_balance = total_in - total_out

    # Dasti outstanding, for the combined "Total Ledger Balance"
    dasti_persons = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('dasti_persons').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    all_dasti_ledger = [doc.to_dict() for doc in db.collection('dasti_ledger').where('user_id', '==', firm_id).where('deleted', '==', 0).stream()]
    total_dasti_outstanding = 0.0
    for dp in dasti_persons:
        adv = sum(float(l.get('amount', 0)) for l in all_dasti_ledger if l.get('dasti_person_id') == dp['id'] and l.get('type') == 'advance' and l.get('status') == 'approved')
        setl = sum(float(l.get('amount', 0)) for l in all_dasti_ledger if l.get('dasti_person_id') == dp['id'] and l.get('type') == 'settlement' and l.get('status') == 'approved')
        owed = adv - setl
        if owed > 0:
            total_dasti_outstanding += owed

    total_ledger_outstanding = total_person_ledger + total_dasti_outstanding
        
    return render_template_string(PERSONS_TEMPLATE, balances=balances, balance=main_balance,
        total_person_ledger=total_person_ledger,
        total_ledger_outstanding=total_ledger_outstanding,
        username=session['username'], active_page='persons')

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
    
    settings = get_global_settings()
    show_ledger_entries = (settings.get('dashboard_ledger_visibility', 'main_only') == 'all')
    return render_template_string(PERSON_ACCOUNT_TEMPLATE, person=person, txns=txns, balance=(advances - settlements), advances=advances, settlements=settlements, username=session['username'], active_page='persons', show_ledger_entries=show_ledger_entries)


@app.route('/edit_person/<string:id>')
def edit_person(id):
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): return redirect(url_for('login'))
    new_name = request.args.get('name')
    if new_name:
        doc_ref = db.collection('persons').document(id)
        if doc_ref.get().to_dict().get('user_id') == session['firm_id']:
            doc_ref.update({'name': new_name})
    return redirect(url_for('persons'))

@app.route('/trash')
def trash():
    if 'user_id' not in session or (session.get('can_view_trash') != 1 and session.get('role') != 'superadmin'): return redirect(url_for('index'))
    trashed = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('transactions').where('user_id', '==', session['firm_id']).where('deleted', '==', 1).stream()]
    trashed.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=True)
    return render_template_string(TRASH_TEMPLATE, trashed=trashed, username=session['username'], active_page='trash')

@app.route('/restore_voucher/<string:link_id>')
def restore_voucher(link_id):
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): return redirect(url_for('index'))
    batch = db.batch()
    for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
        docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', session['firm_id']).stream()
        for d in docs: batch.update(d.reference, {'deleted': 0})
    batch.commit()
    return redirect(url_for('trash'))

@app.route('/hard_delete_voucher/<string:link_id>')
def hard_delete_voucher(link_id):
    if 'user_id' not in session or session.get('role') != 'superadmin': return redirect(url_for('index'))
    batch = db.batch()
    for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
        docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', session['firm_id']).stream()
        for d in docs: batch.delete(d.reference)
    batch.commit()
    return redirect(url_for('trash'))

@app.route('/bulk_restore_trash', methods=['POST'])
def bulk_restore_trash():
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): 
        return redirect(url_for('index'))
    selected_links = request.form.getlist('selected_links')
    if not selected_links: return redirect(url_for('trash'))
        
    batch = db.batch()
    for link_id in selected_links:
        for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
            docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', session['firm_id']).stream()
            for d in docs: batch.update(d.reference, {'deleted': 0})
    batch.commit()
    return redirect(url_for('trash'))

@app.route('/bulk_hard_delete_trash', methods=['POST'])
def bulk_hard_delete_trash():
    if 'user_id' not in session or session.get('role') != 'superadmin': return redirect(url_for('index'))
    selected_links = request.form.getlist('selected_links')
    if not selected_links: return redirect(url_for('trash'))
        
    batch = db.batch()
    for link_id in selected_links:
        for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
            docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', session['firm_id']).stream()
            for d in docs: batch.delete(d.reference)
    batch.commit()
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
    
    raw_results = [doc.to_dict() for doc in query.stream() if doc.to_dict().get('type') not in ('split_expense', 'split_income')]
    
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
        writer.writerow(('Date', 'Time', 'Mode', 'Category', 'Description', 'Type', 'Amount (INR)', 'Approved By', 'Is Flagged'))
        yield data.getvalue(); data.seek(0); data.truncate(0)
        for r in results:
            writer.writerow((r.get('date', ''), r.get('time', ''), r.get('payment_mode', ''), r.get('category', ''), r.get('description', ''), r.get('type', ''), r.get('amount', 0), r.get('approved_by', ''), r.get('is_flagged', 0)))
            yield data.getvalue(); data.seek(0); data.truncate(0)
            
    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment; filename=Firm_Report_Export.csv"})

@app.route('/manage_users')
def manage_users():
    if 'user_id' not in session or session.get('role') != 'superadmin': return redirect(url_for('index'))
    firm_id = session['firm_id']
    users = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('users').where('firm_id', '==', firm_id).stream()]
    approver_list = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('approvers').where('firm_id', '==', firm_id).stream()]
    sys_settings = get_global_settings()
    return render_template_string(USERS_TEMPLATE, users=users, approver_list=approver_list, sys_settings=sys_settings, username=session['username'], active_page='users')

@app.route('/edit_user/<string:uid>', methods=['GET', 'POST'])
def edit_user(uid):
    if 'user_id' not in session or session.get('role') != 'superadmin': return redirect(url_for('index'))
    doc_ref = db.collection('users').document(uid)
    user_data = doc_ref.get().to_dict()
    if not user_data or user_data.get('firm_id') != session['firm_id']: return redirect(url_for('manage_users'))
    
    if request.method == 'POST':
        username_raw = request.form['username'].strip()
        update_data = {
            'username': username_raw,
            'username_lower': username_raw.lower(),
            'role': request.form['role'],
            'can_approve': int(request.form.get('can_approve', 0)),
            'can_edit': int(request.form.get('can_edit', 0)),
            'can_express_cashout': int(request.form.get('can_express_cashout', 0)),
            'can_view_reports': int(request.form.get('can_view_reports', 0)),
            'can_view_trash': int(request.form.get('can_view_trash', 0)),
            'can_delete_logs': int(request.form.get('can_delete_logs', 0)),
            'can_view_ledger_details': int(request.form.get('can_view_ledger_details', 0)), # ADD THIS LINE
            'idle_timeout_minutes': int(request.form.get('idle_timeout', 15))
        }
        new_pw = request.form.get('password', '').strip()
        if new_pw: update_data['password'] = new_pw.lower()
        
        doc_ref.update(update_data)
        return redirect(url_for('manage_users'))
        
    edit_user_obj = {'id': uid, **user_data}
    return render_template_string(EDIT_USER_TEMPLATE, edit_user=edit_user_obj, username=session['username'], active_page='users')

@app.route('/edit_approver/<string:uid>', methods=['POST'])
def edit_approver(uid):
    if 'user_id' not in session or session.get('role') != 'superadmin': return redirect(url_for('index'))
    new_name = request.form.get('name', '').strip()
    if new_name:
        db.collection('approvers').document(uid).update({'name': new_name})
    return redirect(url_for('manage_users'))

@app.route('/delete_approver/<string:uid>')
def delete_approver(uid):
    if 'user_id' not in session or session.get('role') != 'superadmin': return redirect(url_for('index'))
    db.collection('approvers').document(uid).delete()
    return redirect(url_for('manage_users'))

@app.route('/add_user', methods=['POST'])
def add_user():
    if 'user_id' not in session or session.get('role') != 'superadmin': return redirect(url_for('index'))
    
    username_raw = request.form['new_username'].strip()
    password_raw = request.form['new_password'].strip().lower()
    
    db.collection('users').add({
        'username': username_raw,
        'username_lower': username_raw.lower(),
        'password': password_raw,
        'firm_name': session['firm_name'],
        'firm_id': session['firm_id'],
        'role': request.form['role'],
        'can_approve': int(request.form.get('can_approve', 0)),
        'can_edit': int(request.form.get('can_edit', 0)),
        'can_express_cashout': int(request.form.get('can_express_cashout', 0)),
        'can_view_reports': int(request.form.get('can_view_reports', 0)),
        'can_view_trash': int(request.form.get('can_view_trash', 0)),
        'can_delete_logs': int(request.form.get('can_delete_logs', 0)),
        'can_view_ledger_details': int(request.form.get('can_view_ledger_details', 0)), # ADD THIS LINE
        'idle_timeout_minutes': int(request.form.get('idle_timeout', 15))
    })
    return redirect(url_for('manage_users'))


@app.route('/approvals')
def approvals():
    if 'user_id' not in session or session.get('can_approve') != 1: return redirect(url_for('index'))
    firm_id = session['firm_id']
    
    pending = [{'id': doc.id, **doc.to_dict()} for doc in db.collection('transactions').where('user_id', '==', firm_id).where('status', '==', 'pending').where('deleted', '==', 0).stream()]
    pending.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=True)
    
    approved_stream = db.collection('transactions').where('user_id', '==', firm_id).where('status', '==', 'approved').where('deleted', '==', 0).stream()
    approved = [{'id': doc.id, **doc.to_dict()} for doc in approved_stream]
    approved.sort(key=lambda x: (x.get('date', ''), x.get('time', ''), x.get('created_at', 0)), reverse=True)
    approved = approved[:100]
    
    approvers = get_approvers(firm_id)
    
    return render_template_string(APPROVALS_TEMPLATE, pending=pending, approved=approved, approvers=[{'username': a, 'can_approve': 1} for a in approvers], username=session['username'], active_page='approvals')

@app.route('/approve_voucher/<string:link_id>')
def approve_voucher(link_id):
    if 'user_id' not in session or session.get('can_approve') != 1: return redirect(url_for('index'))
    batch = db.batch()
    for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
        docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', session['firm_id']).stream()
        for d in docs: batch.update(d.reference, {'status': 'approved', 'approved_by': session['username']})
    batch.commit()
    return redirect(request.referrer or url_for('approvals'))

@app.route('/reject_voucher/<string:link_id>')
def reject_voucher(link_id):
    if 'user_id' not in session or session.get('can_approve') != 1: return redirect(url_for('index'))
    batch = db.batch()
    for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
        docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', session['firm_id']).stream()
        for d in docs: batch.update(d.reference, {'deleted': 1})
    batch.commit()
    return redirect(request.referrer or url_for('approvals'))

@app.route('/bulk_approve', methods=['POST'])
def bulk_approve():
    if 'user_id' not in session or session.get('can_approve') != 1: return redirect(url_for('index'))
    start = request.form.get('start_date', '')
    end = request.form.get('end_date', '')
    approver = request.form.get('approved_by_select', session['username']) or session['username']
    
    batch = db.batch()
    for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
        docs = db.collection(collection).where('user_id', '==', session['firm_id']).where('status', '==', 'pending').where('deleted', '==', 0).stream()
        for d in docs:
            doc_data = d.to_dict()
            date_val = doc_data.get('date', '')
            if start <= date_val <= end:
                batch.update(d.reference, {'status': 'approved', 'approved_by': approver})
                
    batch.commit()
    return redirect(url_for('approvals'))

@app.route('/bulk_approve_selected', methods=['POST'])
def bulk_approve_selected():
    if 'user_id' not in session or session.get('can_approve') != 1: return redirect(url_for('index'))
    selected_links = request.form.getlist('selected_links')
    if not selected_links: return redirect(url_for('approvals'))
    
    approver = request.form.get('approved_by_select', session['username']) or session['username']
    
    batch = db.batch()
    for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
        docs = db.collection(collection).where('user_id', '==', session['firm_id']).where('status', '==', 'pending').where('deleted', '==', 0).stream()
        for d in docs:
            if d.to_dict().get('link_id') in selected_links:
                batch.update(d.reference, {'status': 'approved', 'approved_by': approver})
                
    batch.commit()
    return redirect(url_for('approvals'))

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

    linked_docs = {'transactions': [], 'person_ledger': [], 'dasti_ledger': []}
    if link_id:
        for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
            found = list(db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', firm_id).stream())
            for f in found: linked_docs[collection].append({'id': f.id, **f.to_dict()})

    txn_docs = linked_docs.get('transactions', [])
    person_docs = linked_docs.get('person_ledger', [])
    dasti_docs = linked_docs.get('dasti_ledger', [])
    has_link = bool(link_id)

    # Detect if it's a split voucher (Master entry exists, and there are multiple sub-entries)
    is_split = False
    splits_data = []
    
    if has_link:
        master_txn = next((t for t in txn_docs if t.get('category') == 'Split Settlement'), None)
        if master_txn and (len(txn_docs) + len(person_docs) + len(dasti_docs)) > 2:
            is_split = True
            entry = master_txn
            for t in txn_docs:
                if t['id'] != master_txn['id']:
                    nat = 'slip_in' if t.get('type') == 'split_expense' else 'receive_cash'
                    splits_data.append({'account': 'main', 'category': t.get('category'), 'amount': t.get('amount'), 'nature': nat})
            for p in person_docs:
                nat = 'advance' if p.get('type') == 'advance' else ('receive_cash' if p.get('voucher_nature') == 'receive_cash' else 'slip_in')
                splits_data.append({'account': f"person_{p.get('person_id')}", 'category': p.get('category'), 'amount': p.get('amount'), 'nature': nat})
            for d in dasti_docs:
                nat = 'advance' if d.get('type') == 'advance' else ('receive_cash' if d.get('voucher_nature') == 'receive_cash' else 'slip_in')
                splits_data.append({'account': f"dasti_{d.get('dasti_person_id')}", 'category': d.get('category'), 'amount': d.get('amount'), 'nature': nat})

    # Standard Voucher Variables
    current_account_type, current_primary_id, current_nature = 'main', '', 'slip_in'
    if not is_split:
        if person_docs:
            current_account_type, current_primary_id = 'person', person_docs[0].get('person_id', '')
        elif dasti_docs:
            current_account_type, current_primary_id = 'dasti', dasti_docs[0].get('dasti_person_id', '')
            
        nature_map = {'expense': 'slip_in', 'batch_ledger_out': 'slip_in', 'settlement': 'slip_in', 'dasti_out': 'advance', 'dasti_voucher_out': 'advance', 'advance': 'advance', 'income': 'receive_cash', 'dasti_voucher_in': 'receive_cash'}
        ref_type = txn_docs[0].get('type', '') if txn_docs else entry.get('type', '')
        current_nature = nature_map.get(ref_type, 'slip_in')

    persons = [{'id': d.id, **d.to_dict()} for d in db.collection('persons').where('user_id', '==', firm_id).stream()]
    persons.sort(key=lambda x: x.get('name', ''))
    dasti_persons = [{'id': d.id, **d.to_dict()} for d in db.collection('dasti_persons').where('user_id', '==', firm_id).stream()]
    dasti_persons.sort(key=lambda x: x.get('name', ''))
    approvers = [{'id': d.id, **d.to_dict()} for d in db.collection('users').where('firm_id', '==', firm_id).stream()]
    approver_names = [u.get('username', '') for u in approvers]
    existing_cats = get_categories(firm_id)

    if request.method == 'POST':
        batch = db.batch()
        date_val = request.form['date']
        time_val = request.form['time']
        mode = request.form['payment_mode']
        is_flagged = int(request.form.get('is_flagged', 0))

        new_status = request.form.get('status', entry.get('status'))
        approver_select = request.form.get('approved_by_select', '')
        approver_custom = request.form.get('approved_by_custom', '').strip()
        
        if 'status' in request.form:
            if approver_select == 'other' and approver_custom:
                chosen_approver = approver_custom
                if not db.collection('approvers').where('firm_id', '==', firm_id).where('name', '==', chosen_approver).get():
                    db.collection('approvers').add({'firm_id': firm_id, 'name': chosen_approver})
            elif approver_select and approver_select != 'other':
                chosen_approver = approver_select
            else:
                chosen_approver = entry.get('approved_by', '')
            approved_by = chosen_approver or session['username'] if new_status == 'approved' else ''
        else:
            new_status, approved_by = entry.get('status'), entry.get('approved_by', '')

        # --- POST HANDLING FOR SPLIT VOUCHER ---
        if request.form.get('is_split_edit') == '1':
            master_desc = request.form['description'].strip()
            natures = request.form.getlist('txn_nature[]')
            accounts = request.form.getlist('primary_account[]')
            cats = request.form.getlist('category[]')
            amts = request.form.getlist('split_amount[]')

            valid_rows = [(cats[i], natures[i], accounts[i], float(amts[i]))
                          for i in range(len(amts)) if amts[i].strip() and float(amts[i]) > 0]
            if not valid_rows:
                return redirect(request.referrer or url_for('index'))
            master_amount = sum(r[3] for r in valid_rows)

            # Delete old split components entirely
            for coll, docs_list in linked_docs.items():
                for d in docs_list:
                    batch.delete(db.collection(coll).document(d['id']))

            first_acc = valid_rows[0][2]
            display_name = "Main"
            if first_acc.startswith('person_'):
                display_name = next((p['name'] for p in persons if p['id'] == first_acc.split('_')[1]), "Person")
            elif first_acc.startswith('dasti_'):
                display_name = next((d['name'] for d in dasti_persons if d['id'] == first_acc.split('_')[1]), "Dasti")
            if len(valid_rows) > 1:
                display_name += " & Others"

            has_out = any(r[1] in ('slip_in', 'advance') for r in valid_rows)
            has_in = any(r[1] == 'receive_cash' for r in valid_rows)
            master_type = 'income' if (has_in and not has_out) else 'expense'

            batch.set(db.collection('transactions').document(), {
                'user_id': firm_id, 'date': date_val, 'time': time_val, 'payment_mode': mode, 'category': 'Split Settlement',
                'amount': master_amount, 'link_id': link_id, 'status': new_status, 'approved_by': approved_by,
                'deleted': entry.get('deleted', 0), 'created_at': entry.get('created_at', time.time()),
                'voucher_nature': 'direct_out' if master_type == 'expense' else 'direct_in', 'is_flagged': is_flagged,
                'description': f"{master_desc} ({display_name})", 'type': master_type
            })

            for cat, txn_nature, account_raw, amt in valid_rows:
                if cat not in existing_cats:
                    db.collection('categories').add({'firm_id': firm_id, 'name': cat})
                    existing_cats.append(cat)

                base_txn = {
                    'user_id': firm_id, 'date': date_val, 'time': time_val, 'payment_mode': mode,
                    'category': cat, 'amount': amt, 'link_id': link_id, 'status': new_status,
                    'approved_by': approved_by, 'deleted': entry.get('deleted', 0),
                    'created_at': entry.get('created_at', time.time()), 'is_flagged': is_flagged
                }

                if account_raw == 'main':
                    leg_type = 'split_expense' if txn_nature in ('slip_in', 'advance') else 'split_income'
                    batch.set(db.collection('transactions').document(), {
                        **base_txn,
                        'description': f"{master_desc} (Split-Gen)",
                        'type': leg_type,
                        'voucher_nature': txn_nature
                    })
                elif account_raw.startswith('person_'):
                    pid = account_raw.split('_')[1]
                    p_name = next((p['name'] for p in persons if p['id'] == pid), "")
                    l_desc = f"{master_desc} (Split: {p_name})"
                    if txn_nature == 'slip_in':
                        batch.set(db.collection('person_ledger').document(), {**base_txn, 'person_id': pid, 'description': l_desc, 'type': 'settlement'})
                    elif txn_nature == 'advance':
                        batch.set(db.collection('person_ledger').document(), {**base_txn, 'person_id': pid, 'description': l_desc, 'type': 'advance'})
                    elif txn_nature == 'receive_cash':
                        batch.set(db.collection('person_ledger').document(), {**base_txn, 'person_id': pid, 'description': l_desc, 'type': 'settlement', 'voucher_nature': 'receive_cash'})
                elif account_raw.startswith('dasti_'):
                    pid = account_raw.split('_')[1]
                    p_name = next((d['name'] for d in dasti_persons if d['id'] == pid), "")
                    l_desc = f"{master_desc} (Split: {p_name})"
                    if txn_nature == 'slip_in':
                        batch.set(db.collection('dasti_ledger').document(), {**base_txn, 'dasti_person_id': pid, 'description': l_desc, 'type': 'settlement'})
                    elif txn_nature == 'advance':
                        batch.set(db.collection('dasti_ledger').document(), {**base_txn, 'dasti_person_id': pid, 'description': l_desc, 'type': 'advance'})
                    elif txn_nature == 'receive_cash':
                        batch.set(db.collection('dasti_ledger').document(), {**base_txn, 'dasti_person_id': pid, 'description': l_desc, 'type': 'settlement', 'voucher_nature': 'receive_cash'})

            batch.set(db.collection('edit_logs').document(), {
                'firm_id': firm_id, 'link_id': link_id, 'edited_by': session['username'],
                'changes': "Modified Split Voucher", 'details': master_desc,
                'timestamp': int(time.time() * 1000),
                'date_formatted': datetime.now(IST).strftime('%d-%b-%Y %I:%M %p')
            })
            batch.commit()
            return redirect(request.referrer or url_for('index'))

        # --- POST HANDLING FOR STANDARD VOUCHER ---
        cat_raw = request.form.get('category', entry.get('category', ''))
        custom_cat = request.form.get('custom_category', '').strip()
        category = custom_cat if cat_raw == 'Other' and custom_cat else cat_raw
        if category and category not in existing_cats: db.collection('categories').add({'firm_id': firm_id, 'name': category})

        amount = float(request.form['amount'])
        desc = request.form.get('description', entry.get('description', '')).strip()

        changes = []
        if float(doc_data.get('amount', 0)) != amount: changes.append(f"Amt: ₹{doc_data.get('amount')} ➔ ₹{amount}")
        if doc_data.get('description', '') != desc: changes.append(f"Desc: {doc_data.get('description')} ➔ {desc}")
        if doc_data.get('category', '') != category: changes.append(f"Cat: {doc_data.get('category')} ➔ {category}")
        if doc_data.get('payment_mode', '') != mode: changes.append(f"Mode: {doc_data.get('payment_mode')} ➔ {mode}")
        if doc_data.get('date', '') != date_val: changes.append(f"Date: {doc_data.get('date')} ➔ {date_val}")
        
        ledger_context_label = "Main Cash Book"
        if has_link:
            new_account_raw = request.form.get('primary_account', 'main')
            new_account_name = request.form.get('new_account_name', '').strip()
            new_nature = request.form.get('txn_nature', current_nature)
            if current_nature != new_nature: changes.append(f"Nature: {current_nature} ➔ {new_nature}")

            new_account_type, new_primary_id, new_person_name = 'main', None, ''
            if new_account_raw == 'new_dasti':
                ref = db.collection('dasti_persons').document()
                ref.set({'user_id': firm_id, 'name': new_account_name, 'deleted': 0})
                new_primary_id, new_account_type, new_person_name = ref.id, 'dasti', new_account_name
                ledger_context_label = f"Dasti Ledger: {new_person_name}"
            elif new_account_raw == 'new_person':
                ref = db.collection('persons').document()
                ref.set({'user_id': firm_id, 'name': new_account_name, 'deleted': 0})
                new_primary_id, new_account_type, new_person_name = ref.id, 'person', new_account_name
                ledger_context_label = f"Person Ledger: {new_person_name}"
            elif new_account_raw.startswith('person_'):
                new_primary_id, new_account_type = new_account_raw.split('_', 1)[1], 'person'
                pd = db.collection('persons').document(new_primary_id).get().to_dict()
                new_person_name, ledger_context_label = (pd.get('name', ''), f"Person Ledger: {pd.get('name', '')}") if pd else ('', "Person")
            elif new_account_raw.startswith('dasti_'):
                new_primary_id, new_account_type = new_account_raw.split('_', 1)[1], 'dasti'
                dd = db.collection('dasti_persons').document(new_primary_id).get().to_dict()
                new_person_name, ledger_context_label = (dd.get('name', ''), f"Dasti Ledger: {dd.get('name', '')}") if dd else ('', "Dasti")

            if current_account_type != new_account_type: changes.append(f"Ledger Mode: {current_account_type} ➔ {new_account_type}")

            base_txn = {'user_id': firm_id, 'date': date_val, 'time': time_val, 'payment_mode': mode, 'category': category, 'amount': amount, 'link_id': link_id, 'status': new_status, 'approved_by': approved_by, 'deleted': entry.get('deleted', 0), 'created_at': entry.get('created_at', time.time()), 'is_flagged': is_flagged, 'voucher_nature': new_nature if new_account_type != 'main' else ('direct_in' if new_nature == 'receive_cash' else 'direct_out')}

            for coll, docs_list in linked_docs.items():
                for d in docs_list: batch.delete(db.collection(coll).document(d['id']))

            if new_account_type == 'main':
                batch.set(db.collection('transactions').document(), {**base_txn, 'description': desc, 'type': 'income' if new_nature == 'receive_cash' else 'expense'})
            elif new_account_type == 'person':
                if new_nature == 'slip_in':
                    batch.set(db.collection('person_ledger').document(), {**base_txn, 'person_id': new_primary_id, 'description': desc, 'type': 'settlement'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Slip ({new_person_name}): {desc}", 'type': 'batch_ledger_out'})
                elif new_nature == 'advance':
                    batch.set(db.collection('person_ledger').document(), {**base_txn, 'person_id': new_primary_id, 'description': desc, 'type': 'advance'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Transfer Out ({new_person_name}): {desc}", 'type': 'dasti_out'})
                elif new_nature == 'receive_cash':
                    batch.set(db.collection('person_ledger').document(), {**base_txn, 'person_id': new_primary_id, 'description': desc, 'type': 'settlement', 'voucher_nature': 'receive_cash'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Transfer In ({new_person_name}): {desc}", 'type': 'income', 'voucher_nature': 'receive_cash'})
            elif new_account_type == 'dasti':
                if new_nature == 'slip_in':
                    batch.set(db.collection('dasti_ledger').document(), {**base_txn, 'dasti_person_id': new_primary_id, 'description': desc, 'type': 'settlement'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Dasti Slip ({new_person_name}): {desc}", 'type': 'batch_ledger_out'})
                elif new_nature == 'advance':
                    batch.set(db.collection('dasti_ledger').document(), {**base_txn, 'dasti_person_id': new_primary_id, 'description': desc, 'type': 'advance'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Dasti Out ({new_person_name}): {desc}", 'type': 'dasti_voucher_out'})
                elif new_nature == 'receive_cash':
                    batch.set(db.collection('dasti_ledger').document(), {**base_txn, 'dasti_person_id': new_primary_id, 'description': desc, 'type': 'settlement', 'voucher_nature': 'receive_cash'})
                    batch.set(db.collection('transactions').document(), {**base_txn, 'description': f"Dasti In ({new_person_name}): {desc}", 'type': 'dasti_voucher_in', 'voucher_nature': 'receive_cash'})
        else:
            batch.update(doc_ref, {'date': date_val, 'time': time_val, 'payment_mode': mode, 'category': category, 'amount': amount, 'status': new_status, 'approved_by': approved_by, 'description': desc, 'type': request.form.get('type', entry.get('type')), 'is_flagged': is_flagged})

        if changes:
            batch.set(db.collection('edit_logs').document(), {'firm_id': firm_id, 'link_id': link_id, 'edited_by': session['username'], 'changes': " | ".join(changes), 'details': f"Ledger: {ledger_context_label} | Desc: {desc}", 'timestamp': int(time.time() * 1000), 'date_formatted': datetime.now(IST).strftime('%d-%b-%Y %I:%M %p')})

        batch.commit()
        return redirect(request.referrer or url_for('index'))

    return render_template_string(EDIT_TEMPLATE, entry=entry, table_name=table_name, categories=existing_cats, persons=persons, dasti_persons=dasti_persons, approvers=approvers, approver_names=approver_names, has_link=has_link, current_account_type=current_account_type, current_primary_id=current_primary_id, current_nature=current_nature, username=session['username'], is_split=is_split, splits_data=splits_data)

@app.route('/add_express', methods=['POST'])
def add_express():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    approver = request.form.get('approved_by_select', '')
    txn_status = 'approved' if approver else 'pending'
    category = request.form.get('category', 'General')
    
    db.collection('transactions').add({
        'user_id': session['firm_id'],
        'date': request.form['date'],
        'time': request.form['time'],
        'payment_mode': 'Cash',
        'category': category,
        'description': request.form['description'],
        'type': request.form['type'],
        'amount': float(request.form['amount']),
        'link_id': uuid.uuid4().hex[:12],
        'status': txn_status,
        'approved_by': approver,
        'deleted': 0,
        'created_at': time.time(),
        'voucher_nature': 'direct_in' if request.form['type'] == 'income' else 'direct_out',
        'is_flagged': 0
    })
    return redirect(request.referrer or url_for('index'))

@app.route('/add_split_voucher', methods=['POST'])
def add_split_voucher():
    if 'user_id' not in session: return redirect(url_for('login'))
    firm_id = session['firm_id']
    
    date_val, time_val, mode = request.form['date'], request.form['time'], request.form['payment_mode']
    master_desc = request.form['master_description'].strip()
    approver = request.form.get('approved_by_select', '')
    
    natures = request.form.getlist('txn_nature[]')
    accounts = request.form.getlist('primary_account[]')
    cats = request.form.getlist('category[]')
    amts = request.form.getlist('split_amount[]')

    # Total is ALWAYS computed on the server from the rows the user filled in -
    # never trust a client-supplied total.
    valid_rows = [(cats[i], natures[i], accounts[i], float(amts[i]))
                  for i in range(len(amts)) if amts[i].strip() and float(amts[i]) > 0]
    if not valid_rows:
        return redirect(request.referrer or url_for('index'))
    master_amount = sum(r[3] for r in valid_rows)

    # Direction of the single combined entry: only "Receive Cash" rows mean money
    # coming IN; if any row is Slip/Advance, the voucher counts as OUT.
    has_out = any(r[1] in ('slip_in', 'advance') for r in valid_rows)
    has_in = any(r[1] == 'receive_cash' for r in valid_rows)
    master_type = 'income' if (has_in and not has_out) else 'expense'
    master_nature = 'direct_in' if master_type == 'income' else 'direct_out'

    existing_cats = get_categories(firm_id)
    batch = db.batch()
    shared_link_id = uuid.uuid4().hex[:12]

    first_acc = valid_rows[0][2]
    display_name = "Main"
    if first_acc.startswith('person_'):
        display_name = db.collection('persons').document(first_acc.split('_')[1]).get().to_dict().get('name', 'Person')
    elif first_acc.startswith('dasti_'):
        display_name = db.collection('dasti_persons').document(first_acc.split('_')[1]).get().to_dict().get('name', 'Dasti')
    if len(valid_rows) > 1: display_name += " & Others"

    # SINGLE combined entry - type is 'income'/'expense' like a normal transaction,
    # so it is counted in the Main Cash Book balance AND shows as one line in the
    # Payments/Receipts tables.
    batch.set(db.collection('transactions').document(), {
        'user_id': firm_id, 'date': date_val, 'time': time_val, 'payment_mode': mode,
        'category': 'Split Settlement', 'amount': master_amount, 'link_id': shared_link_id,
        'status': 'approved' if approver else 'pending', 'approved_by': approver,
        'deleted': 0, 'created_at': time.time(), 'voucher_nature': master_nature,
        'description': f"{master_desc} ({display_name})", 'type': master_type
    })

    # Per-account breakdown legs - update each person/dasti account's own balance,
    # and (for a 'main' row) a memo entry used only to rebuild the Edit screen.
    # These are excluded from the Main Cash Book totals/lists so the voucher only
    # ever shows once.
    for cat, txn_nature, account_raw, amt in valid_rows:
        if cat not in existing_cats:
            db.collection('categories').add({'firm_id': firm_id, 'name': cat})
            existing_cats.append(cat)

        base_txn = {'user_id': firm_id, 'date': date_val, 'time': time_val, 'payment_mode': mode,
                     'category': cat, 'amount': amt, 'link_id': shared_link_id,
                     'status': 'approved' if approver else 'pending', 'approved_by': approver,
                     'deleted': 0, 'created_at': time.time(), 'is_flagged': 0}

        if account_raw == 'main':
            batch.set(db.collection('transactions').document(), {
                **base_txn, 'description': f"{master_desc} (Split-Gen)",
                'type': 'split_expense' if txn_nature in ('slip_in', 'advance') else 'split_income',
                'voucher_nature': txn_nature
            })
        elif account_raw.startswith('person_'):
            pid = account_raw.split('_')[1]
            p_name = db.collection('persons').document(pid).get().to_dict().get('name', '')
            l_desc = f"{master_desc} (Split: {p_name})"
            type_val = 'advance' if txn_nature == 'advance' else 'settlement'
            batch.set(db.collection('person_ledger').document(), {**base_txn, 'person_id': pid, 'description': l_desc, 'type': type_val, 'voucher_nature': txn_nature})
        elif account_raw.startswith('dasti_'):
            pid = account_raw.split('_')[1]
            p_name = db.collection('dasti_persons').document(pid).get().to_dict().get('name', '')
            l_desc = f"{master_desc} (Split: {p_name})"
            type_val = 'advance' if txn_nature == 'advance' else 'settlement'
            batch.set(db.collection('dasti_ledger').document(), {**base_txn, 'dasti_person_id': pid, 'description': l_desc, 'type': type_val, 'voucher_nature': txn_nature})

    batch.commit()
    return redirect(request.referrer or url_for('index'))


@app.route('/demo_game')
def demo_game():
    if 'user_id' not in session or session.get('role') != 'superadmin': return redirect(url_for('index'))
    settings = get_global_settings()
    return render_template_string(LOGIN_TEMPLATE, settings=settings, is_demo=True)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if has_users(): return "Setup complete. Ask the Superadmin to create an account for you.", 403
    if request.method == 'POST':
        new_user_ref = db.collection('users').document()
        user_id = new_user_ref.id
        
        username_raw = request.form['username'].strip()
        password_raw = request.form['password'].strip().lower()
        
        new_user_ref.set({
            'username': username_raw,
            'username_lower': username_raw.lower(),
            'password': password_raw,
            'firm_name': request.form['firm_name'],
            'firm_id': user_id,
            'role': 'superadmin',
            'can_approve': 1,
            'can_edit': 1,
            'can_express_cashout': 1,
            'can_view_reports': 1,
            'can_view_trash': 1,
            'can_delete_logs': 1,
            'can_view_ledger_details': 1,
            'idle_timeout_minutes': 15
        })
        
        session['user_id'] = user_id
        session['firm_id'] = user_id
        session['username'] = username_raw
        session['firm_name'] = request.form['firm_name']
        session['role'] = 'superadmin'
        session['can_approve'] = 1
        session['can_edit'] = 1
        session['can_express_cashout'] = 1
        session['can_view_reports'] = 1
        session['can_view_trash'] = 1
        session['can_delete_logs'] = 1
        session['can_view_ledger_details'] = 1 
        session['idle_timeout'] = 15
        
        opening_balance = float(request.form.get('opening_balance', 0))
        if opening_balance > 0:
            now = datetime.now(IST)
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
                'created_at': time.time(),
                'voucher_nature': 'direct_in',
                'is_flagged': 0
            })
            
        return redirect(url_for('index'))
    return render_template_string(REGISTER_TEMPLATE)

@app.route('/bulk_delete', methods=['POST'])
def bulk_delete():
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): 
        return redirect(request.referrer or url_for('index'))
    
    selected_links = request.form.getlist('selected_links')
    if not selected_links: 
        return redirect(request.referrer or url_for('index'))
    
    batch = db.batch()
    for link_id in selected_links:
        for collection in ['transactions', 'person_ledger', 'dasti_ledger']:
            docs = db.collection(collection).where('link_id', '==', link_id).where('user_id', '==', session['firm_id']).stream()
            for d in docs:
                batch.update(d.reference, {'deleted': 1})
                
    batch.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/edit_by_link/<string:link_id>')
def edit_by_link(link_id):
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'): 
        return redirect(url_for('index'))
        
    if link_id == 'bulk_edit':
        return redirect(url_for('logs'))
        
    firm_id = session['firm_id']
    
    # 1. Check Main Transactions First
    docs = list(db.collection('transactions').where('link_id', '==', link_id).where('user_id', '==', firm_id).limit(1).stream())
    if docs:
        return redirect(url_for('edit_entry', table_name='transactions', row_id=docs[0].id))
        
    # 2. If not found, check Person Ledger
    p_docs = list(db.collection('person_ledger').where('link_id', '==', link_id).where('user_id', '==', firm_id).limit(1).stream())
    if p_docs:
        return redirect(url_for('edit_entry', table_name='person_ledger', row_id=p_docs[0].id))
        
    # 3. If still not found, check Dasti Ledger
    d_docs = list(db.collection('dasti_ledger').where('link_id', '==', link_id).where('user_id', '==', firm_id).limit(1).stream())
    if d_docs:
        return redirect(url_for('edit_entry', table_name='dasti_ledger', row_id=d_docs[0].id))
        
    # Fallback if voucher was permanently deleted from the trash
    return redirect(url_for('logs'))

@app.route('/delete_person/<string:id>')
def delete_person(id):
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'):
        return redirect(url_for('persons'))
    doc_ref = db.collection('persons').document(id)
    doc_data = doc_ref.get().to_dict()
    if doc_data and doc_data.get('user_id') == session['firm_id']:
        doc_ref.update({'deleted': 1})
    return redirect(url_for('persons'))

@app.route('/delete_dasti_person/<string:id>')
def delete_dasti_person(id):
    if 'user_id' not in session or (session.get('can_edit') != 1 and session.get('role') != 'superadmin'):
        return redirect(url_for('dasti_ledger'))
    doc_ref = db.collection('dasti_persons').document(id)
    doc_data = doc_ref.get().to_dict()
    if doc_data and doc_data.get('user_id') == session['firm_id']:
        doc_ref.update({'deleted': 1})
    return redirect(url_for('dasti_ledger'))

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
