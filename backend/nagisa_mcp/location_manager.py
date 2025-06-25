"""
位置信息管理器
用于存储和管理不同session的地理位置信息
"""

import time
import threading
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

class LocationData:
    """位置数据类"""
    def __init__(
        self,
        latitude: float,
        longitude: float,
        accuracy: Optional[float] = None,
        timestamp: Optional[int] = None,
        source: str = "unknown",
        session_id: Optional[str] = None,
        city: Optional[str] = None,
        country: Optional[str] = None,
        region: Optional[str] = None,
        ip: Optional[str] = None
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.accuracy = accuracy
        self.timestamp = timestamp or int(time.time())
        self.source = source
        self.session_id = session_id
        self.city = city
        self.country = country
        self.region = region
        self.ip = ip
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy": self.accuracy,
            "timestamp": self.timestamp,
            "source": self.source,
            "session_id": self.session_id,
            "city": self.city,
            "country": self.country,
            "region": self.region,
            "ip": self.ip,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LocationData':
        """从字典创建LocationData实例"""
        location = cls(
            latitude=data["latitude"],
            longitude=data["longitude"],
            accuracy=data.get("accuracy"),
            timestamp=data.get("timestamp"),
            source=data.get("source", "unknown"),
            session_id=data.get("session_id"),
            city=data.get("city"),
            country=data.get("country"),
            region=data.get("region"),
            ip=data.get("ip")
        )
        if "created_at" in data:
            location.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            location.updated_at = datetime.fromisoformat(data["updated_at"])
        return location
    
    def update(self, **kwargs):
        """更新位置信息"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()
        self.timestamp = int(time.time())

class LocationManager:
    """位置信息管理器"""
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        初始化位置管理器
        
        Args:
            storage_path: 持久化存储路径，如果为None则不持久化
        """
        self._locations: Dict[str, LocationData] = {}  # session_id -> LocationData
        self._global_location: Optional[LocationData] = None  # 全局位置信息
        self._lock = threading.RLock()
        self._storage_path = storage_path
        
        # 如果指定了存储路径，尝试加载持久化数据
        if storage_path:
            self._load_persistent_data()
    
    def set_session_location(
        self,
        session_id: str,
        latitude: float,
        longitude: float,
        accuracy: Optional[float] = None,
        source: str = "browser_geolocation",
        **kwargs
    ) -> LocationData:
        """
        设置指定session的位置信息
        
        Args:
            session_id: 会话ID
            latitude: 纬度
            longitude: 经度
            accuracy: 精度
            source: 位置信息来源
            **kwargs: 其他位置信息
            
        Returns:
            LocationData: 位置数据对象
        """
        with self._lock:
            location_data = LocationData(
                latitude=latitude,
                longitude=longitude,
                accuracy=accuracy,
                source=source,
                session_id=session_id,
                **kwargs
            )
            
            self._locations[session_id] = location_data
            
            # 如果是第一个位置信息，也设置为全局位置
            if self._global_location is None:
                self._global_location = location_data
            
            # 持久化数据
            if self._storage_path:
                self._save_persistent_data()
            
            return location_data
    
    def get_session_location(self, session_id: str) -> Optional[LocationData]:
        """
        获取指定session的位置信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            LocationData: 位置数据对象，如果不存在则返回None
        """
        with self._lock:
            return self._locations.get(session_id)
    
    def get_global_location(self) -> Optional[LocationData]:
        """
        获取全局位置信息（通常是最近更新的位置）
        
        Returns:
            LocationData: 位置数据对象，如果不存在则返回None
        """
        with self._lock:
            return self._global_location
    
    def update_session_location(
        self,
        session_id: str,
        **kwargs
    ) -> Optional[LocationData]:
        """
        更新指定session的位置信息
        
        Args:
            session_id: 会话ID
            **kwargs: 要更新的位置信息
            
        Returns:
            LocationData: 更新后的位置数据对象，如果session不存在则返回None
        """
        with self._lock:
            location = self._locations.get(session_id)
            if location:
                location.update(**kwargs)
                
                # 如果这个session的位置是最新的，也更新全局位置
                if (self._global_location is None or 
                    location.timestamp > self._global_location.timestamp):
                    self._global_location = location
                
                # 持久化数据
                if self._storage_path:
                    self._save_persistent_data()
                
                return location
            return None
    
    def remove_session_location(self, session_id: str) -> bool:
        """
        移除指定session的位置信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 是否成功移除
        """
        with self._lock:
            if session_id in self._locations:
                del self._locations[session_id]
                
                # 如果移除的是全局位置，重新选择一个全局位置
                if (self._global_location and 
                    self._global_location.session_id == session_id):
                    self._update_global_location()
                
                # 持久化数据
                if self._storage_path:
                    self._save_persistent_data()
                
                return True
            return False
    
    def get_all_sessions(self) -> Dict[str, LocationData]:
        """
        获取所有session的位置信息
        
        Returns:
            Dict[str, LocationData]: 所有session的位置信息
        """
        with self._lock:
            return self._locations.copy()
    
    def get_recent_locations(self, hours: int = 24) -> Dict[str, LocationData]:
        """
        获取最近指定小时内的位置信息
        
        Args:
            hours: 小时数
            
        Returns:
            Dict[str, LocationData]: 最近的位置信息
        """
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_locations = {}
            
            for session_id, location in self._locations.items():
                if location.updated_at >= cutoff_time:
                    recent_locations[session_id] = location
            
            return recent_locations
    
    def clear_expired_locations(self, days: int = 7) -> int:
        """
        清理过期的位置信息
        
        Args:
            days: 过期天数
            
        Returns:
            int: 清理的位置信息数量
        """
        with self._lock:
            cutoff_time = datetime.now() - timedelta(days=days)
            expired_sessions = []
            
            for session_id, location in self._locations.items():
                if location.updated_at < cutoff_time:
                    expired_sessions.append(session_id)
            
            # 移除过期的位置信息
            for session_id in expired_sessions:
                del self._locations[session_id]
            
            # 如果全局位置被清理，重新选择一个
            if (self._global_location and 
                self._global_location.session_id in expired_sessions):
                self._update_global_location()
            
            # 持久化数据
            if self._storage_path:
                self._save_persistent_data()
            
            return len(expired_sessions)
    
    def _update_global_location(self):
        """更新全局位置信息为最新的位置"""
        if not self._locations:
            self._global_location = None
            return
        
        # 选择最新的位置作为全局位置
        latest_location = max(
            self._locations.values(),
            key=lambda loc: loc.timestamp
        )
        self._global_location = latest_location
    
    def _save_persistent_data(self):
        """保存数据到持久化存储"""
        if not self._storage_path:
            return
        
        try:
            # 确保目录存在
            storage_dir = Path(self._storage_path)
            storage_dir.mkdir(parents=True, exist_ok=True)
            
            # 准备数据
            data = {
                "global_location": self._global_location.to_dict() if self._global_location else None,
                "sessions": {
                    session_id: location.to_dict()
                    for session_id, location in self._locations.items()
                }
            }
            
            # 保存到文件
            file_path = storage_dir / "location_data.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"[WARNING] Failed to save location data: {e}")
    
    def _load_persistent_data(self):
        """从持久化存储加载数据"""
        if not self._storage_path:
            return
        
        try:
            file_path = Path(self._storage_path) / "location_data.json"
            if not file_path.exists():
                return
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 加载全局位置
            if data.get("global_location"):
                self._global_location = LocationData.from_dict(data["global_location"])
            
            # 加载session位置
            for session_id, location_data in data.get("sessions", {}).items():
                self._locations[session_id] = LocationData.from_dict(location_data)
                
        except Exception as e:
            print(f"[WARNING] Failed to load location data: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取位置管理器统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        with self._lock:
            return {
                "total_sessions": len(self._locations),
                "has_global_location": self._global_location is not None,
                "storage_enabled": self._storage_path is not None,
                "oldest_location": min(
                    (loc.updated_at for loc in self._locations.values()),
                    default=None
                ).isoformat() if self._locations else None,
                "newest_location": max(
                    (loc.updated_at for loc in self._locations.values()),
                    default=None
                ).isoformat() if self._locations else None
            }

# 全局位置管理器实例
_location_manager: Optional[LocationManager] = None

def get_location_manager(storage_path: Optional[str] = None) -> LocationManager:
    """
    获取全局位置管理器实例
    
    Args:
        storage_path: 持久化存储路径
        
    Returns:
        LocationManager: 位置管理器实例
    """
    global _location_manager
    if _location_manager is None:
        _location_manager = LocationManager(storage_path)
    return _location_manager

def set_global_location_manager(manager: LocationManager):
    """
    设置全局位置管理器实例（主要用于测试）
    
    Args:
        manager: 位置管理器实例
    """
    global _location_manager
    _location_manager = manager 