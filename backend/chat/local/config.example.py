"""
Configuration template for local model clients.

COPY THIS FILE TO config.py AND FILL IN YOUR ACTUAL VALUES.

This template provides configuration helpers for vLLM and Ollama clients
with support for HPC environments and local deployments.
"""

import os
from typing import Dict, Any, Optional
from backend.config import get_llm_specific_config

def get_local_model_config() -> Dict[str, Any]:
    """
    Get local model configuration.
    
    Returns:
        Dictionary containing local model settings
    """
    return {
        "vllm": get_vllm_config(),
        "ollama": get_ollama_config(),
        "hpc": get_hpc_config()
    }

def get_vllm_config() -> Dict[str, Any]:
    """
    Get vLLM client configuration.
    
    Returns:
        vLLM configuration dictionary
    """
    config = get_llm_specific_config("vllm")
    
    # Default vLLM configuration
    defaults = {
        "model_path": "microsoft/DialoGPT-medium",  # Default model
        "base_url": "http://localhost:8000",
        "gpu_memory_utilization": 0.9,
        "max_model_len": None,
        "tensor_parallel_size": 1,
        "auto_start": True,
        "health_check_interval": 30
    }
    
    # Merge with environment variables
    env_overrides = {
        "model_path": os.getenv("VLLM_MODEL_PATH"),
        "base_url": os.getenv("VLLM_BASE_URL"),
        "gpu_memory_utilization": float(os.getenv("VLLM_GPU_MEMORY", "0.9")),
        "max_model_len": int(os.getenv("VLLM_MAX_MODEL_LEN")) if os.getenv("VLLM_MAX_MODEL_LEN") else None,
        "tensor_parallel_size": int(os.getenv("VLLM_TENSOR_PARALLEL", "1")),
        "auto_start": os.getenv("VLLM_AUTO_START", "true").lower() == "true"
    }
    
    # Remove None values
    env_overrides = {k: v for k, v in env_overrides.items() if v is not None}
    
    # Priority: config file > environment > defaults
    final_config = {**defaults, **env_overrides, **config}
    
    return final_config

def get_ollama_config() -> Dict[str, Any]:
    """
    Get Ollama client configuration.
    
    Returns:
        Ollama configuration dictionary
    """
    config = get_llm_specific_config("ollama")
    
    # Default Ollama configuration
    defaults = {
        "model_name": "llama3.2:3b",
        "base_url": "http://localhost:11434",
        "auto_start": True,
        "auto_download": True,
        "health_check_interval": 30,
        "embedding_model": "nomic-embed-text",
        "whisper_model": "whisper:large"
    }
    
    # Merge with environment variables
    env_overrides = {
        "model_name": os.getenv("OLLAMA_MODEL"),
        "base_url": os.getenv("OLLAMA_BASE_URL"),
        "auto_start": os.getenv("OLLAMA_AUTO_START", "true").lower() == "true",
        "auto_download": os.getenv("OLLAMA_AUTO_DOWNLOAD", "true").lower() == "true",
        "embedding_model": os.getenv("OLLAMA_EMBEDDING_MODEL"),
        "whisper_model": os.getenv("OLLAMA_WHISPER_MODEL")
    }
    
    # Remove None values
    env_overrides = {k: v for k, v in env_overrides.items() if v is not None}
    
    # Priority: config file > environment > defaults
    final_config = {**defaults, **env_overrides, **config}
    
    return final_config

def get_hpc_config() -> Dict[str, Any]:
    """
    Get HPC (High Performance Computing) configuration.
    
    ⚠️  SECURITY NOTICE: Fill in your actual HPC credentials below.
    This file should be ignored by git to prevent credential leaks.
    
    Returns:
        HPC configuration dictionary
    """
    config = get_llm_specific_config("hpc")
    
    # 🔧 CONFIGURE YOUR HPC SETTINGS HERE 🔧
    defaults = {
        "enabled": False,  # ✅ Set to True to enable HPC distributed inference
        
        # 🔐 SSH Connection Configuration - REPLACE WITH YOUR VALUES
        "host": "YOUR_HPC_CLUSTER.edu",           # 🔧 Your HPC cluster address
        "username": "YOUR_USERNAME",              # 🔧 Your HPC username  
        "ssh_key_path": os.path.expanduser("~/.ssh/id_rsa"),  # 🔧 SSH private key path
        "ssh_port": 22,  # SSH port, usually 22
        
        # 📁 HPC Project Configuration
        "project_path": "/shared/ainagisa",       # 🔧 Project path on HPC
        "auto_start": True,
        "session_duration_hours": 8,             # Resource allocation duration
        
        # 💻 Resource Request Configuration
        "gpu_request": "gpu:1",      # Number of GPUs
        "cpu_request": "8",          # Number of CPU cores
        "memory_request": "32G",     # Memory size
        "queue_system": "tssrun",    # Queue system: "tssrun" or "slurm"
        "partition": "gpu",          # Partition name
        
        # 🔌 Port Mapping Configuration
        "tunnel_ports": {
            "vllm": 8000,        # vLLM service port
            "ollama": 11434,     # Ollama service port
            "local_base": 8000   # Local mapping base port
        },
        
        # 🤖 Model Path Configuration - REPLACE WITH YOUR PATHS
        "models": {
            "vllm": "/shared/models/YOUR_VLLM_MODEL",    # 🔧 vLLM model path on HPC
            "ollama": "llama3.2:3b"                      # 🔧 Ollama model name
        },
        
        # 🔗 SSH Connection Options
        "ssh_options": {
            "ServerAliveInterval": 30,
            "ServerAliveCountMax": 3,
            "StrictHostKeyChecking": "no",
            "ConnectTimeout": 10
        }
    }
    
    # Merge with environment variables
    env_overrides = {
        "enabled": os.getenv("HPC_ENABLED", "false").lower() == "true",
        "host": os.getenv("HPC_HOST"),
        "username": os.getenv("HPC_USERNAME"),
        "ssh_key_path": os.getenv("HPC_SSH_KEY"),
        "ssh_port": int(os.getenv("HPC_SSH_PORT", "22")),
        "project_path": os.getenv("HPC_PROJECT_PATH"),
        "session_duration_hours": int(os.getenv("HPC_SESSION_HOURS", "8")),
        "gpu_request": os.getenv("HPC_GPU_REQUEST"),
        "queue_system": os.getenv("HPC_QUEUE_SYSTEM"),
        "partition": os.getenv("HPC_PARTITION")
    }
    
    # Remove None values
    env_overrides = {k: v for k, v in env_overrides.items() if v is not None}
    
    # Priority: config file > environment > defaults
    final_config = {**defaults, **env_overrides, **config}
    
    return final_config

def get_local_model_recommendations() -> Dict[str, Dict[str, Any]]:
    """
    Get recommended models for different use cases.
    
    Returns:
        Dictionary of model recommendations
    """
    return {
        "chat": {
            "vllm": [
                {
                    "name": "Qwen/Qwen2.5-7B-Instruct",
                    "description": "Excellent multilingual chat model",
                    "size": "7B",
                    "memory_gb": 16
                },
                {
                    "name": "meta-llama/Llama-3.2-8B-Instruct",
                    "description": "Latest Llama model with strong performance",
                    "size": "8B", 
                    "memory_gb": 18
                }
            ],
            "ollama": [
                {
                    "name": "llama3.2:3b",
                    "description": "Lightweight Llama for CPU inference",
                    "size": "3B",
                    "memory_gb": 4
                },
                {
                    "name": "qwen2.5:7b",
                    "description": "Qwen model optimized for Ollama",
                    "size": "7B",
                    "memory_gb": 8
                }
            ]
        },
        "embedding": {
            "ollama": [
                {
                    "name": "nomic-embed-text",
                    "description": "High-quality text embeddings",
                    "dimension": 768
                },
                {
                    "name": "mxbai-embed-large",
                    "description": "Large embedding model for better accuracy",
                    "dimension": 1024
                }
            ]
        },
        "asr": {
            "ollama": [
                {
                    "name": "whisper:large",
                    "description": "OpenAI Whisper large model",
                    "languages": "multilingual"
                },
                {
                    "name": "whisper:medium",
                    "description": "Balanced accuracy and speed",
                    "languages": "multilingual"
                }
            ]
        }
    }

def validate_local_config() -> Dict[str, bool]:
    """
    Validate local model configuration.
    
    Returns:
        Dictionary indicating validation status for each component
    """
    results = {}
    
    # Validate vLLM config
    vllm_config = get_vllm_config()
    results["vllm"] = bool(vllm_config.get("model_path") and vllm_config.get("base_url"))
    
    # Validate Ollama config
    ollama_config = get_ollama_config()
    results["ollama"] = bool(ollama_config.get("model_name") and ollama_config.get("base_url"))
    
    # Validate HPC config (if enabled)
    hpc_config = get_hpc_config()
    if hpc_config.get("enabled"):
        results["hpc"] = bool(
            hpc_config.get("host") and 
            hpc_config.get("username") and 
            hpc_config.get("project_path") and
            hpc_config.get("host") != "YOUR_HPC_CLUSTER.edu" and
            hpc_config.get("username") != "YOUR_USERNAME"
        )
    else:
        results["hpc"] = True  # Not required if disabled
    
    return results