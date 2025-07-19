"""
Simple SSH Manager - No External Dependencies

Lightweight SSH tunnel management using system SSH commands only.
Designed for simplicity and reliability.
"""

import asyncio
import logging
import subprocess
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SimpleTunnel:
    """Simple tunnel configuration."""
    name: str
    ssh_host: str
    ssh_user: str
    local_port: int
    remote_port: int = 8000
    ssh_key_path: Optional[str] = None
    process: Optional[subprocess.Popen] = None

class SimpleSshManager:
    """
    Simplified SSH tunnel manager using system SSH commands.
    
    No external dependencies - uses subprocess and system SSH.
    """
    
    def __init__(self):
        self.tunnels: Dict[str, SimpleTunnel] = {}
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def create_tunnel(self,
                          name: str,
                          ssh_host: str,
                          ssh_user: str,
                          local_port: int,
                          remote_port: int = 8000,
                          ssh_key_path: Optional[str] = None) -> bool:
        """
        Create SSH tunnel using system SSH command.
        
        Args:
            name: Tunnel identifier
            ssh_host: Remote host
            ssh_user: SSH username
            local_port: Local port for tunnel
            remote_port: Remote port on HPC node
            ssh_key_path: Path to SSH private key
            
        Returns:
            True if tunnel created successfully
        """
        try:
            # Build SSH command
            cmd = [
                "ssh",
                "-N",  # No remote command
                "-L", f"{local_port}:localhost:{remote_port}",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "LogLevel=ERROR"
            ]
            
            if ssh_key_path:
                cmd.extend(["-i", ssh_key_path])
            
            cmd.append(f"{ssh_user}@{ssh_host}")
            
            logger.info(f"Creating SSH tunnel: {name}")
            logger.debug(f"SSH command: {' '.join(cmd)}")
            
            # Start tunnel process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=None
            )
            
            # Wait a moment for tunnel to establish
            await asyncio.sleep(3)
            
            # Check if process is still running
            if process.poll() is None:
                tunnel = SimpleTunnel(
                    name=name,
                    ssh_host=ssh_host,
                    ssh_user=ssh_user,
                    local_port=local_port,
                    remote_port=remote_port,
                    ssh_key_path=ssh_key_path,
                    process=process
                )
                
                self.tunnels[name] = tunnel
                logger.info(f"✅ SSH tunnel {name} created: localhost:{local_port} -> {ssh_host}:{remote_port}")
                return True
            else:
                stdout, stderr = process.communicate()
                logger.error(f"❌ SSH tunnel {name} failed: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating SSH tunnel {name}: {e}")
            return False
    
    async def remove_tunnel(self, name: str) -> bool:
        """Remove SSH tunnel."""
        if name not in self.tunnels:
            return False
        
        tunnel = self.tunnels[name]
        
        try:
            if tunnel.process and tunnel.process.poll() is None:
                tunnel.process.terminate()
                
                # Wait for graceful termination
                await asyncio.sleep(2)
                if tunnel.process.poll() is None:
                    tunnel.process.kill()
            
            del self.tunnels[name]
            logger.info(f"🗑️  SSH tunnel {name} removed")
            return True
            
        except Exception as e:
            logger.error(f"Error removing tunnel {name}: {e}")
            return False
    
    async def check_tunnel_health(self, name: str) -> bool:
        """Check if tunnel is healthy."""
        if name not in self.tunnels:
            return False
        
        tunnel = self.tunnels[name]
        return tunnel.process and tunnel.process.poll() is None
    
    async def test_connection(self, ssh_host: str, ssh_user: str, ssh_key_path: Optional[str] = None) -> bool:
        """Test SSH connection without creating tunnel."""
        try:
            cmd = ["ssh", "-o", "ConnectTimeout=10"]
            
            if ssh_key_path:
                cmd.extend(["-i", ssh_key_path])
            
            cmd.extend([f"{ssh_user}@{ssh_host}", "echo 'SSH_TEST_OK'"])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            return result.returncode == 0 and "SSH_TEST_OK" in result.stdout
            
        except Exception as e:
            logger.error(f"SSH connection test failed: {e}")
            return False
    
    async def start_monitoring(self):
        """Start monitoring tunnels."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_tunnels())
        logger.info("🔍 SSH tunnel monitoring started")
    
    async def stop_monitoring(self):
        """Stop monitoring."""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️  SSH tunnel monitoring stopped")
    
    async def _monitor_tunnels(self):
        """Monitor tunnel health."""
        while self._monitoring:
            try:
                for name in list(self.tunnels.keys()):
                    if not await self.check_tunnel_health(name):
                        logger.warning(f"⚠️  Tunnel {name} is unhealthy, attempting recovery")
                        await self._recover_tunnel(name)
                
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in tunnel monitoring: {e}")
                await asyncio.sleep(30)
    
    async def _recover_tunnel(self, name: str) -> bool:
        """Attempt to recover a failed tunnel."""
        if name not in self.tunnels:
            return False
        
        tunnel = self.tunnels[name]
        
        try:
            # Remove old tunnel
            await self.remove_tunnel(name)
            
            # Recreate tunnel
            return await self.create_tunnel(
                name=tunnel.name,
                ssh_host=tunnel.ssh_host,
                ssh_user=tunnel.ssh_user,
                local_port=tunnel.local_port,
                remote_port=tunnel.remote_port,
                ssh_key_path=tunnel.ssh_key_path
            )
            
        except Exception as e:
            logger.error(f"Error recovering tunnel {name}: {e}")
            return False
    
    def get_tunnel_status(self) -> Dict[str, Dict]:
        """Get status of all tunnels."""
        status = {}
        for name, tunnel in self.tunnels.items():
            is_healthy = tunnel.process and tunnel.process.poll() is None
            status[name] = {
                "ssh_host": tunnel.ssh_host,
                "ssh_user": tunnel.ssh_user,
                "local_port": tunnel.local_port,
                "remote_port": tunnel.remote_port,
                "is_healthy": is_healthy,
                "endpoint": f"localhost:{tunnel.local_port}"
            }
        return status
    
    async def cleanup(self):
        """Clean up all tunnels."""
        await self.stop_monitoring()
        
        for name in list(self.tunnels.keys()):
            await self.remove_tunnel(name)
        
        logger.info("🧹 SSH manager cleaned up")
    
    def list_tunnels(self) -> List[str]:
        """Get list of tunnel names."""
        return list(self.tunnels.keys())
    
    async def create_hpc_tunnel(self,
                              hpc_host: str,
                              ssh_user: str,
                              local_port: int,
                              remote_port: int = 8000,
                              ssh_key_path: Optional[str] = None) -> Optional[str]:
        """
        Convenience method to create HPC tunnel.
        
        Returns:
            Tunnel name if successful, None otherwise
        """
        tunnel_name = f"hpc_{local_port}"
        
        success = await self.create_tunnel(
            name=tunnel_name,
            ssh_host=hpc_host,
            ssh_user=ssh_user,
            local_port=local_port,
            remote_port=remote_port,
            ssh_key_path=ssh_key_path
        )
        
        return tunnel_name if success else None