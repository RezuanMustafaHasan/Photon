import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';

const normalizeMarkdownWithMath = (value) => {
  if (typeof value !== 'string') {
    return value;
  }

  return value
    .replace(/\\\[((?:.|\n)*?)\\\]/g, (_, inner) => `$$\n${inner}\n$$`)
    .replace(/\\\((.*?)\\\)/g, (_, inner) => `$${inner}$`);
};

const ChatMessage = ({ sender, text, label, images }) => {
  const isAI = sender === 'ai';
  const isString = typeof text === 'string';
  const safeImages = Array.isArray(images)
    ? images.filter((item) => typeof item?.imageURL === 'string' && item.imageURL.trim().length > 0)
    : [];

  const normalized = isString ? normalizeMarkdownWithMath(text) : text;

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
        {isAI && safeImages.length > 0 && (
          <div className="mt-3 vstack gap-3">
            {safeImages.map((image, index) => (
              <figure
                key={`${image.imageURL}-${index}`}
                className="mx-auto mb-0 d-flex flex-column align-items-center"
                style={{ width: '100%', maxWidth: '26rem' }}
              >
                <a
                  href={image.imageURL}
                  target="_blank"
                  rel="noreferrer"
                  className="d-block text-decoration-none w-100"
                >
                  <div
                    className="w-100 rounded-4 overflow-hidden border border-orange-100 bg-orange-50 d-flex justify-content-center align-items-center"
                    style={{ minHeight: '10rem', maxHeight: '16rem' }}
                  >
                    <img
                      src={image.imageURL}
                      alt={image.description || 'Lesson visual'}
                      loading="lazy"
                      className="w-100 h-100"
                      style={{ objectFit: 'contain' }}
                    />
                  </div>
                </a>

                {typeof image.description === 'string' && image.description.trim() && (
                  <figcaption className="small text-secondary mt-2 w-100">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                      components={{
                        p: (props) => <p className="mb-0" {...props} />,
                      }}
                    >
                      {normalizeMarkdownWithMath(image.description)}
                    </ReactMarkdown>
                  </figcaption>
                )}
              </figure>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
