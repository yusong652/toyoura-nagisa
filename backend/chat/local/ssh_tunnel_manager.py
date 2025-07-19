"""
SSH Tunnel Manager for Remote HPC Deployment

Manages SSH tunnels to HPC platforms for distributed LLM inference,
providing secure connection management and automatic tunnel recovery.
"""

import asyncio
import logging
import subprocess
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TunnelConfig:
    """SSH tunnel configuration."""
    name: str
    ssh_host: str
    ssh_port: int = 22
    ssh_user: str = ""
    ssh_key_path: Optional[str] = None
    local_port: int = 8000
    remote_host: str = "localhost"
    remote_port: int = 8000
    keep_alive_interval: int = 30
    max_retries: int = 3

@dataclass 
class HpcNode:
    """HPC node configuration."""
    node_id: str
    hostname: str
    gpu_count: int
    memory_gb: int
    is_available: bool = True
    current_load: float = 0.0

class SshTunnelManager:
    """
    Manages SSH tunnels for distributed LLM inference on HPC platforms.
    
    Features:
    - Multiple tunnel management
    - Automatic reconnection
    - Health monitoring
    - Load balancing across nodes
    """
    
    def __init__(self):
        self.tunnels: Dict[str, subprocess.Popen] = {}
        self.tunnel_configs: Dict[str, TunnelConfig] = {}
        self.hpc_nodes: Dict[str, HpcNode] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        
    async def add_tunnel(self, config: TunnelConfig) -> bool:
        """
        Add and establish a new SSH tunnel.
        
        Args:
            config: Tunnel configuration
            
        Returns:
            True if tunnel was established successfully
        """
        try:
            self.tunnel_configs[config.name] = config
            
            # Build SSH command
            ssh_cmd = self._build_ssh_command(config)
            
            logger.info(f"Establishing SSH tunnel: {config.name}")
            logger.debug(f"SSH command: {' '.join(ssh_cmd)}")
            
            # Start tunnel process
            process = subprocess.Popen(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=None
            )
            
            # Wait a moment for tunnel to establish
            await asyncio.sleep(2)
            
            # Check if process is still running
            if process.poll() is None:
                self.tunnels[config.name] = process
                logger.info(f"SSH tunnel {config.name} established successfully")
                return True
            else:
                stdout, stderr = process.communicate()
                logger.error(f"SSH tunnel {config.name} failed: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to establish SSH tunnel {config.name}: {e}")
            return False
    
    def _build_ssh_command(self, config: TunnelConfig) -> List[str]:
        """Build SSH command for tunnel creation."""
        cmd = [
            "ssh",
            "-N",  # No remote command
            "-L", f"{config.local_port}:{config.remote_host}:{config.remote_port}",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR"
        ]
        
        if config.ssh_key_path:
            cmd.extend(["-i", config.ssh_key_path])
            
        if config.ssh_port != 22:
            cmd.extend(["-p", str(config.ssh_port)])
            
        # Add user@host
        if config.ssh_user:
            cmd.append(f"{config.ssh_user}@{config.ssh_host}")
        else:
            cmd.append(config.ssh_host)
            
        return cmd
    
    async def remove_tunnel(self, tunnel_name: str) -> bool:
        """
        Remove and close an SSH tunnel.
        
        Args:
            tunnel_name: Name of tunnel to remove
            
        Returns:
            True if tunnel was removed successfully
        """
        try:
            if tunnel_name in self.tunnels:
                process = self.tunnels[tunnel_name]
                process.terminate()
                
                # Wait for graceful termination
                await asyncio.sleep(2)
                if process.poll() is None:
                    process.kill()
                    
                del self.tunnels[tunnel_name]
                logger.info(f"SSH tunnel {tunnel_name} removed")
                
            if tunnel_name in self.tunnel_configs:
                del self.tunnel_configs[tunnel_name]
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove SSH tunnel {tunnel_name}: {e}")
            return False
    
    async def check_tunnel_health(self, tunnel_name: str) -> bool:
        """
        Check if a specific tunnel is healthy.
        
        Args:
            tunnel_name: Name of tunnel to check
            
        Returns:
            True if tunnel is healthy
        """
        if tunnel_name not in self.tunnels:
            return False
            
        process = self.tunnels[tunnel_name]
        return process.poll() is None
    
    async def recover_tunnel(self, tunnel_name: str) -> bool:
        """
        Attempt to recover a failed tunnel.
        
        Args:
            tunnel_name: Name of tunnel to recover
            
        Returns:
            True if recovery was successful
        """
        if tunnel_name not in self.tunnel_configs:
            return False
            
        logger.info(f"Attempting to recover tunnel: {tunnel_name}")
        
        # Remove existing tunnel
        await self.remove_tunnel(tunnel_name)
        
        # Re-establish tunnel
        config = self.tunnel_configs[tunnel_name]
        return await self.add_tunnel(config)
    
    async def start_monitoring(self):
        """Start monitoring all tunnels for health and automatic recovery."""
        if self._is_monitoring:
            return
            
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitor_tunnels())
        logger.info("SSH tunnel monitoring started")
    
    async def stop_monitoring(self):
        """Stop tunnel monitoring."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("SSH tunnel monitoring stopped")
    
    async def _monitor_tunnels(self):
        """Monitor tunnel health and perform automatic recovery."""
        while self._is_monitoring:
            try:
                for tunnel_name in list(self.tunnels.keys()):
                    if not await self.check_tunnel_health(tunnel_name):
                        logger.warning(f"Tunnel {tunnel_name} is unhealthy, attempting recovery")
                        await self.recover_tunnel(tunnel_name)
                        
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in tunnel monitoring: {e}")
                await asyncio.sleep(30)
    
    async def get_available_tunnels(self) -> List[str]:
        """
        Get list of healthy tunnels.
        
        Returns:
            List of healthy tunnel names
        """
        healthy_tunnels = []
        for tunnel_name in self.tunnels.keys():
            if await self.check_tunnel_health(tunnel_name):
                healthy_tunnels.append(tunnel_name)
        return healthy_tunnels
    
    async def add_hpc_node(self, node: HpcNode):
        """Add HPC node for resource management."""
        self.hpc_nodes[node.node_id] = node
        logger.info(f"Added HPC node: {node.node_id}")
    
    async def get_best_node(self) -> Optional[HpcNode]:
        """
        Get the best available HPC node based on load and availability.
        
        Returns:
            Best available node or None if no nodes available
        """
        available_nodes = [
            node for node in self.hpc_nodes.values() 
            if node.is_available
        ]
        
        if not available_nodes:
            return None
            
        # Sort by current load (ascending)
        return min(available_nodes, key=lambda x: x.current_load)
    
    async def create_hpc_tunnel(self, 
                              node: HpcNode, 
                              local_port: int,
                              remote_port: int = 8000,
                              ssh_user: str = "",
                              ssh_key_path: Optional[str] = None) -> Optional[str]:
        """
        Create tunnel to specific HPC node.
        
        Args:
            node: Target HPC node
            local_port: Local port for tunnel
            remote_port: Remote port on HPC node
            ssh_user: SSH username
            ssh_key_path: Path to SSH private key
            
        Returns:
            Tunnel name if successful, None otherwise
        """
        tunnel_name = f"hpc_{node.node_id}_{local_port}"
        
        config = TunnelConfig(
            name=tunnel_name,
            ssh_host=node.hostname,
            ssh_user=ssh_user,
            ssh_key_path=ssh_key_path,
            local_port=local_port,
            remote_port=remote_port
        )
        
        if await self.add_tunnel(config):
            return tunnel_name
        return None
    
    def get_tunnel_status(self) -> Dict[str, Dict]:
        """
        Get status of all tunnels.
        
        Returns:
            Dictionary with tunnel status information
        """
        status = {}
        for name, config in self.tunnel_configs.items():
            is_healthy = name in self.tunnels and self.tunnels[name].poll() is None
            status[name] = {
                "config": config,
                "is_healthy": is_healthy,
                "local_port": config.local_port,
                "remote_endpoint": f"{config.remote_host}:{config.remote_port}"
            }
        return status
    
    async def cleanup(self):
        """Clean up all tunnels and stop monitoring."""
        await self.stop_monitoring()
        
        for tunnel_name in list(self.tunnels.keys()):
            await self.remove_tunnel(tunnel_name)
            
        logger.info("SSH tunnel manager cleaned up")