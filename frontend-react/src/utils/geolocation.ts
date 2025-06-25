/**
 * 地理位置服务
 * 管理浏览器地理位置的获取和更新
 */

interface LocationData {
  latitude: number;
  longitude: number;
  accuracy?: number;
  timestamp?: number;
}

interface LocationResponse {
  success: boolean;
  message?: string;
  location?: LocationData;
}

class GeolocationService {
  private static instance: GeolocationService;
  private locationPermission: 'granted' | 'denied' | 'prompt' = 'prompt';
  private isInitialized = false;

  private constructor() {}

  static getInstance(): GeolocationService {
    if (!GeolocationService.instance) {
      GeolocationService.instance = new GeolocationService();
    }
    return GeolocationService.instance;
  }

  /**
   * 初始化地理位置服务
   */
  async initialize(): Promise<void> {
    if (this.isInitialized) return;

    // 检查浏览器是否支持地理位置
    if (!navigator.geolocation) {
      console.warn('Geolocation is not supported by this browser');
      return;
    }

    // 检查权限状态
    if ('permissions' in navigator) {
      try {
        const permission = await navigator.permissions.query({ name: 'geolocation' as PermissionName });
        this.locationPermission = permission.state;
        
        permission.onchange = () => {
          this.locationPermission = permission.state;
          console.log('Location permission changed:', permission.state);
        };
      } catch (error) {
        console.warn('Could not check location permission:', error);
      }
    }

    this.isInitialized = true;
    console.log('Geolocation service initialized');
  }

  /**
   * 请求地理位置权限并获取位置
   */
  async requestLocation(): Promise<LocationData | null> {
    if (!navigator.geolocation) {
      console.warn('Geolocation is not supported');
      return null;
    }

    return new Promise((resolve, reject) => {
      const options = {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 300000 // 5分钟缓存
      };

      navigator.geolocation.getCurrentPosition(
        (position) => {
          const locationData: LocationData = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            timestamp: position.timestamp
          };

          console.log('Location obtained:', locationData);
          this.locationPermission = 'granted';
          resolve(locationData);
        },
        (error) => {
          console.error('Error getting location:', error);
          this.locationPermission = 'denied';
          reject(error);
        },
        options
      );
    });
  }

  /**
   * 更新位置信息到后端
   */
  async updateLocationToBackend(locationData: LocationData): Promise<boolean> {
    try {
      const response = await fetch('/api/location/update', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(locationData),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result: LocationResponse = await response.json();
      return result.success;
    } catch (error) {
      console.error('Failed to update location to backend:', error);
      return false;
    }
  }

  /**
   * 获取并更新位置信息
   */
  async getAndUpdateLocation(): Promise<boolean> {
    try {
      const locationData = await this.requestLocation();
      if (locationData) {
        return await this.updateLocationToBackend(locationData);
      }
      return false;
    } catch (error) {
      console.error('Failed to get and update location:', error);
      return false;
    }
  }

  /**
   * 获取当前权限状态
   */
  getPermissionStatus(): 'granted' | 'denied' | 'prompt' {
    return this.locationPermission;
  }

  /**
   * 检查是否已初始化
   */
  isServiceInitialized(): boolean {
    return this.isInitialized;
  }
}

export default GeolocationService; 