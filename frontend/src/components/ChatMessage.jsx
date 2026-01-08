import React from 'react';

const ChatMessage = ({ sender, text, label }) => {
  const isAI = sender === 'ai';

  return (
    <div className={`d-flex flex-column ${isAI ? 'align-items-start' : 'align-items-end'} mb-4`}>
      <span className="text-xs fw-semibold text-secondary mb-2 px-1">
        {label || (isAI ? "AI's response" : "User's response")}
      </span>
      <div 
        className={`message-bubble px-4 py-3 rounded-2xl text-base leading-relaxed font-bangla shadow-sm ${
          isAI 
            ? 'bg-white text-primary border border-gray-100 rounded-tl-sm' 
            : 'bg-background text-primary border border-orange-100 rounded-tr-sm'
        }`}
      >
        {text}
      </div>
    </div>
  );
};

export default ChatMessage;
