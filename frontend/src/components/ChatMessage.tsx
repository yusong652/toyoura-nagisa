import React, { useState } from 'react';
import { Message } from '../types/chat';
import ImagePreview from './ImagePreview';

interface ChatMessageProps {
  message: Message;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const [previewImage, setPreviewImage] = useState<string | null>(null);

  const handleImageClick = (imageUrl: string) => {
    setPreviewImage(imageUrl);
  };

  return (
    <>
      <div className={`chat-message ${message.sender}`}>
        <div className="message-content">
          {message.text && <p>{message.text}</p>}
          {message.files && message.files.map((file, index) => (
            file.type.startsWith('image/') ? (
              <img
                key={index}
                src={file.data}
                alt={file.name}
                className="message-image"
                onClick={() => handleImageClick(file.data)}
                style={{
                  maxWidth: '300px',
                  maxHeight: '300px',
                  cursor: 'pointer',
                  borderRadius: '8px',
                  marginTop: '8px',
                }}
              />
            ) : (
              <div key={index} className="file-attachment">
                <a href={file.data} target="_blank" rel="noopener noreferrer">
                  {file.name}
                </a>
              </div>
            )
          ))}
        </div>
      </div>
      {previewImage && (
        <ImagePreview
          open={!!previewImage}
          onClose={() => setPreviewImage(null)}
          imageUrl={previewImage}
        />
      )}
    </>
  );
};

export default ChatMessage; 