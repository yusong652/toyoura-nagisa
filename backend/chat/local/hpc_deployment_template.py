"""
HPC Deployment Templates and Scripts

Simple templates for quick HPC deployment setup.
"""

import os
from pathlib import Path
from typing import Dict, Any

class HpcDeploymentTemplate:
    """Generates deployment scripts and configurations for HPC."""
    
    @staticmethod
    def generate_vllm_script(model_path: str, 
                           port: int = 8000,
                           gpu_memory_util: float = 0.9,
                           **kwargs) -> str:
        """Generate vLLM deployment script for HPC."""
        
        return f"""#!/bin/bash
#SBATCH --job-name=vllm_persistent
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --time=08:00:00
#SBATCH --output=vllm_%j.out
#SBATCH --error=vllm_%j.err

echo "=== vLLM Persistent Server Starting ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "GPU: $CUDA_VISIBLE_DEVICES"
echo "Model: {model_path}"
echo "Port: {port}"
echo "Start time: $(date)"

# Load modules
module load cuda/11.8
module load python/3.9

# Set environment
export CUDA_VISIBLE_DEVICES=0

# Create session directory
mkdir -p /tmp/llm_sessions
echo "vllm_running" > /tmp/llm_sessions/$SLURM_JOB_ID

# Start vLLM server
echo "Starting vLLM server..."
python -m vllm.entrypoints.openai.api_server \\
    --model {model_path} \\
    --host 0.0.0.0 \\
    --port {port} \\
    --gpu-memory-utilization {gpu_memory_util} \\
    --tensor-parallel-size 1 \\
    --max-model-len 4096 &

VLLM_PID=$!
echo "vLLM started with PID: $VLLM_PID"

# Wait for service to be ready
echo "Waiting for vLLM to initialize..."
for i in {{1..60}}; do
    if curl -s http://localhost:{port}/health > /dev/null; then
        echo "✅ vLLM is ready!"
        break
    fi
    echo "Waiting... ($i/60)"
    sleep 5
done

# Keep session alive
echo "vLLM server is running. Keeping session alive..."
while kill -0 $VLLM_PID 2>/dev/null; do
    echo "Heartbeat: $(date) - vLLM running on $(hostname):{port}"
    sleep 30
done

echo "=== vLLM Server Stopped ==="
rm -f /tmp/llm_sessions/$SLURM_JOB_ID
"""
    
    @staticmethod
    def generate_ollama_script(model_name: str, 
                             port: int = 11434,
                             **kwargs) -> str:
        """Generate Ollama deployment script for HPC."""
        
        return f"""#!/bin/bash
#SBATCH --job-name=ollama_persistent
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --gres=gpu:1
#SBATCH --time=08:00:00
#SBATCH --output=ollama_%j.out
#SBATCH --error=ollama_%j.err

echo "=== Ollama Persistent Server Starting ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Model: {model_name}"
echo "Port: {port}"
echo "Start time: $(date)"

# Load modules
module load python/3.9

# Set environment
export OLLAMA_HOST=0.0.0.0:{port}
export OLLAMA_ORIGINS="*"

# Create session directory
mkdir -p /tmp/llm_sessions
echo "ollama_running" > /tmp/llm_sessions/$SLURM_JOB_ID

# Start Ollama daemon
echo "Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!

# Wait for service to start
echo "Waiting for Ollama to initialize..."
sleep 10

# Pull model if needed
echo "Ensuring model {model_name} is available..."
ollama pull {model_name}

echo "✅ Ollama is ready!"

# Keep session alive
echo "Ollama server is running. Keeping session alive..."
while kill -0 $OLLAMA_PID 2>/dev/null; do
    echo "Heartbeat: $(date) - Ollama running on $(hostname):{port}"
    sleep 30
done

echo "=== Ollama Server Stopped ==="
rm -f /tmp/llm_sessions/$SLURM_JOB_ID
"""
    
    @staticmethod
    def generate_ssh_config(hpc_host: str, 
                          ssh_user: str,
                          ssh_key_path: str = "~/.ssh/id_rsa") -> str:
        """Generate SSH config template."""
        
        return f"""# HPC SSH Configuration
Host hpc-llm
    HostName {hpc_host}
    User {ssh_user}
    IdentityFile {ssh_key_path}
    ServerAliveInterval 30
    ServerAliveCountMax 3
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    LogLevel ERROR
    
    # Tunnel configurations for LLM services
    # LocalForward 8000 localhost:8000  # vLLM
    # LocalForward 11434 localhost:11434  # Ollama
"""
    
    @staticmethod
    def generate_deployment_config(hpc_host: str,
                                 ssh_user: str,
                                 model_configs: Dict[str, Any]) -> str:
        """Generate deployment configuration YAML."""
        
        config = {
            "hpc": {
                "host": hpc_host,
                "user": ssh_user,
                "key_path": "~/.ssh/id_rsa",
                "partition": "gpu",
                "session_hours": 8
            },
            "models": model_configs,
            "ports": {
                "vllm_base": 8000,
                "ollama_base": 11434,
                "local_base": 8000
            },
            "deployment": {
                "auto_start": True,
                "health_check_interval": 30,
                "max_retries": 3
            }
        }
        
        import yaml
        return yaml.dump(config, default_flow_style=False, indent=2)


def create_deployment_files(output_dir: str,
                          hpc_host: str,
                          ssh_user: str,
                          vllm_model_path: str = "/hpc/models/llama-7b",
                          ollama_model_name: str = "llama3.2:3b"):
    """
    Create all deployment files in specified directory.
    
    Args:
        output_dir: Directory to create files in
        hpc_host: HPC cluster hostname
        ssh_user: SSH username
        vllm_model_path: Path to vLLM model
        ollama_model_name: Ollama model name
    """
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    template = HpcDeploymentTemplate()
    
    # 1. vLLM script
    vllm_script = template.generate_vllm_script(vllm_model_path)
    with open(output_path / "deploy_vllm.sh", "w") as f:
        f.write(vllm_script)
    
    # 2. Ollama script  
    ollama_script = template.generate_ollama_script(ollama_model_name)
    with open(output_path / "deploy_ollama.sh", "w") as f:
        f.write(ollama_script)
    
    # 3. SSH config
    ssh_config = template.generate_ssh_config(hpc_host, ssh_user)
    with open(output_path / "ssh_config", "w") as f:
        f.write(ssh_config)
    
    # 4. Deployment config
    model_configs = {
        "vllm": {
            "model_path": vllm_model_path,
            "port": 8000,
            "gpu_memory_util": 0.9
        },
        "ollama": {
            "model_name": ollama_model_name,
            "port": 11434
        }
    }
    
    deploy_config = template.generate_deployment_config(
        hpc_host, ssh_user, model_configs
    )
    with open(output_path / "deployment_config.yaml", "w") as f:
        f.write(deploy_config)
    
    # 5. Quick start script
    quickstart = f"""#!/bin/bash
# Quick start script for HPC LLM deployment

echo "🚀 HPC LLM Deployment Quick Start"
echo "================================="

# Check SSH connection
echo "📡 Testing SSH connection to {hpc_host}..."
if ssh -o ConnectTimeout=10 {ssh_user}@{hpc_host} "echo 'SSH OK'"; then
    echo "✅ SSH connection successful"
else
    echo "❌ SSH connection failed. Please check your credentials."
    exit 1
fi

# Deploy scripts to HPC
echo "📤 Uploading deployment scripts..."
scp deploy_vllm.sh deploy_ollama.sh {ssh_user}@{hpc_host}:~/

echo "🎯 Deployment files ready!"
echo ""
echo "Next steps:"
echo "1. Submit vLLM job: ssh {ssh_user}@{hpc_host} 'sbatch deploy_vllm.sh'"
echo "2. Submit Ollama job: ssh {ssh_user}@{hpc_host} 'sbatch deploy_ollama.sh'"
echo "3. Check job status: ssh {ssh_user}@{hpc_host} 'squeue -u {ssh_user}'"
echo "4. Setup SSH tunnels when jobs are running"
echo ""
echo "📚 Check deployment_config.yaml for detailed configuration"
"""
    
    with open(output_path / "quickstart.sh", "w") as f:
        f.write(quickstart)
    
    # Make scripts executable
    os.chmod(output_path / "quickstart.sh", 0o755)
    
    print(f"✅ Deployment files created in: {output_path}")
    print("📁 Files created:")
    print("  - deploy_vllm.sh")
    print("  - deploy_ollama.sh") 
    print("  - ssh_config")
    print("  - deployment_config.yaml")
    print("  - quickstart.sh")
    print("")
    print("🚀 Run './quickstart.sh' to get started!")


if __name__ == "__main__":
    # Example usage
    create_deployment_files(
        output_dir="./hpc_deployment",
        hpc_host="hpc.university.edu", 
        ssh_user="username",
        vllm_model_path="/shared/models/llama-7b-chat",
        ollama_model_name="llama3.2:3b"
    )