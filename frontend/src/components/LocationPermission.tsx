import React, { useState, useEffect } from 'react'
import GeolocationService from '../utils/geolocation'
import './LocationPermission.css'

interface LocationPermissionProps {
  onLocationGranted?: () => void;
}

const LocationPermission: React.FC<LocationPermissionProps> = ({ onLocationGranted }) => {
  const [permissionStatus, setPermissionStatus] = useState<'granted' | 'denied' | 'prompt'>('prompt')
  const [isRequesting, setIsRequesting] = useState(false)
  const [showBanner, setShowBanner] = useState(false)

  useEffect(() => {
    const geolocationService = GeolocationService.getInstance()
    
    // 检查初始权限状态
    if (geolocationService.isServiceInitialized()) {
      const status = geolocationService.getPermissionStatus()
      setPermissionStatus(status)
      
      // 如果权限是prompt状态，显示横幅
      if (status === 'prompt') {
        setShowBanner(true)
      }
    }
  }, [])

  const handleRequestPermission = async () => {
    setIsRequesting(true)
    try {
      const geolocationService = GeolocationService.getInstance()
      const success = await geolocationService.getAndUpdateLocation()
      
      if (success) {
        setPermissionStatus('granted')
        setShowBanner(false)
        onLocationGranted?.()
      } else {
        setPermissionStatus('denied')
      }
    } catch (error) {
      console.error('Failed to request location permission:', error)
      setPermissionStatus('denied')
    } finally {
      setIsRequesting(false)
    }
  }

  const handleDismiss = () => {
    setShowBanner(false)
  }

  // 如果权限已授予或已拒绝，不显示横幅
  if (!showBanner || permissionStatus !== 'prompt') {
    return null
  }

  return (
    <div className="location-permission-banner">
      <div className="location-permission-content">
        <div className="location-permission-icon">📍</div>
        <div className="location-permission-text">
          <h4>位置权限</h4>
          <p>为了提供更精确的位置服务，我们需要获取您的地理位置信息。</p>
        </div>
        <div className="location-permission-actions">
          <button
            className="location-permission-button primary"
            onClick={handleRequestPermission}
            disabled={isRequesting}
          >
            {isRequesting ? '请求中...' : '允许'}
          </button>
          <button
            className="location-permission-button secondary"
            onClick={handleDismiss}
            disabled={isRequesting}
          >
            稍后
          </button>
        </div>
      </div>
    </div>
  )
}

export default LocationPermission 