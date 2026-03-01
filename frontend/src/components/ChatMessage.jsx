import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';

const ChatMessage = ({ sender, text, label }) => {
  const isAI = sender === 'ai';
  const isString = typeof text === 'string';
  const normalized = isString
    ? text
        .replace(/\\\[((?:.|\n)*?)\\\]/g, (_, inner) => `$$\n${inner}\n$$`)
        .replace(/\\\((.*?)\\\)/g, (_, inner) => `$${inner}$`)
    : text;

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
        {isString ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={{
              table: (props) => <table className="table table-sm table-bordered mb-3" {...props} />,
              th: (props) => <th className="small" {...props} />,
              td: (props) => <td className="small" {...props} />,
            }}
          >
            {normalized}
          </ReactMarkdown>
        ) : (
          normalized
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
