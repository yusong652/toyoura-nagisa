"""
Persistent HPC Manager for Long-Running LLM Services

Manages long-running LLM inference servers on HPC platforms with
immediate response capabilities and persistent SSH connections.
"""

import asyncio
import json
import logging
import subprocess
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import yaml

from .ssh_tunnel_manager import SshTunnelManager, TunnelConfig, HpcNode

logger = logging.getLogger(__name__)

class ServerStatus(Enum):
    """Server status enumeration."""
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"
    FAILED = "failed"

@dataclass
class PersistentServer:
    """Persistent server configuration."""
    server_id: str
    server_type: str  # "vllm" or "ollama"
    hpc_node: HpcNode
    model_path: str
    port: int
    ssh_tunnel_name: Optional[str] = None
    status: ServerStatus = ServerStatus.INITIALIZING
    start_time: Optional[float] = None
    last_health_check: Optional[float] = None
    job_id: Optional[str] = None
    session_duration_hours: int = 8

@dataclass
class HpcSession:
    """HPC resource allocation session."""
    session_id: str
    job_id: str
    nodes: List[HpcNode]
    start_time: float
    duration_hours: int
    is_active: bool = True

class PersistentHpcManager:
    """
    Manages persistent LLM inference servers on HPC platforms.
    
    Features:
    - Long-running server deployment (hours)
    - Immediate response without queuing
    - Automatic SSH tunnel management
    - Health monitoring and recovery
    - Multi-node load balancing
    """
    
    def __init__(self,
                 ssh_manager: SshTunnelManager,
                 tssrun_command: str = "tssrun",
                 default_session_hours: int = 8):
        self.ssh_manager = ssh_manager
        self.tssrun_command = tssrun_command
        self.default_session_hours = default_session_hours
        
        # Server tracking
        self.servers: Dict[str, PersistentServer] = {}
        self.hpc_sessions: Dict[str, HpcSession] = {}
        
        # Monitoring
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        
    async def allocate_hpc_session(self,
                                 gpu_count: int = 1,
                                 duration_hours: int = None,
                                 partition: str = "gpu",
                                 node_features: List[str] = None) -> Optional[str]:
        """
        Allocate HPC resources for long-running session.
        
        Args:
            gpu_count: Number of GPUs needed
            duration_hours: Session duration in hours
            partition: HPC partition name
            node_features: Required node features
            
        Returns:
            Session ID if successful, None otherwise
        """
        duration = duration_hours or self.default_session_hours
        session_id = f"hpc_session_{int(time.time())}"
        
        try:
            # Create allocation script
            script_content = self._generate_allocation_script(
                gpu_count, duration, partition, node_features or []
            )
            
            script_path = f"/tmp/hpc_session_{session_id}.sh"
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            # Submit allocation job
            cmd = [
                self.tssrun_command,
                "--partition", partition,
                "--nodes", str(gpu_count),  # One GPU per node for now
                "--ntasks-per-node", "1",
                "--cpus-per-task", "8",
                "--mem", "32G",
                "--time", f"{duration}:00:00",
                "--gres", f"gpu:1",
                "--job-name", f"llm_session_{session_id}"
            ]
            
            if node_features:
                cmd.extend(["--constraint", ",".join(node_features)])
            
            cmd.append(script_path)
            
            logger.info(f"Allocating HPC session: {session_id}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Extract job ID
                output_lines = result.stdout.strip().split('\n')
                job_id = None
                for line in output_lines:
                    if "Submitted batch job" in line:
                        job_id = line.split()[-1]
                        break
                
                if job_id:
                    # Wait for job to start and get node allocation
                    nodes = await self._wait_for_job_start(job_id, timeout=300)
                    
                    if nodes:
                        session = HpcSession(
                            session_id=session_id,
                            job_id=job_id,
                            nodes=nodes,
                            start_time=time.time(),
                            duration_hours=duration
                        )
                        
                        self.hpc_sessions[session_id] = session
                        logger.info(f"HPC session {session_id} allocated with {len(nodes)} nodes")
                        return session_id
            
            logger.error(f"Failed to allocate HPC session: {result.stderr}")
            return None
            
        except Exception as e:
            logger.error(f"Error allocating HPC session: {e}")
            return None
    
    def _generate_allocation_script(self,
                                  gpu_count: int,
                                  duration_hours: int,
                                  partition: str,
                                  node_features: List[str]) -> str:
        """Generate HPC allocation script that keeps nodes alive."""
        
        script = f"""#!/bin/bash
#SBATCH --job-name=llm_persistent_session
#SBATCH --output=session_%j.out
#SBATCH --error=session_%j.err

# Load necessary modules
module load cuda/11.8
module load python/3.9

echo "=== HPC LLM Session Started ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "GPUs: $CUDA_VISIBLE_DEVICES"
echo "Start time: $(date)"
echo "Duration: {duration_hours} hours"

# Create session marker file
mkdir -p /tmp/llm_sessions
echo "active" > /tmp/llm_sessions/$SLURM_JOB_ID

# Setup environment
export CUDA_VISIBLE_DEVICES=$SLURM_LOCALID

# Keep session alive by running a monitoring loop
# This script will run for the allocated time, keeping the node reserved
end_time=$(($(date +%s) + {duration_hours * 3600}))

while [ $(date +%s) -lt $end_time ]; do
    echo "Session heartbeat: $(date) - $(hostname)"
    
    # Check if any services are supposed to run
    if [ -f "/tmp/llm_sessions/$SLURM_JOB_ID.service" ]; then
        echo "Service request detected, starting service..."
        source /tmp/llm_sessions/$SLURM_JOB_ID.service
    fi
    
    sleep 30
done

echo "=== HPC LLM Session Ended ==="
echo "End time: $(date)"

# Cleanup
rm -f /tmp/llm_sessions/$SLURM_JOB_ID*
"""
        return script
    
    async def _wait_for_job_start(self, job_id: str, timeout: int = 300) -> List[HpcNode]:
        """Wait for job to start and get allocated nodes."""
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                # Check job status
                status_cmd = [self.tssrun_command, "squeue", "-j", job_id, "-h", "-o", "%T,%N"]
                result = subprocess.run(status_cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0 and result.stdout.strip():
                    status_line = result.stdout.strip()
                    status, node_list_str = status_line.split(',', 1)
                    
                    if status.upper() == "RUNNING":
                        # Parse node list and create HpcNode objects
                        node_names = self._parse_node_list(node_list_str)
                        nodes = [
                            HpcNode(
                                node_id=f"hpc_{name}",
                                hostname=name,
                                gpu_count=1,
                                memory_gb=32,
                                is_available=True
                            )
                            for name in node_names
                        ]
                        return nodes
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error checking job status: {e}")
                await asyncio.sleep(5)
        
        logger.error(f"Job {job_id} did not start within {timeout} seconds")
        return []
    
    def _parse_node_list(self, node_list_str: str) -> List[str]:
        """Parse SLURM node list format."""
        if '[' in node_list_str and ']' in node_list_str:
            base = node_list_str.split('[')[0]
            range_part = node_list_str.split('[')[1].split(']')[0]
            
            nodes = []
            for part in range_part.split(','):
                if '-' in part:
                    start, end = part.split('-')
                    for i in range(int(start), int(end) + 1):
                        nodes.append(f"{base}{i:02d}")
                else:
                    nodes.append(f"{base}{part}")
            return nodes
        else:
            return [node_list_str] if node_list_str else []
    
    async def deploy_persistent_vllm(self,
                                   session_id: str,
                                   model_path: str,
                                   port: int = 8000,
                                   local_port: int = 8000,
                                   ssh_user: str = "",
                                   ssh_key_path: Optional[str] = None,
                                   **vllm_args) -> Optional[str]:
        """
        Deploy persistent vLLM server on allocated HPC node.
        
        Args:
            session_id: HPC session ID
            model_path: Path to model on HPC filesystem
            port: Remote port for vLLM service
            local_port: Local port for SSH tunnel
            ssh_user: SSH username
            ssh_key_path: SSH private key path
            **vllm_args: Additional vLLM arguments
            
        Returns:
            Server ID if successful, None otherwise
        """
        if session_id not in self.hpc_sessions:
            logger.error(f"HPC session {session_id} not found")
            return None
        
        session = self.hpc_sessions[session_id]
        if not session.nodes:
            logger.error(f"No nodes available in session {session_id}")
            return None
        
        # Use first available node
        node = session.nodes[0]
        server_id = f"vllm_{session_id}_{int(time.time())}"
        
        try:
            # Create vLLM startup script
            vllm_script = self._generate_vllm_startup_script(
                model_path, port, **vllm_args
            )
            
            # Deploy script to HPC node
            script_path = f"/tmp/llm_sessions/{session.job_id}.service"
            
            # Use SSH to deploy and start vLLM
            ssh_cmd = [
                "ssh",
                f"{ssh_user}@{node.hostname}" if ssh_user else node.hostname,
                f"echo '{vllm_script}' > {script_path}"
            ]
            
            if ssh_key_path:
                ssh_cmd.insert(1, f"-i {ssh_key_path}")
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.error(f"Failed to deploy vLLM script: {result.stderr}")
                return None
            
            # Create SSH tunnel
            tunnel_name = await self.ssh_manager.create_hpc_tunnel(
                node, local_port, port, ssh_user, ssh_key_path
            )
            
            if not tunnel_name:
                logger.error("Failed to create SSH tunnel for vLLM server")
                return None
            
            # Create server record
            server = PersistentServer(
                server_id=server_id,
                server_type="vllm",
                hpc_node=node,
                model_path=model_path,
                port=port,
                ssh_tunnel_name=tunnel_name,
                status=ServerStatus.STARTING,
                start_time=time.time(),
                job_id=session.job_id
            )
            
            self.servers[server_id] = server
            
            # Wait for server to become healthy
            if await self._wait_for_server_ready(server_id, timeout=120):
                logger.info(f"vLLM server {server_id} deployed successfully")
                return server_id
            else:
                logger.error(f"vLLM server {server_id} failed to start")
                await self.stop_server(server_id)
                return None
                
        except Exception as e:
            logger.error(f"Error deploying vLLM server: {e}")
            return None
    
    def _generate_vllm_startup_script(self, model_path: str, port: int, **vllm_args) -> str:
        """Generate vLLM startup script."""
        
        args = [
            f"--model {model_path}",
            f"--host 0.0.0.0",
            f"--port {port}",
            "--gpu-memory-utilization 0.9"
        ]
        
        for key, value in vllm_args.items():
            args.append(f"--{key.replace('_', '-')} {value}")
        
        script = f"""#!/bin/bash
# vLLM persistent server startup script

echo "Starting vLLM server on port {port}"
echo "Model: {model_path}"
echo "Node: $(hostname)"

# Activate environment
export CUDA_VISIBLE_DEVICES=0

# Start vLLM server in background
nohup python -m vllm.entrypoints.openai.api_server \\
    {' '.join(args)} \\
    > /tmp/vllm_{port}.log 2>&1 &

echo "vLLM server started with PID $!"
"""
        return script
    
    async def _wait_for_server_ready(self, server_id: str, timeout: int = 120) -> bool:
        """Wait for server to become ready."""
        if server_id not in self.servers:
            return False
        
        server = self.servers[server_id]
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            if await self._check_server_health(server_id):
                server.status = ServerStatus.RUNNING
                return True
            await asyncio.sleep(5)
        
        server.status = ServerStatus.FAILED
        return False
    
    async def _check_server_health(self, server_id: str) -> bool:
        """Check if server is healthy."""
        if server_id not in self.servers:
            return False
        
        server = self.servers[server_id]
        
        # Check SSH tunnel health
        if server.ssh_tunnel_name:
            if not await self.ssh_manager.check_tunnel_health(server.ssh_tunnel_name):
                return False
        
        # Check service health via HTTP
        try:
            import aiohttp
            
            base_url = f"http://localhost:{server.port}"
            if server.server_type == "vllm":
                health_url = f"{base_url}/health"
            else:  # ollama
                health_url = f"{base_url}/api/tags"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    return response.status == 200
                    
        except Exception:
            return False
    
    async def start_monitoring(self):
        """Start monitoring all servers."""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitor_servers())
        logger.info("Persistent server monitoring started")
    
    async def stop_monitoring(self):
        """Stop server monitoring."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Persistent server monitoring stopped")
    
    async def _monitor_servers(self):
        """Monitor server health and perform recovery."""
        while self._is_monitoring:
            try:
                for server_id in list(self.servers.keys()):
                    server = self.servers[server_id]
                    
                    if server.status == ServerStatus.RUNNING:
                        is_healthy = await self._check_server_health(server_id)
                        
                        if is_healthy:
                            server.last_health_check = time.time()
                        else:
                            logger.warning(f"Server {server_id} is unhealthy")
                            server.status = ServerStatus.UNHEALTHY
                            
                            # Attempt recovery
                            if await self._recover_server(server_id):
                                logger.info(f"Server {server_id} recovered successfully")
                            else:
                                logger.error(f"Failed to recover server {server_id}")
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in server monitoring: {e}")
                await asyncio.sleep(30)
    
    async def _recover_server(self, server_id: str) -> bool:
        """Attempt to recover a failed server."""
        if server_id not in self.servers:
            return False
        
        server = self.servers[server_id]
        
        try:
            # Try to recover SSH tunnel first
            if server.ssh_tunnel_name:
                await self.ssh_manager.recover_tunnel(server.ssh_tunnel_name)
            
            # Wait and check health again
            await asyncio.sleep(10)
            if await self._check_server_health(server_id):
                server.status = ServerStatus.RUNNING
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error recovering server {server_id}: {e}")
            return False
    
    async def stop_server(self, server_id: str) -> bool:
        """Stop a persistent server."""
        if server_id not in self.servers:
            return False
        
        server = self.servers[server_id]
        
        try:
            # Remove SSH tunnel
            if server.ssh_tunnel_name:
                await self.ssh_manager.remove_tunnel(server.ssh_tunnel_name)
            
            # Mark as stopped
            server.status = ServerStatus.STOPPED
            
            logger.info(f"Server {server_id} stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping server {server_id}: {e}")
            return False
    
    def get_available_servers(self) -> List[str]:
        """Get list of available servers."""
        return [
            server_id for server_id, server in self.servers.items()
            if server.status == ServerStatus.RUNNING
        ]
    
    def get_server_info(self, server_id: str) -> Optional[Dict]:
        """Get detailed server information."""
        if server_id not in self.servers:
            return None
        
        server = self.servers[server_id]
        info = asdict(server)
        
        # Add computed fields
        if server.start_time:
            info['uptime'] = time.time() - server.start_time
        
        return info
    
    async def cleanup(self):
        """Clean up all resources."""
        await self.stop_monitoring()
        
        # Stop all servers
        for server_id in list(self.servers.keys()):
            await self.stop_server(server_id)
        
        # Cancel HPC sessions
        for session in self.hpc_sessions.values():
            if session.is_active:
                try:
                    subprocess.run([self.tssrun_command, "scancel", session.job_id], timeout=10)
                except Exception as e:
                    logger.error(f"Error cancelling session {session.job_id}: {e}")
        
        logger.info("Persistent HPC manager cleaned up")