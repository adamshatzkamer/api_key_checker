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
import re

app = Flask(__name__)
CORS(app)  # Enable CORS for browser requests

# Database configuration
DB_FILE = 'api_keys.db'

def detect_key_type(api_key):
    """Detect API provider and key type based on format"""
    if api_key.startswith('sk-admin-'):
        return {'provider': 'openai', 'type': 'admin'}
    elif api_key.startswith('sk-proj-'):
        return {'provider': 'openai', 'type': 'project'}
    elif api_key.startswith('sk-'):
        # Check if it's DeepSeek (usually longer than OpenAI)
        if len(api_key) > 60:
            return {'provider': 'deepseek', 'type': 'api'}
        return {'provider': 'openai', 'type': 'project'}  # Default for older OpenAI formats
    elif api_key.startswith('sk-ant-'):
        return {'provider': 'anthropic', 'type': 'project'}
    elif api_key.startswith('BSA'):
        return {'provider': 'brave', 'type': 'search'}
    elif api_key.startswith('pub_'):
        return {'provider': 'newsdata', 'type': 'news'}
    elif api_key.startswith('gsk_'):
        return {'provider': 'groq', 'type': 'ai'}
    elif api_key.startswith('pplx-'):
        return {'provider': 'perplexity', 'type': 'ai'}
    elif api_key.startswith('AIzaSy'):
        return {'provider': 'gemini', 'type': 'ai'}
    elif api_key.startswith('AKIA') or api_key.startswith('ASIA'):
        return {'provider': 'aws', 'type': 'access_key'}
    elif api_key.startswith('claude-'):
        return {'provider': 'anthropic', 'type': 'claude'}
    elif api_key.startswith('hf_'):
        return {'provider': 'huggingface', 'type': 'token'}
    elif api_key.startswith('xai-'):
        return {'provider': 'xai', 'type': 'api'}
    elif api_key.startswith('rplx-'):
        return {'provider': 'replicate', 'type': 'api'}
    elif api_key.startswith('gcp_'):
        return {'provider': 'google_cloud', 'type': 'service_account'}
    elif len(api_key) == 32 and all(c in '0123456789abcdef' for c in api_key.lower()):
        # Could be NewsAPI.org or GNews - we'll need context or let user specify
        return {'provider': 'newsapi_org', 'type': 'news'}  # Default assumption
    elif len(api_key) == 36 and api_key.count('-') == 4:
        # UUID format - likely NewsAPI.ai
        return {'provider': 'newsapi_ai', 'type': 'news'}
    elif len(api_key) == 64 and all(c in '0123456789abcdef' for c in api_key.lower()):
        return {'provider': 'serpapi', 'type': 'search'}
    elif ':' in api_key and len(api_key) > 10:
        # Google CSE format (usually has colons)
        return {'provider': 'google_cse', 'type': 'search'}
    elif re.match(r'^[A-Za-z0-9]{39}$', api_key):
        return {'provider': 'gemini', 'type': 'api'}
    elif re.match(r'^[A-Za-z0-9_\-]{20,}$', api_key) and 'azure' in api_key.lower():
        return {'provider': 'azure', 'type': 'cognitive_services'}
    elif re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', api_key):
        return {'provider': 'microsoft', 'type': 'subscription_id'}
    else:
        return {'provider': 'unknown', 'type': 'unknown'}

def mask_api_key(full_key):
    """Create a masked version of the API key for display"""
    if len(full_key) > 20:
        prefix = full_key[:12]
        suffix = full_key[-6:]
        return f"{prefix}...{suffix}"
    return full_key[:8] + "..."

def init_database():
    """Initialize the SQLite database with required tables"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # Create accounts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                name TEXT,
                organization_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Database already exists with correct schema
        pass
        
        # Create usage_data table for storing API usage information
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id INTEGER,
                date TEXT,
                usage_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (key_id) REFERENCES api_keys (id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    try:
        yield conn
    finally:
        conn.close()

def validate_openai_key(api_key):
    """Validate an OpenAI API key by making a test request"""
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # Try to get models list - this is a lightweight operation
        response = requests.get(
            'https://api.openai.com/v1/models',
            headers=headers,
            timeout=10
        )
        
        return {
            'valid': response.status_code == 200,
            'status_code': response.status_code,
            'response': response.json() if response.status_code == 200 else response.text
        }
    except Exception as e:
        return {
            'valid': False,
            'status_code': None,
            'error': str(e)
        }

def validate_anthropic_key(api_key):
    """Validate an Anthropic API key"""
    try:
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        
        # Test with a minimal message
        data = {
            'model': 'claude-3-haiku-20240307',
            'max_tokens': 1,
            'messages': [{'role': 'user', 'content': 'Hi'}]
        }
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data,
            timeout=10
        )
        
        return {
            'valid': response.status_code == 200,
            'status_code': response.status_code,
            'response': response.json() if response.status_code == 200 else response.text
        }
    except Exception as e:
        return {
            'valid': False,
            'status_code': None,
            'error': str(e)
        }

def validate_api_key(api_key, provider=None):
    """Validate an API key based on its provider"""
    if not provider:
        key_info = detect_key_type(api_key)
        provider = key_info['provider']
    
    if provider == 'openai':
        return validate_openai_key(api_key)
    elif provider == 'anthropic':
        return validate_anthropic_key(api_key)
    else:
        # For other providers, we'll just mark as unknown for now
        return {
            'valid': None,
            'status_code': None,
            'message': f'Validation not implemented for {provider}'
        }

# Flask Routes

@app.route('/')
def index():
    """Serve the main dashboard HTML"""
    return render_template_string(open('enhanced_template.html').read())

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Get all accounts"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM accounts ORDER BY name')
        accounts = [dict(row) for row in cursor.fetchall()]
        return jsonify(accounts)

@app.route('/api/accounts', methods=['POST'])
def create_account():
    """Create a new account"""
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Account name is required'}), 400
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO accounts (name, description) VALUES (?, ?)',
                (data['name'], data.get('description', ''))
            )
            conn.commit()
            
            account_id = cursor.lastrowid
            cursor.execute('SELECT * FROM accounts WHERE id = ?', (account_id,))
            account = dict(cursor.fetchone())
            
            return jsonify(account), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Account name already exists'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/accounts/<int:account_id>', methods=['PUT'])
def update_account(account_id):
    """Update an account"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if account exists
            cursor.execute('SELECT id FROM accounts WHERE id = ?', (account_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Account not found'}), 404
            
            # Update account
            update_fields = []
            update_values = []
            
            if 'name' in data:
                update_fields.append('name = ?')
                update_values.append(data['name'])
            
            if 'description' in data:
                update_fields.append('description = ?')
                update_values.append(data['description'])
            
            if update_fields:
                update_values.append(account_id)
                cursor.execute(
                    f'UPDATE accounts SET {", ".join(update_fields)} WHERE id = ?',
                    update_values
                )
                conn.commit()
            
            # Return updated account
            cursor.execute('SELECT * FROM accounts WHERE id = ?', (account_id,))
            account = dict(cursor.fetchone())
            
            return jsonify(account)
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Account name already exists'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """Delete an account and all its API keys"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
            
            if cursor.rowcount == 0:
                return jsonify({'error': 'Account not found'}), 404
            
            conn.commit()
            return jsonify({'message': 'Account deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/keys', methods=['GET'])
def get_keys():
    """Get all API keys with account information"""
    account_id = request.args.get('account_id')
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if account_id:
            cursor.execute('''
                SELECT k.*, a.name as account_name 
                FROM api_keys k 
                LEFT JOIN accounts a ON k.account_id = a.id 
                WHERE k.account_id = ?
                ORDER BY k.name
            ''', (account_id,))
        else:
            cursor.execute('''
                SELECT k.*, a.name as account_name 
                FROM api_keys k 
                LEFT JOIN accounts a ON k.account_id = a.id 
                ORDER BY k.name
            ''')
        
        keys = []
        for row in cursor.fetchall():
            key_data = dict(row)
            key_data['masked_key'] = mask_api_key(key_data['full_key'])
            keys.append(key_data)
        
        return jsonify(keys)

@app.route('/api/keys', methods=['POST'])
def create_key():
    """Create a new API key"""
    data = request.get_json()
    
    if not data or 'name' not in data or 'full_key' not in data:
        return jsonify({'error': 'Name and full_key are required'}), 400
    
    try:
        # Detect key type
        key_info = detect_key_type(data['full_key'])
        
        # Validate key if possible
        validation_result = validate_api_key(data['full_key'], key_info['provider'])
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO api_keys (account_id, name, full_key, provider, key_type, masked_key, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (
                data.get('account_id'),
                data['name'],
                data['full_key'],
                key_info['provider'],
                key_info['type'],
                mask_api_key(data['full_key'])
            ))
            conn.commit()
            
            key_id = cursor.lastrowid
            cursor.execute('''
                SELECT k.*, a.name as account_name 
                FROM api_keys k 
                LEFT JOIN accounts a ON k.account_id = a.id 
                WHERE k.id = ?
            ''', (key_id,))
            
            key_data = dict(cursor.fetchone())
            key_data['masked_key'] = mask_api_key(key_data['full_key'])
            
            return jsonify(key_data), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/keys/<int:key_id>', methods=['PUT'])
def update_key(key_id):
    """Update an API key"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if key exists
            cursor.execute('SELECT * FROM api_keys WHERE id = ?', (key_id,))
            existing_key = cursor.fetchone()
            if not existing_key:
                return jsonify({'error': 'API key not found'}), 404
            
            # Update key
            update_fields = []
            update_values = []
            
            if 'name' in data:
                update_fields.append('name = ?')
                update_values.append(data['name'])
            
            if 'account_id' in data:
                update_fields.append('account_id = ?')
                update_values.append(data['account_id'])
            
            if 'full_key' in data:
                # If key value changed, re-detect type and validate
                key_info = detect_key_type(data['full_key'])
                validation_result = validate_api_key(data['full_key'], key_info['provider'])
                
                update_fields.extend(['full_key = ?', 'provider = ?', 'key_type = ?', 'masked_key = ?', 'updated_at = ?'])
                update_values.extend([
                    data['full_key'],
                    key_info['provider'],
                    key_info['type'],
                    mask_api_key(data['full_key']),
                    datetime.now().isoformat()
                ])
            
            if update_fields:
                update_fields.append('updated_at = ?')
                update_values.extend([datetime.now().isoformat(), key_id])
                
                cursor.execute(
                    f'UPDATE api_keys SET {", ".join(update_fields)} WHERE id = ?',
                    update_values
                )
                conn.commit()
            
            # Return updated key
            cursor.execute('''
                SELECT k.*, a.name as account_name 
                FROM api_keys k 
                LEFT JOIN accounts a ON k.account_id = a.id 
                WHERE k.id = ?
            ''', (key_id,))
            
            key_data = dict(cursor.fetchone())
            key_data['masked_key'] = mask_api_key(key_data['full_key'])
            
            return jsonify(key_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/keys/<int:key_id>', methods=['DELETE'])
def delete_key(key_id):
    """Delete an API key"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM api_keys WHERE id = ?', (key_id,))
            
            if cursor.rowcount == 0:
                return jsonify({'error': 'API key not found'}), 404
            
            conn.commit()
            return jsonify({'message': 'API key deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/keys/<int:key_id>/validate', methods=['POST'])
def validate_key_endpoint(key_id):
    """Validate a specific API key"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM api_keys WHERE id = ?', (key_id,))
            key_data = cursor.fetchone()
            
            if not key_data:
                return jsonify({'error': 'API key not found'}), 404
            
            key_data = dict(key_data)
            validation_result = validate_api_key(key_data['full_key'], key_data['provider'])
            
            # Update validation status in database
            cursor.execute('''
                UPDATE api_keys 
                SET is_valid = ?, last_checked = ? 
                WHERE id = ?
            ''', (
                validation_result.get('valid'),
                datetime.now().isoformat(),
                key_id
            ))
            conn.commit()
            
            return jsonify(validation_result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
