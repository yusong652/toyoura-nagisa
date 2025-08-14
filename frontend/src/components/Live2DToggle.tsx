import React from 'react';
import { SlideToggle } from './SlideToggle';
import { useLive2D } from '../contexts/live2d/Live2DContext';

export const Live2DToggle: React.FC = () => {
  const { isLive2DEnabled, toggleLive2D } = useLive2D();

  return (
    <SlideToggle
      checked={isLive2DEnabled}
      onChange={toggleLive2D}
    />
  );
};