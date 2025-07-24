# 🔧 配置文件示例

这个文件夹包含了 Nagisa AI 配置系统的示例文件，用于版本控制和新环境部署。

## 📋 使用方法

### 1. 首次部署
```bash
# 复制示例配置到实际配置目录
cp -r backend/config_example backend/config
```

### 2. 配置环境变量
创建 `backend/.env` 文件并填入您的API密钥：

```bash
# 必需 - LLM配置
LLM__TYPE=gemini
GOOGLE_API_KEY=your_actual_google_api_key_here
# OPENAI_API_KEY=your_actual_openai_api_key_here  
# ANTHROPIC_API_KEY=your_actual_anthropic_api_key_here

# 可选 - TTS配置
TTS__TYPE=gpt_sovits
# FISH_AUDIO_API_KEY=your_fish_audio_api_key_here
# FISH_AUDIO_REFERENCE_ID=your_reference_id_here

# 可选 - 其他服务
# GOOGLE_CUSTOM_SEARCH_API_KEY=your_search_api_key_here
# GOOGLE_CUSTOM_SEARCH_ENGINE_ID=your_search_engine_id_here
# MODELS_LAB_API_KEY=your_models_lab_api_key_here
```

### 3. 验证配置
```bash
cd backend
python -c "from config import get_llm_config; print('✅ 配置验证成功')"
```

## ⚠️ 安全注意事项

- ✅ **config_example/** - 版本控制，不包含敏感信息
- ❌ **config/** - 在 .gitignore 中，包含真实API密钥
- ❌ **.env** - 在 .gitignore 中，包含敏感信息

## 📁 文件说明

- `__init__.py` - 主配置入口，提供向后兼容的接口
- `llm.py` - GPT、Gemini、Anthropic 配置
- `tts.py` - Fish Audio、GPT-SoVITS 配置  
- `email.py` - 邮件、认证、搜索配置
- `text_to_image.py` - Models Lab、Stable Diffusion 配置
- `base.py` - 基础路径和通用配置

## 🔄 更新配置

当添加新的配置项时：

1. 更新 `config/` 中的实际配置文件
2. 同步更新 `config_example/` 中的示例文件（移除敏感信息）
3. 提交 `config_example/` 的更改到版本控制 