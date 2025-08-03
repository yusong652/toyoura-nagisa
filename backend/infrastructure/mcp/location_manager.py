"""
位置信息管理器
简化的位置数据结构，移除缓存机制。
"""

import time
from typing import Optional

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
