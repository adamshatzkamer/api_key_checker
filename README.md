# 🔧 API Usage Dashboard

A comprehensive web-based dashboard for monitoring and managing API keys across multiple providers (OpenAI, Anthropic, Brave Search) with real-time usage tracking, cost analysis, and multi-account organization.

## ✨ Features

### 🏢 Multi-Account Management
- **Account Organization**: Group API keys by email/organization
- **Hierarchical Structure**: Organize keys within accounts for better management
- **Account Metadata**: Track names, organizations, and contact information

### 🔑 Advanced API Key Management
- **Multi-Provider Support**: OpenAI, Anthropic, and Brave Search APIs
- **Key Type Detection**: Automatically detect admin vs project keys
- **Secure Storage**: SQLite database with masked key display
- **Key Associations**: Link project keys to admin keys for better organization

### 📊 Real-Time Usage Monitoring
- **Live Usage Data**: Fetch real usage statistics from OpenAI's Usage API
- **Cost Tracking**: Monitor spending across all your API keys
- **Token Analytics**: Track input/output token consumption
- **Request Metrics**: Monitor API call frequency and patterns

### 🛡️ Security & Privacy
- **Masked Display**: API keys are masked in the interface by default
- **Secure Storage**: Full keys stored securely in local SQLite database
- **Copy Protection**: Show/hide functionality with secure copying
- **Local Deployment**: All data stays on your machine

### 🎨 Modern Interface
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Tabbed Navigation**: Clean interface with accounts, keys, and usage tabs
- **Real-time Updates**: Live data refresh without page reload
- **Error Handling**: Detailed error messages with actionable solutions

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/api-usage-dashboard.git
   cd api-usage-dashboard
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install flask flask-cors requests
   ```

4. **Run the dashboard**
   ```bash
   python dashboard.py
   ```

5. **Open your browser**
   Navigate to `http://localhost:5000`

## 📖 Usage Guide

### Setting Up Your First Account

1. **Navigate to the Accounts tab**
2. **Click "Add New Account"**
3. **Fill in your details:**
   - Email address (required)
   - Name (optional)
   - Organization (optional)
4. **Save the account**

### Adding API Keys

1. **Go to the API Keys tab**
2. **Click "Add New API Key"**
3. **Select an account from the dropdown**
4. **Enter key details:**
   - **Name**: Descriptive name (e.g., "OpenAI Production Key", "Brave Development", "Grok DD/MM/YY", etc.)
   - **API Key**: Your actual API key
   - **Admin Association**: For project keys, link to an admin key
5. **Test the key** (optional but recommended)
6. **Save the key**

### Monitoring Usage

1. **Switch to the Usage Dashboard tab**
2. **Select your time range** (7, 30, or 90 days)
3. **Click "Refresh Data"** to fetch latest usage statistics
4. **View metrics:**
   - Total cost across all keys
   - Request counts and token usage
   - Individual key performance
   - Error diagnostics and solutions

## 🔧 Configuration

### Supported API Providers

| Provider | Key Format | Features |
|----------|------------|----------|
| **OpenAI** | `sk-proj-*` (Project)<br>`sk-admin-*` (Admin) | ✅ Usage tracking<br>✅ Cost monitoring<br>✅ Token analytics |
| **Anthropic** | `sk-ant-*` | ✅ Key validation<br>❌ Usage API (not available) |
| **Brave Search** | `BSA*` | ✅ Key validation<br>✅ Basic usage (if available) |

### Key Types Explained

- **Admin Keys** (`sk-admin-*`): High-privilege keys with organization-wide access
- **Project Keys** (`sk-proj-*`): Scoped to specific projects, can be linked to admin keys
- **Legacy Keys** (`sk-*`): Older OpenAI format, treated as project keys

### Database Schema

The dashboard uses SQLite with two main tables:

```sql
-- Accounts table
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    organization_name TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- API Keys table  
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    full_key TEXT NOT NULL,
    masked_key TEXT NOT NULL,
    key_type TEXT DEFAULT 'project',
    provider TEXT DEFAULT 'openai',
    account_id INTEGER REFERENCES accounts(id),
    admin_key_id INTEGER REFERENCES api_keys(id),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## 🛠️ API Endpoints

The dashboard provides a REST API for programmatic access:

### Accounts
- `GET /api/accounts` - List all accounts
- `POST /api/accounts` - Create new account
- `PUT /api/accounts/{id}` - Update account
- `DELETE /api/accounts/{id}` - Delete account

### API Keys
- `GET /api/keys` - List all keys (masked)
- `POST /api/keys` - Add new key
- `PUT /api/keys/{id}` - Update key
- `DELETE /api/keys/{id}` - Delete key
- `GET /api/keys/{id}/full` - Get full key (for copying)
- `POST /api/keys/{id}/test` - Test key validity

### Usage Data
- `GET /api/usage?days={n}` - Fetch usage data for all admin keys

## 🔍 Troubleshooting

### Common Issues

#### ❌ "Permission Denied" or "Missing Scopes" Error
**Cause**: Your API key doesn't have the required permissions for the Usage API.

**Solutions**:
1. Create a new API key with "All" permissions in OpenAI dashboard
2. Ensure your role is "Owner" or "Admin" in the organization
3. Contact OpenAI support to request Usage API access (it's restricted)

#### ❌ "Authentication Failed" Error
**Cause**: Invalid or expired API key.

**Solutions**:
1. Check if the API key is correctly copied (no extra spaces)
2. Verify the key hasn't been revoked in your provider's dashboard
3. Ensure billing is enabled on your account

#### ❌ "No usage data available"
**Cause**: Most API keys cannot access usage monitoring endpoints.

**Solutions**:
1. Usage API access is highly restricted by OpenAI
2. Use OpenAI's web dashboard for official usage monitoring
3. This dashboard is still useful for key organization and testing

### Debug Mode

Enable debug output by running:
```bash
python dashboard.py
```

Check the console output for detailed error messages and API responses.

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Make your changes**
4. **Add tests** (if applicable)
5. **Commit your changes**
   ```bash
   git commit -m 'Add amazing feature'
   ```
6. **Push to the branch**
   ```bash
   git push origin feature/amazing-feature
   ```
7. **Open a Pull Request**

### Development Setup

For development, you might want to enable additional debugging:

```python
app.run(debug=True, host='0.0.0.0', port=5000)
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI** for providing the Usage API
- **Flask** for the excellent web framework
- **SQLite** for reliable local data storage
- **Contributors** who help improve this project

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/api-usage-dashboard/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/api-usage-dashboard/discussions)

---

**⭐ If this project helps you manage your API keys better, please consider giving it a star!**
