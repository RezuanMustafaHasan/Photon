import React, { useRef, useEffect } from 'react';

const ChatInput = () => {
  const textareaRef = useRef(null);

  const handleInput = (e) => {
    const target = e.target;
    target.style.height = 'auto';
    target.style.height = `${Math.min(target.scrollHeight, 120)}px`; // Cap height at 120px
  };

  return (
    <div className="bg-white p-4 border-t border-gray-100 sticky bottom-0 z-20">
      <div className="relative flex items-end">
        <textarea 
          ref={textareaRef}
          rows={1}
          placeholder="Reply..." 
          onInput={handleInput}
          className="w-full pl-5 pr-14 py-3.5 bg-gray-50 border border-gray-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-orange-100 focus:border-orange-300 transition-all font-bangla placeholder:text-gray-400 resize-none overflow-hidden max-h-[120px]"
        />
        <button className="absolute right-2 bottom-2 p-2 bg-gradient-to-br from-cta-start to-cta-end rounded-full text-white shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 flex items-center justify-center">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
            <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default ChatInput;
