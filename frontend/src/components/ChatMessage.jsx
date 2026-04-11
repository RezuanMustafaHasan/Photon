import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';

const ChatMessage = ({ sender, text, label, images }) => {
  const isAI = sender === 'ai';
  const isString = typeof text === 'string';
  const safeImages = Array.isArray(images)
    ? images.filter((item) => typeof item?.imageURL === 'string' && item.imageURL.trim().length > 0)
    : [];

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

      {isAI && safeImages.length > 0 && (
        <div className="mt-3 w-100 vstack gap-3" style={{ maxWidth: '80%' }}>
          {safeImages.map((image, index) => {
            const topics = Array.isArray(image.topic) ? image.topic.filter(Boolean) : [];
            return (
              <figure key={`${image.imageURL}-${index}`} className="bg-white border border-orange-100 rounded-2xl p-2 mb-0 shadow-sm">
                <a href={image.imageURL} target="_blank" rel="noreferrer" className="d-block text-decoration-none">
                  <img
                    src={image.imageURL}
                    alt={image.description || 'Lesson visual'}
                    loading="lazy"
                    className="w-100 rounded-xl"
                    style={{ maxHeight: '18rem', objectFit: 'cover' }}
                  />
                </a>

                {image.description && (
                  <figcaption className="small text-secondary mt-2">{image.description}</figcaption>
                )}

                {topics.length > 0 && (
                  <div className="d-flex flex-wrap gap-2 mt-2">
                    {topics.map((topic, topicIndex) => (
                      <span key={`${topic}-${topicIndex}`} className="badge bg-orange-50 text-secondary border border-orange-100">
                        {topic}
                      </span>
                    ))}
                  </div>
                )}
              </figure>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ChatMessage;
