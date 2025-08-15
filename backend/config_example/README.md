# 🔧 Configuration Examples

This folder contains example configuration files for the Nagisa AI configuration system, used for version control and new environment deployment.

## 📋 Usage

### 1. Initial Deployment
```bash
# Copy example configurations to actual config directory
cp -r backend/config_example backend/config
```

### 2. Configure Environment Variables
Create a `backend/.env` file and fill in your API keys:

```bash
# Required - LLM Configuration
LLM__TYPE=gemini
GOOGLE_API_KEY=your_actual_google_api_key_here
# OPENAI_API_KEY=your_actual_openai_api_key_here  
# ANTHROPIC_API_KEY=your_actual_anthropic_api_key_here

# Optional - TTS Configuration
TTS__TYPE=gpt_sovits
# FISH_AUDIO_API_KEY=your_fish_audio_api_key_here
# FISH_AUDIO_REFERENCE_ID=your_reference_id_here

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

## 📁 File Descriptions

- `__init__.py` - Main configuration entry point, provides backward compatible interface
- `llm.py` - GPT, Gemini, Anthropic configurations
- `tts.py` - Fish Audio, GPT-SoVITS configurations  
- `email.py` - Email, authentication, search configurations
- `text_to_image.py` - Stable Diffusion configurations
- `base.py` - Base paths and common configurations

## 🔄 Updating Configurations

When adding new configuration items:

1. Update actual configuration files in `config/`
2. Synchronously update example files in `config_example/` (remove sensitive information)
3. Commit changes to `config_example/` to version control 