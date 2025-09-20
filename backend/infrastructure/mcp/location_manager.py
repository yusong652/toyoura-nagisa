"""
位置信息管理器
简化的位置数据结构，移除缓存机制。
"""

import time
from typing import Optional

class LocationData:
    """
    Location data structure
    """
    def __init__(self, latitude: float, longitude: float, accuracy: Optional[float] = None, timestamp: Optional[int] = None, city: Optional[str] = None, country: Optional[str] = None, session_id: Optional[str] = None):
        self.latitude = latitude
        self.longitude = longitude
        self.accuracy = accuracy
        self.timestamp = timestamp or int(time.time())
        self.session_id = session_id
        self.city = city
        self.country = country

    def to_dict(self):
        """
        Convert to dictionary, excluding None values
        """
        return {k: v for k, v in self.__dict__.items() if v is not None}
