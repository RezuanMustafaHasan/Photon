import React, { useEffect, useRef } from 'react';

const ChatInput = ({ value, onChange, onSend, disabled }) => {
  const textareaRef = useRef(null);

  const resize = () => {
    const target = textareaRef.current;
    if (!target) return;
    target.style.height = 'auto';
    target.style.height = `${Math.min(target.scrollHeight, 120)}px`;
  };

  useEffect(() => {
    resize();
  }, [value]);

  return (
    <div className="bg-white p-3 border-top border-gray-100">
      <div className="position-relative d-flex align-items-end">
        <textarea 
          ref={textareaRef}
          rows={1}
          placeholder="Reply..." 
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onInput={resize}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
          disabled={disabled}
          className="w-100 ps-3 pe-5 py-3 bg-gray-50 border border-gray-200 rounded-2xl focus-ring-orange transition-all font-bangla placeholder-gray-400 resize-none overflow-hidden"
          style={{ paddingRight: '3.5rem', maxHeight: '120px' }}
        />
        <button
          type="button"
          disabled={disabled}
          onClick={onSend}
          className="position-absolute bottom-0 p-2 custom-gradient-btn rounded-circle text-white d-flex align-items-center justify-content-center border-0"
          style={{ right: '0.5rem', marginBottom: '0.5rem' }}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style={{ width: '1.25rem', height: '1.25rem' }}>
            <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default ChatInput;
