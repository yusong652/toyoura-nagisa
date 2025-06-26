"""
位置信息管理器
一个简单的内存缓存，用于存储和管理会话的地理位置信息。
"""

import time
import requests
from typing import Optional, Dict, Any
from threading import RLock

class LocationData:
    """
    用于封装地理位置数据的结构体
    """
    def __init__(self, latitude: float, longitude: float, source: str, accuracy: Optional[float] = None, timestamp: Optional[int] = None, city: Optional[str] = None, country: Optional[str] = None, region: Optional[str] = None, session_id: Optional[str] = None):
        self.latitude = latitude
        self.longitude = longitude
        self.accuracy = accuracy
        self.timestamp = timestamp or int(time.time())
        self.source = source
        self.session_id = session_id
        self.city = city
        self.country = country
        self.region = region

    def to_dict(self):
        """
        将位置数据转换为字典
        """
        return {k: v for k, v in self.__dict__.items() if v is not None}

class LocationManager:
    """
    管理地理位置信息的单例类。
    这个类只负责在内存中存储和检索位置数据。
    """
    _instance = None
    _lock = RLock()

    def __init__(self):
        self.session_locations: Dict[str, LocationData] = {}
        self.global_location: Optional[LocationData] = None

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def update_location(self, session_id: str, data: Dict[str, Any]):
        """
        从前端更新指定 session 的位置信息。
        """
        with self._lock:
            location = LocationData(
                latitude=data['latitude'],
                longitude=data['longitude'],
                accuracy=data.get('accuracy'),
                source="browser_geolocation",
                session_id=session_id
            )
            self.session_locations[session_id] = location
            self.global_location = location  # 同时更新全局位置作为备选
            print(f"[LocationManager] Updated location for session {session_id}")

    def get_session_location(self, session_id: str) -> Optional[LocationData]:
        """
        获取指定 session 的位置信息。
        """
        with self._lock:
            return self.session_locations.get(session_id)

    def get_global_location(self) -> Optional[LocationData]:
        """
        获取最近一次上报的全局位置。
        """
        with self._lock:
            return self.global_location

# 全局单例
_location_manager_instance = LocationManager.get_instance()

def get_location_manager() -> LocationManager:
    """
    获取 LocationManager 的全局唯一实例。
    """
    return _location_manager_instance
