import React from 'react';
import './ConnectionError.css';

interface ConnectionErrorProps {
  message: string;
  onRetry: () => void;
}

const ConnectionError: React.FC<ConnectionErrorProps> = ({ message, onRetry }) => {
  return (
    <div className="connection-error">
      <div className="connection-error-content">
        <svg className="connection-error-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M12 8V12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M12 16H12.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <h3>连接错误</h3>
        <p>{message || '无法连接到服务器，请检查后端服务是否正常运行。'}</p>
        <button className="retry-button" onClick={onRetry}>
          重试连接
        </button>
      </div>
    </div>
  );
};

export default ConnectionError; 