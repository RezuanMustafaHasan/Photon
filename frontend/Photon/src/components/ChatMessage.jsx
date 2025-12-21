import React from 'react';

const ChatMessage = ({ sender, text, label }) => {
  const isAI = sender === 'ai';

  return (
    <div className={`flex flex-col ${isAI ? 'items-start' : 'items-end'} mb-6`}>
      <span className="text-xs font-semibold text-secondary mb-2 px-1">
        {label || (isAI ? "AI's response" : "User's response")}
      </span>
      <div 
        className={`max-w-[90%] md:max-w-[80%] px-6 py-4 rounded-2xl text-base leading-relaxed font-bangla shadow-sm ${
          isAI 
            ? 'bg-white text-primary border border-gray-100 rounded-tl-sm' 
            : 'bg-[#FFF7ED] text-primary border border-orange-100 rounded-tr-sm'
        }`}
      >
        {text}
      </div>
    </div>
  );
};

export default ChatMessage;
