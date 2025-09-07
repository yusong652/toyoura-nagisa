# 本地服务优化策略：TTS和Text2Image服务迁移方案

## 当前架构分析

### 现状
1. **TTS服务**：
   - Fish Audio：通过Cloudflare访问远程API
   - GPT-SoVITS：本地服务（localhost:9880）

2. **Text2Image服务**：
   - ComfyUI：本地服务（localhost:8188）
   - 已配置多个本地模型

### 问题
- Fish Audio依赖外部API和网络延迟
- 需要API密钥管理
- 受Cloudflare限制影响

## 优化方案

### 方案A：Windows服务器本地化部署（推荐）⭐⭐⭐

将所有AI服务部署在Windows服务器上，完全本地化：

```
Windows服务器
├── aiNagisa主程序
├── ComfyUI (图像生成)
├── GPT-SoVITS (语音合成)
├── Fish Audio本地替代
└── 商业软件 (PFC等)
```

#### 实施步骤

1. **TTS服务本地化**

```powershell
# Windows上部署GPT-SoVITS
cd C:\AI_Services

# 克隆GPT-SoVITS
git clone https://github.com/RVC-Boss/GPT-SoVITS.git
cd GPT-SoVITS

# 安装依赖
pip install -r requirements.txt

# 下载预训练模型
python download_models.py

# 启动服务
python api.py --port 9880
```

2. **Fish Audio替代方案**

使用开源替代品：
- **Bert-VITS2**：高质量中文TTS
- **VALL-E-X**：微软开源的零样本TTS
- **Coqui TTS**：多语言TTS

```powershell
# 部署Bert-VITS2作为Fish Audio替代
git clone https://github.com/fishaudio/Bert-VITS2.git
cd Bert-VITS2
pip install -r requirements.txt
python server.py --port 9881
```

3. **ComfyUI优化**

```powershell
# Windows上ComfyUI已经是本地的
# 只需确保模型都下载到本地
cd C:\ComfyUI\models\checkpoints

# 下载所需模型
# hassaku, nova, janku, wai等
```

### 方案B：统一网关服务 ⭐⭐

创建统一的本地服务网关，智能路由：

```python
# backend/infrastructure/services/local_service_gateway.py
from fastapi import FastAPI
import httpx

class LocalServiceGateway:
    """统一的本地服务网关"""
    
    def __init__(self):
        self.services = {
            'tts': {
                'gpt_sovits': 'http://localhost:9880',
                'bert_vits2': 'http://localhost:9881',
                'coqui': 'http://localhost:9882'
            },
            'text2image': {
                'comfyui': 'http://localhost:8188',
                'stable_diffusion': 'http://localhost:7860'
            }
        }
        
    async def call_service(self, service_type: str, provider: str, data: dict):
        """统一的服务调用接口"""
        url = self.services[service_type][provider]
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data)
            return response.json()
```

### 方案C：混合部署 ⭐

保留部分云服务作为备份：

```python
# backend/config/service_routing.py
class ServiceRouter:
    """智能服务路由"""
    
    def __init__(self):
        self.local_services = {
            'tts': ['gpt_sovits', 'bert_vits2'],
            'text2image': ['comfyui']
        }
        
        self.cloud_services = {
            'tts': ['fish_audio'],  # 作为备份
            'text2image': ['dall-e', 'stability']  # 高质量备选
        }
    
    async def get_service(self, service_type: str, prefer_local: bool = True):
        """根据可用性和偏好选择服务"""
        if prefer_local:
            # 优先使用本地服务
            for service in self.local_services[service_type]:
                if await self.check_health(service):
                    return service
        
        # 降级到云服务
        return self.cloud_services[service_type][0]
```

## 配置迁移策略

### 1. 环境配置分离

```python
# backend/config/services.py
from pydantic import BaseSettings

class ServiceConfig(BaseSettings):
    """服务配置基类"""
    
    # 服务位置
    deployment_mode: str = "local"  # local, cloud, hybrid
    
    # TTS配置
    tts_provider: str = "gpt_sovits"  # 默认本地
    tts_fallback: str = "fish_audio"  # 备用云服务
    
    # Text2Image配置  
    text2image_provider: str = "comfyui"  # 默认本地
    text2image_fallback: str = "dall-e"  # 备用云服务
    
    class Config:
        env_prefix = "SERVICE_"
```

### 2. Windows服务管理

```powershell
# 创建Windows服务启动脚本
# C:\AI_Services\start_all_services.ps1

# 启动所有AI服务
Start-Process python -ArgumentList "C:\GPT-SoVITS\api.py" -WorkingDirectory "C:\GPT-SoVITS"
Start-Process python -ArgumentList "C:\ComfyUI\main.py" -WorkingDirectory "C:\ComfyUI"
Start-Process python -ArgumentList "C:\Bert-VITS2\server.py" -WorkingDirectory "C:\Bert-VITS2"

# 等待服务启动
Start-Sleep -Seconds 10

# 启动aiNagisa
Start-Process python -ArgumentList "C:\Projects\aiNagisa\backend\app.py"
```

### 3. Docker容器化（可选）

```yaml
# docker-compose.yml
version: '3.8'

services:
  gpt-sovits:
    build: ./gpt-sovits
    ports:
      - "9880:9880"
    volumes:
      - ./models/gpt-sovits:/app/models
      
  comfyui:
    build: ./comfyui
    ports:
      - "8188:8188"
    volumes:
      - ./models/comfyui:/app/models
      
  bert-vits2:
    build: ./bert-vits2
    ports:
      - "9881:9881"
    volumes:
      - ./models/bert-vits2:/app/models
      
  ainagisa:
    build: .
    ports:
      - "8000:8000"
      - "9000:9000"
    depends_on:
      - gpt-sovits
      - comfyui
      - bert-vits2
    environment:
      - TTS_PROVIDER=gpt_sovits
      - TEXT2IMAGE_PROVIDER=comfyui
```

## 性能优化

### 1. 服务预热
```python
# backend/infrastructure/services/service_warmup.py
async def warmup_services():
    """服务预热，减少首次调用延迟"""
    
    # 预热TTS
    await tts_service.synthesize("系统启动完成", warmup=True)
    
    # 预热Text2Image
    await text2image_service.generate("test", warmup=True)
    
    # 加载模型到显存
    await load_models_to_gpu()
```

### 2. 缓存策略
```python
# backend/infrastructure/services/cache.py
class ServiceCache:
    """服务结果缓存"""
    
    def __init__(self):
        self.tts_cache = {}  # 文本到音频缓存
        self.image_cache = {}  # 提示词到图像缓存
        
    async def get_or_generate_tts(self, text: str):
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self.tts_cache:
            return self.tts_cache[cache_key]
        
        audio = await generate_tts(text)
        self.tts_cache[cache_key] = audio
        return audio
```

### 3. GPU资源管理
```python
# backend/infrastructure/services/gpu_manager.py
class GPUResourceManager:
    """GPU资源管理器"""
    
    def __init__(self):
        self.gpu_memory_limit = 8192  # MB
        self.current_usage = 0
        
    async def allocate_for_service(self, service: str, required_memory: int):
        """为服务分配GPU内存"""
        if self.current_usage + required_memory > self.gpu_memory_limit:
            await self.free_unused_memory()
        
        self.current_usage += required_memory
        return True
```

## 迁移时间表

### Phase 1：评估（1天）
- [ ] 测试GPT-SoVITS性能
- [ ] 评估Bert-VITS2作为Fish Audio替代
- [ ] 确认ComfyUI模型完整性

### Phase 2：部署（2天）
- [ ] Windows服务器部署所有服务
- [ ] 配置服务启动脚本
- [ ] 测试服务连通性

### Phase 3：切换（1天）
- [ ] 更新配置指向本地服务
- [ ] 保留云服务作为备份
- [ ] 监控服务稳定性

### Phase 4：优化（持续）
- [ ] 实施缓存策略
- [ ] GPU资源优化
- [ ] 服务预热机制

## 预期收益

1. **延迟降低**：从300ms降至<50ms
2. **成本节省**：无需API调用费用
3. **隐私保护**：数据完全本地化
4. **稳定性提升**：不受网络影响
5. **可控性增强**：完全掌控服务

## 结论

推荐采用**方案A：Windows服务器本地化部署**，配合智能路由和缓存策略，实现：
- 完全本地化的AI服务
- 毫秒级响应延迟
- 零外部依赖
- 完整的数据隐私

这将使aiNagisa成为真正的离线可用、高性能的AI助手系统！