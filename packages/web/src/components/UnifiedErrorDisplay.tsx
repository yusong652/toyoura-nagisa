import React, { useState, useEffect, useCallback } from 'react';
import { Alert, Snackbar, IconButton } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import './UnifiedErrorDisplay.css';

export interface ErrorDisplayConfig {
  message: string;
  severity?: 'error' | 'warning' | 'info';
  duration?: number;
  position?: 'top' | 'bottom' | 'center';
  persistent?: boolean;
  actionLabel?: string;
  onAction?: () => void;
}

interface UnifiedErrorDisplayProps {
  error: ErrorDisplayConfig | null;
  onClose: () => void;
}

const UnifiedErrorDisplay: React.FC<UnifiedErrorDisplayProps> = ({ error, onClose }) => {
  const [isVisible, setIsVisible] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);

  // Handle error state changes with animation
  useEffect(() => {
    if (error) {
      setIsAnimating(true);
      // Small delay to ensure smooth animation
      const timer = setTimeout(() => {
        setIsVisible(true);
        setIsAnimating(false);
      }, 50);
      return () => clearTimeout(timer);
    } else {
      setIsAnimating(true);
      setIsVisible(false);
      // Wait for exit animation before clearing
      const timer = setTimeout(() => {
        setIsAnimating(false);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [error]);

  const handleClose = useCallback((_?: React.SyntheticEvent | Event, reason?: string) => {
    if (reason === 'clickaway') {
      return;
    }
    onClose();
  }, [onClose]);

  if (!error && !isAnimating) {
    return null;
  }

  const {
    message = '',
    severity = 'error',
    duration = 6000,
    position = 'bottom',
    persistent = false,
    actionLabel,
    onAction
  } = error || {};

  const anchorOrigin = {
    vertical: position === 'top' ? 'top' as const : 'bottom' as const,
    horizontal: 'center' as const
  };

  return (
    <Snackbar
      open={isVisible}
      autoHideDuration={persistent ? null : duration}
      onClose={handleClose}
      anchorOrigin={anchorOrigin}
      className={`unified-error-display ${severity} position-${position}`}
      TransitionProps={{
        onExited: () => setIsAnimating(false)
      }}
    >
      <Alert 
        severity={severity}
        onClose={persistent ? undefined : handleClose}
        className="unified-error-alert"
        action={
          <>
            {actionLabel && onAction && (
              <button
                className="unified-error-action"
                onClick={onAction}
              >
                {actionLabel}
              </button>
            )}
            {persistent && (
              <IconButton
                size="small"
                onClick={handleClose}
                className="unified-error-close"
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            )}
          </>
        }
      >
        {message}
      </Alert>
    </Snackbar>
  );
};

export default UnifiedErrorDisplay;