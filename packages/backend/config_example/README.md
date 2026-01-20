# 🔧 Configuration Examples

This folder contains example configuration files for the Nagisa AI configuration system, used for version control and new environment deployment.

## 📋 Usage

### 1. Initial Deployment
```bash
# Copy example configurations to actual config directory
cp -r backend/config_example backend/config
```

### 2. Configure Environment Variables
Create a `.env` file in the project root and fill in your settings:

```bash
# Environment Type
ENVIRONMENT=development  # Options: development, staging, production

# Required - LLM Configuration
LLM__TYPE=google
GOOGLE_API_KEY=your_actual_google_api_key_here
# OPENAI_API_KEY=your_actual_openai_api_key_here
# ANTHROPIC_API_KEY=your_actual_anthropic_api_key_here

# CORS Configuration
# For development, leave empty to use default localhost ports
# For production, specify your allowed domains (comma-separated)
CORS_ALLOWED_ORIGINS=
# Example for production:
# CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Optional - Other Services
# GOOGLE_CUSTOM_SEARCH_API_KEY=your_search_api_key_here
# GOOGLE_CUSTOM_SEARCH_ENGINE_ID=your_search_engine_id_here
```

### 3. Validate Configuration
```bash
cd backend
python -c "from config import get_llm_config; print('✅ Configuration validation successful')"
```

## ⚠️ Security Considerations

- ✅ **config_example/** - Version controlled, contains no sensitive information
- ❌ **config/** - In .gitignore, contains real API keys
- ❌ **.env** - In .gitignore, contains sensitive information

### CORS Security Best Practices

**⚠️ CRITICAL:** Never use `allow_origins=["*"]` in production with `allow_credentials=True`

✅ **Development Environment:**

- Default: Allows localhost ports (5173, 3000, 8000)
- Safe for local development
- Allows debugging headers

❌ **Production Environment - DO NOT DO:**

```python
# DANGEROUS: Allows ANY website to access your API with credentials
allow_origins=["*"]
allow_credentials=True
```

✅ **Production Environment - CORRECT:**

```python
# SAFE: Only allows your specific domains
allow_origins=["https://yourdomain.com", "https://www.yourdomain.com"]
allow_credentials=True
```

**Configuration Checklist:**

- [ ] Set `ENVIRONMENT=production` in production deployment
- [ ] Configure `CORS_ALLOWED_ORIGINS` with your actual domains
- [ ] Never commit API keys or production domains to version control
- [ ] Test CORS configuration before production deployment

## 📁 File Descriptions

- `__init__.py` - Main configuration entry point, provides backward compatible interface
- `llm.py` - LLM provider configurations (Google Gemini, OpenAI, Anthropic, etc.)
- `cors.py` - CORS (Cross-Origin Resource Sharing) security settings
- `dev.py` - Development environment settings
- `memory.py` - Memory and ChromaDB configurations
- `pfc.py` - PFC (Particle Flow Code) integration settings

## 🔄 Updating Configurations

When adding new configuration items:

1. Update actual configuration files in `config/`
2. Synchronously update example files in `config_example/` (remove sensitive information)
3. Commit changes to `config_example/` to version control
