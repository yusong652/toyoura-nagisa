import React, { createContext, useContext, useState } from 'react';

interface Live2DContextType {
  isLive2DEnabled: boolean;
  toggleLive2D: () => void;
}

const Live2DContext = createContext<Live2DContextType | undefined>(undefined);

export const Live2DProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Load the saved preference from localStorage, default to true (enabled)
  const [isLive2DEnabled, setIsLive2DEnabled] = useState<boolean>(() => {
    const saved = localStorage.getItem('live2d-enabled');
    return saved !== null ? saved === 'true' : true;
  });

  const toggleLive2D = () => {
    setIsLive2DEnabled(prev => {
      const newValue = !prev;
      localStorage.setItem('live2d-enabled', String(newValue));
      return newValue;
    });
  };

  return (
    <Live2DContext.Provider value={{ isLive2DEnabled, toggleLive2D }}>
      {children}
    </Live2DContext.Provider>
  );
};

export const useLive2D = () => {
  const context = useContext(Live2DContext);
  if (!context) {
    throw new Error('useLive2D must be used within a Live2DProvider');
  }
  return context;
};