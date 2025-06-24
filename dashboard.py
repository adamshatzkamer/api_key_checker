#!/usr/bin/env python3
"""
OpenAI API Usage Dashboard Backend with SQLite Database
Run this Python server to fetch real usage data from OpenAI's API
"""

from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS
import requests
import time
import json
import sqlite3
import os
from datetime import datetime, timedelta
from contextlib import contextmanager

app = Flask(__name__)
CORS(app)  # Enable CORS for browser requests

# Database configuration
DB_FILE = 'api_keys.db'

def init_database():
    """Initialize the SQLite database"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                name TEXT,
                organization_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                full_key TEXT NOT NULL,
                masked_key TEXT NOT NULL,
                key_type TEXT DEFAULT 'project',
                account_id INTEGER,
                admin_key_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts (id),
                FOREIGN KEY (admin_key_id) REFERENCES api_keys (id),
                UNIQUE(name, account_id)
            )
        ''')
        
        # Create default account if none exists
        conn.execute('''
            INSERT OR IGNORE INTO accounts (email, name, organization_name) 
            VALUES ('adam@shatzkamer.com', 'Adam Shatzkamer', 'AstraMedia')
        ''')
        
        conn.commit()

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    try:
        yield conn
    finally:
        conn.close()

def mask_api_key(full_key):
    """Create a masked version of the API key for display"""
    if len(full_key) > 20:
        prefix = full_key[:12]
        suffix = full_key[-6:]
        return f"{prefix}...{suffix}"
    return full_key[:8] + "..."

# Account Management Functions
def get_all_accounts():
    """Get all accounts from database"""
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM accounts ORDER BY email')
        return [dict(row) for row in cursor.fetchall()]

def add_account(email, name, organization_name):
    """Add a new account to database"""
    with get_db() as conn:
        cursor = conn.execute(
            'INSERT INTO accounts (email, name, organization_name) VALUES (?, ?, ?)',
            (email, name, organization_name)
        )
        conn.commit()
        return cursor.lastrowid

def get_account_by_id(account_id):
    """Get a single account by ID"""
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM accounts WHERE id = ?', (account_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_account(account_id, email, name, organization_name):
    """Update an existing account"""
    with get_db() as conn:
        conn.execute(
            'UPDATE accounts SET email = ?, name = ?, organization_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (email, name, organization_name, account_id)
        )
        conn.commit()

def delete_account(account_id):
    """Delete an account and all associated keys"""
    with get_db() as conn:
        # Delete associated keys first
        conn.execute('DELETE FROM api_keys WHERE account_id = ?', (account_id,))
        # Delete account
        conn.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
        conn.commit()

def get_admin_keys_for_account(account_id):
    """Get all admin keys for a specific account"""
    with get_db() as conn:
        cursor = conn.execute('''
            SELECT id, name, masked_key 
            FROM api_keys 
            WHERE account_id = ? AND key_type = 'admin' 
            ORDER BY name
        ''', (account_id,))
        return [dict(row) for row in cursor.fetchall()]

# API Key Management Functions
def get_all_keys():
    """Get all API keys from database with admin associations and account info"""
    with get_db() as conn:
        cursor = conn.execute('''
            SELECT k.id, k.name, k.full_key, k.masked_key, k.key_type, k.account_id, k.admin_key_id,
                   admin.name as admin_name, admin.full_key as admin_full_key,
                   a.email as account_email, a.name as account_name, a.organization_name
            FROM api_keys k
            LEFT JOIN api_keys admin ON k.admin_key_id = admin.id
            LEFT JOIN accounts a ON k.account_id = a.id
            ORDER BY a.email, k.name
        ''')
        return [dict(row) for row in cursor.fetchall()]

def get_key_by_id(key_id):
    """Get a single API key by ID with admin association and account info"""
    with get_db() as conn:
        cursor = conn.execute('''
            SELECT k.id, k.name, k.full_key, k.masked_key, k.key_type, k.account_id, k.admin_key_id,
                   admin.name as admin_name, admin.full_key as admin_full_key,
                   a.email as account_email, a.name as account_name, a.organization_name
            FROM api_keys k
            LEFT JOIN api_keys admin ON k.admin_key_id = admin.id
            LEFT JOIN accounts a ON k.account_id = a.id
            WHERE k.id = ?
        ''', (key_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def add_key(name, full_key, key_type='project', account_id=None, admin_key_id=None):
    """Add a new API key to database"""
    masked_key = mask_api_key(full_key)
    with get_db() as conn:
        cursor = conn.execute(
            'INSERT INTO api_keys (name, full_key, masked_key, key_type, account_id, admin_key_id) VALUES (?, ?, ?, ?, ?, ?)',
            (name, full_key, masked_key, key_type, account_id, admin_key_id)
        )
        conn.commit()
        return cursor.lastrowid

def update_key(key_id, name, full_key=None, account_id=None, admin_key_id=None):
    """Update an existing API key"""
    with get_db() as conn:
        if full_key:
            masked_key = mask_api_key(full_key)
            conn.execute(
                'UPDATE api_keys SET name = ?, full_key = ?, masked_key = ?, account_id = ?, admin_key_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (name, full_key, masked_key, account_id, admin_key_id, key_id)
            )
        else:
            conn.execute(
                'UPDATE api_keys SET name = ?, account_id = ?, admin_key_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (name, account_id, admin_key_id, key_id)
            )
        conn.commit()

def delete_key(key_id):
    """Delete an API key from database"""
    with get_db() as conn:
        conn.execute('DELETE FROM api_keys WHERE id = ?', (key_id,))
        conn.commit()

def check_name_exists(name, account_id, exclude_id=None):
    """Check if a key name already exists for this account"""
    with get_db() as conn:
        if exclude_id:
            cursor = conn.execute('SELECT COUNT(*) FROM api_keys WHERE name = ? AND account_id = ? AND id != ?', (name, account_id, exclude_id))
        else:
            cursor = conn.execute('SELECT COUNT(*) FROM api_keys WHERE name = ? AND account_id = ?', (name, account_id))
        return cursor.fetchone()[0] > 0

def detect_key_type(api_key):
    """Detect if key is admin or project based on prefix"""
    if api_key.startswith('sk-admin-'):
        return 'admin'
    elif api_key.startswith('sk-proj-'):
        return 'project'
    else:
        return 'project'  # Default for older key formats

def get_error_details(error_message, status_code):
    """Map HTTP status codes to user-friendly error messages"""
    error_mappings = {
        401: {
            "icon": "🔑",
            "title": "Authentication Failed",
            "description": "Your API key is invalid, expired, or doesn't have proper permissions.",
            "solutions": [
                "Check if the API key is correctly copied (no extra spaces)",
                "Verify the key hasn't been revoked in OpenAI dashboard", 
                "Ensure the key has billing enabled on your OpenAI account",
                "Check if the key belongs to the correct organization"
            ]
        },
        403: {
            "icon": "🚫", 
            "title": "Permission Denied",
            "description": "Your API key doesn't have access to the Usage API or your organization.",
            "solutions": [
                "Upgrade to a paid OpenAI plan (Usage API requires billing)",
                "Contact OpenAI support to enable Usage API access",
                "Check if you're part of the correct organization",
                "Verify your account has admin permissions for usage data"
            ]
        },
        429: {
            "icon": "⏱️",
            "title": "Rate Limited", 
            "description": "You're making too many requests. OpenAI has temporarily blocked further calls.",
            "solutions": [
                "Wait a few minutes before trying again",
                "Reduce the frequency of dashboard refreshes",
                "Consider upgrading your OpenAI plan for higher limits",
                "Implement exponential backoff in your requests"
            ]
        },
        500: {
            "icon": "🔧",
            "title": "OpenAI Server Error",
            "description": "OpenAI's servers are experiencing issues. This is not your fault.",
            "solutions": [
                "Wait a few minutes and try again",
                "Check OpenAI's status page (status.openai.com)",
                "Try again during off-peak hours", 
                "Contact OpenAI support if the issue persists"
            ]
        },
        404: {
            "icon": "❓",
            "title": "Endpoint Not Found",
            "description": "The Usage API endpoint doesn't exist or has changed.",
            "solutions": [
                "Check if your account has access to the new Usage API",
                "Verify you're on a paid OpenAI plan",
                "Update to the latest API version",
                "Contact support if you believe this is an error"
            ]
        }
    }
    
    return error_mappings.get(status_code, {
        "icon": "⚠️",
        "title": "Unknown Error",
        "description": error_message,
        "solutions": [
            "Check your internet connection",
            "Verify the API key is correct", 
            "Try refreshing the page",
            "Contact support if the issue persists"
        ]
    })

def fetch_openai_usage(api_key, days=30):
    """Fetch usage data from OpenAI's Usage API with fallback"""
    start_time = int(time.time()) - (days * 24 * 60 * 60)
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    result = {}
    
    # Test basic authentication first
    try:
        print(f"Testing basic API access...")
        models_response = requests.get(
            'https://api.openai.com/v1/models',
            headers=headers,
            timeout=10
        )
        
        if models_response.status_code != 200:
            result['error'] = f"Basic API test failed: {models_response.status_code} - {models_response.text}"
            result['error_details'] = get_error_details(models_response.text, models_response.status_code)
            result['status'] = 'error'
            result['status_code'] = models_response.status_code
            return result
        
        print(f"✓ Basic API access works")
        
    except requests.exceptions.RequestException as e:
        result['error'] = f"Network error during basic test: {str(e)}"
        result['error_details'] = get_error_details(str(e), None)
        result['status'] = 'error'
        return result
    
    # Now try Usage API
    usage_params = {
        'start_time': start_time,
        'bucket_width': '1d',
        'limit': days
    }
    
    try:
        print(f"Testing Usage API access...")
        usage_response = requests.get(
            'https://api.openai.com/v1/organization/usage/completions',
            headers=headers,
            params=usage_params,
            timeout=10
        )
        
        if usage_response.status_code == 200:
            print(f"✓ Usage API access works")
            result['usage'] = usage_response.json()
            result['status'] = 'success'
        else:
            print(f"✗ Usage API failed: {usage_response.status_code}")
            # If Usage API fails but basic API works, show partial success
            result['usage_error'] = {
                'error': f"Usage API failed: {usage_response.status_code} - {usage_response.text}",
                'error_details': get_error_details(usage_response.text, usage_response.status_code)
            }
            result['status'] = 'partial'  # New status for partial success
            
    except requests.exceptions.RequestException as e:
        result['usage_error'] = {
            'error': f"Usage API network error: {str(e)}",
            'error_details': get_error_details(str(e), None)
        }
        result['status'] = 'partial'
    
    # Try Costs API only if we got this far
    if result.get('status') in ['success', 'partial']:
        costs_params = {
            'start_time': start_time,
            'bucket_width': '1d',
            'limit': days
        }
        
        try:
            print(f"Testing Costs API access...")
            costs_response = requests.get(
                'https://api.openai.com/v1/organization/costs',
                headers=headers,
                params=costs_params,
                timeout=10
            )
            
            if costs_response.status_code == 200:
                print(f"✓ Costs API access works")
                result['costs'] = costs_response.json()
            else:
                print(f"✗ Costs API failed: {costs_response.status_code}")
                result['costs_error'] = {
                    'error': f"Costs API failed: {costs_response.status_code} - {costs_response.text}",
                    'error_details': get_error_details(costs_response.text, costs_response.status_code)
                }
                
        except requests.exceptions.RequestException as e:
            result['costs_error'] = {
                'error': f"Costs API network error: {str(e)}",
                'error_details': get_error_details(str(e), None)
            }
    
    # If we only have basic API access, that's still something
    if result.get('status') is None:
        result['status'] = 'basic_only'
        result['message'] = "API key works for basic calls but not Usage/Costs APIs"
    
    return result

# Flask Routes

@app.route('/')
def dashboard():
    """Serve the HTML dashboard"""
    # Read the HTML template file
    try:
        with open('enhanced_template.html', 'r') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return """
        <h1>Template file not found</h1>
        <p>Please make sure 'enhanced_template.html' exists in the same directory as dashboard.py</p>
        """, 404

# Account Management Routes
@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Get all accounts"""
    accounts = get_all_accounts()
    return jsonify(accounts)

@app.route('/api/accounts', methods=['POST'])
def add_account_endpoint():
    """Add a new account"""
    data = request.get_json()
    
    if not data or 'email' not in data:
        return jsonify({'error': 'Email is required'}), 400
    
    email = data['email'].strip()
    name = data.get('name', '').strip()
    organization_name = data.get('organization_name', '').strip()
    
    try:
        account_id = add_account(email, name, organization_name)
        return jsonify({
            'id': account_id,
            'email': email,
            'name': name,
            'organization_name': organization_name
        }), 201
    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            return jsonify({'error': 'Account with this email already exists'}), 400
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/accounts/<account_id>', methods=['PUT'])
def update_account_endpoint(account_id):
    """Update an existing account"""
    data = request.get_json()
    
    if not data or 'email' not in data:
        return jsonify({'error': 'Email is required'}), 400
    
    account = get_account_by_id(account_id)
    if not account:
        return jsonify({'error': 'Account not found'}), 404
    
    email = data['email'].strip()
    name = data.get('name', '').strip()
    organization_name = data.get('organization_name', '').strip()
    
    try:
        update_account(account_id, email, name, organization_name)
        return jsonify({
            'id': int(account_id),
            'email': email,
            'name': name,
            'organization_name': organization_name
        })
    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            return jsonify({'error': 'Account with this email already exists'}), 400
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/accounts/<account_id>', methods=['DELETE'])
def delete_account_endpoint(account_id):
    """Delete an account and all associated keys"""
    account = get_account_by_id(account_id)
    if not account:
        return jsonify({'error': 'Account not found'}), 404
    
    try:
        delete_account(account_id)
        return jsonify({'message': 'Account and associated keys deleted successfully'})
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/accounts/<account_id>/admin-keys', methods=['GET'])
def get_account_admin_keys(account_id):
    """Get all admin keys for a specific account"""
    admin_keys = get_admin_keys_for_account(account_id)
    return jsonify(admin_keys)

# API Key Management Routes
@app.route('/api/keys', methods=['GET'])
def get_keys():
    """Get all API keys (masked) with admin associations"""
    keys = get_all_keys()
    return jsonify([{
        'id': str(key['id']),
        'name': key['name'],
        'key': key['masked_key'],
        'key_type': key['key_type'],
        'account_id': key['account_id'],
        'admin_key_id': key['admin_key_id'],
        'admin_name': key['admin_name'],
        'account_email': key['account_email'],
        'account_name': key['account_name'],
        'organization_name': key['organization_name']
    } for key in keys])

@app.route('/api/keys', methods=['POST'])
def add_key_endpoint():
    """Add a new API key"""
    data = request.get_json()
    
    if not data or 'name' not in data or 'full_key' not in data:
        return jsonify({'error': 'Name and API key are required'}), 400
    
    name = data['name'].strip()
    full_key = data['full_key'].strip()
    account_id = data.get('account_id')
    admin_key_id = data.get('admin_key_id')
    
    if not full_key.startswith('sk-'):
        return jsonify({'error': 'Invalid OpenAI API key format - must start with sk-'}), 400
    
    if not account_id:
        return jsonify({'error': 'Account ID is required'}), 400
    
    # Auto-detect key type
    key_type = detect_key_type(full_key)
    
    # Check for duplicate names in this account
    if check_name_exists(name, account_id):
        return jsonify({'error': 'API key name already exists for this account'}), 400
    
    try:
        key_id = add_key(name, full_key, key_type, account_id, admin_key_id)
        return jsonify({
            'id': str(key_id),
            'name': name,
            'key': mask_api_key(full_key),
            'key_type': key_type
        }), 201
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/keys/<key_id>', methods=['PUT'])
def update_key_endpoint(key_id):
    """Update an existing API key"""
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Name is required'}), 400
    
    key = get_key_by_id(key_id)
    if not key:
        return jsonify({'error': 'API key not found'}), 404
    
    name = data['name'].strip()
    account_id = data.get('account_id', key['account_id'])
    admin_key_id = data.get('admin_key_id')
    
    # Check for duplicate names (excluding current key)
    if check_name_exists(name, account_id, exclude_id=key_id):
        return jsonify({'error': 'API key name already exists for this account'}), 400
    
    # Handle API key update
    full_key = None
    if 'full_key' in data and data['full_key'].strip():
        full_key = data['full_key'].strip()
        if not full_key.startswith('sk-'):
            return jsonify({'error': 'Invalid OpenAI API key format - must start with sk-'}), 400
    
    try:
        update_key(key_id, name, full_key, account_id, admin_key_id)
        updated_key = get_key_by_id(key_id)
        return jsonify({
            'id': str(updated_key['id']),
            'name': updated_key['name'],
            'key': updated_key['masked_key'],
            'key_type': updated_key['key_type'],
            'account_id': updated_key['account_id'],
            'admin_key_id': updated_key['admin_key_id']
        })
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/keys/<key_id>', methods=['DELETE'])
def delete_key_endpoint(key_id):
    """Delete an API key"""
    key = get_key_by_id(key_id)
    if not key:
        return jsonify({'error': 'API key not found'}), 404
    
    try:
        delete_key(key_id)
        return jsonify({'message': 'API key deleted successfully'})
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/keys/<key_id>/test', methods=['POST'])
def test_key_endpoint(key_id):
    """Test an API key by making a simple request"""
    key = get_key_by_id(key_id)
    if not key:
        return jsonify({'error': 'API key not found'}), 404
    
    try:
        # Make a simple request to test the key
        headers = {
            'Authorization': f'Bearer {key["full_key"]}',
            'Content-Type': 'application/json'
        }
        
        # Try to get models list (simpler than usage API)
        response = requests.get(
            'https://api.openai.com/v1/models',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return jsonify({
                'status': 'success',
                'message': 'API key is valid and working'
            })
        else:
            error_details = get_error_details(response.text, response.status_code)
            return jsonify({
                'status': 'error',
                'message': f'API key test failed: {response.status_code}',
                'error_details': error_details
            }), 400
            
    except requests.exceptions.RequestException as e:
        return jsonify({
            'status': 'error',
            'message': f'Network error: {str(e)}'
        }), 500

@app.route('/api/usage')
def get_usage():
    """API endpoint to fetch usage data only for admin keys, with associated project keys shown as inventory"""
    days = request.args.get('days', 30, type=int)
    
    results = {}
    all_keys = get_all_keys()
    
    # Group keys by account and separate admin from project keys
    admin_keys = [key for key in all_keys if key['key_type'] == 'admin']
    project_keys = [key for key in all_keys if key['key_type'] == 'project']
    
    print(f"Found {len(admin_keys)} admin keys and {len(project_keys)} project keys")
    
    # Process admin keys - fetch actual usage data
    for admin_key in admin_keys:
        print(f"Fetching usage for admin key: {admin_key['name']} - Account: {admin_key['account_email']}")
        
        # Fetch usage data for admin key
        usage_data = fetch_openai_usage(admin_key['full_key'], days)
        
        # Find associated project keys for this admin key
        associated_projects = [
            {
                'id': str(proj['id']),
                'name': proj['name'],
                'key': proj['masked_key']
            }
            for proj in project_keys 
            if proj['admin_key_id'] == admin_key['id']
        ]
        
        # Add metadata
        usage_data['usage_key_source'] = 'admin key direct access'
        usage_data['associated_project_keys'] = associated_projects
        usage_data['project_key_count'] = len(associated_projects)
        
        # Combine admin key info with usage data
        results[admin_key['name']] = {
            'id': str(admin_key['id']),
            'name': admin_key['name'],
            'key': admin_key['masked_key'],
            'key_type': admin_key['key_type'],
            'account_email': admin_key['account_email'],
            'account_name': admin_key['account_name'],
            'organization_name': admin_key['organization_name'],
            'admin_name': None,  # This IS the admin key
            **usage_data
        }
        
        # Add small delay to avoid rate limiting
        time.sleep(0.5)
    
    # Process orphaned project keys (no admin key association)
    orphaned_projects = [key for key in project_keys if not key['admin_key_id']]
    
    for orphaned_key in orphaned_projects:
        print(f"Testing orphaned project key: {orphaned_key['name']} - Account: {orphaned_key['account_email']}")
        
        # Test basic connectivity only (no usage data expected)
        usage_data = fetch_openai_usage(orphaned_key['full_key'], days)
        usage_data['usage_key_source'] = 'orphaned project key (limited access)'
        usage_data['associated_project_keys'] = []
        usage_data['project_key_count'] = 0
        usage_data['note'] = 'Project key without admin association - consider linking to an admin key for usage data'
        
        results[orphaned_key['name']] = {
            'id': str(orphaned_key['id']),
            'name': orphaned_key['name'],
            'key': orphaned_key['masked_key'],
            'key_type': orphaned_key['key_type'],
            'account_email': orphaned_key['account_email'],
            'account_name': orphaned_key['account_name'],
            'organization_name': orphaned_key['organization_name'],
            'admin_name': None,
            **usage_data
        }
        
        time.sleep(0.5)
    
    print(f"Processed {len(admin_keys)} admin keys and {len(orphaned_projects)} orphaned project keys")
    return jsonify(results)

if __name__ == '__main__':
    print("🚀 Starting OpenAI Usage Dashboard with SQLite Database...")
    print("📊 Dashboard will be available at: http://localhost:5000")
    print("🔧 Make sure you have the required packages: pip install flask flask-cors requests")
    print("💾 Database file: api_keys.db")
    
    # Initialize database
    if not os.path.exists(DB_FILE):
        print("📦 Creating new database...")
        init_database()
        print("✅ Database initialized!")
    else:
        print("📂 Using existing database...")
        # Make sure we have the latest schema
        init_database()
    
    app.run(debug=True, host='0.0.0.0', port=5000)