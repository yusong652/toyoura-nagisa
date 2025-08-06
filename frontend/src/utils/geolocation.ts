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
   * 获取位置信息（不再上传到后端，仅用于浏览器端获取）
   * 位置信息现在通过 WebSocket 由后端主动请求
   */
  async getAndUpdateLocation(): Promise<boolean> {
    try {
      const locationData = await this.requestLocation();
      if (locationData) {
        console.log('Location acquired successfully:', locationData);
        return true;
      }
      return false;
    } catch (error) {
      console.error('Failed to get location:', error);
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