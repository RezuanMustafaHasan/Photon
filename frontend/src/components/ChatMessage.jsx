import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import { hasStructuredAssistantContent } from '../utils/chatMessages.js';
import { normalizeRichText } from '../utils/richText.js';

const MarkdownContent = ({ text }) => {
  const normalized = typeof text === 'string' ? normalizeRichText(text) : text;

  if (typeof normalized !== 'string') {
    return normalized;
  }

  return (
    <div className="chat-rich-text font-bangla">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { strict: 'ignore', throwOnError: false, errorColor: 'currentColor' }]]}
        components={{
          table: (props) => <table className="table table-sm table-bordered mb-3" {...props} />,
          th: (props) => <th className="small" {...props} />,
          td: (props) => <td className="small" {...props} />,
        }}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  );
};

const ChatMessage = ({ message, sender, text, label, onSourceClick }) => {
  const resolvedMessage = message || { sender, text };
  const currentSender = resolvedMessage.sender || sender;
  const isAI = currentSender === 'ai';
  const structured = isAI && hasStructuredAssistantContent(resolvedMessage);
  const citations = Array.isArray(resolvedMessage.citations) ? resolvedMessage.citations : [];
  const safeImages = Array.isArray(resolvedMessage.images)
    ? resolvedMessage.images.filter((item) => typeof item?.imageURL === 'string' && item.imageURL.trim().length > 0)
    : [];
  const plainText = resolvedMessage.text || text;

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
        {structured ? (
          <div className="vstack gap-3">
            {!resolvedMessage.textbookAnswer && plainText && (
              <MarkdownContent text={plainText} />
            )}

            {resolvedMessage.textbookAnswer && (
              <div>
                <div className="small fw-semibold text-primary mb-2">From your lesson</div>
                <MarkdownContent text={resolvedMessage.textbookAnswer} />
              </div>
            )}

            {resolvedMessage.extraExplanation && (
              <div className={resolvedMessage.textbookAnswer ? 'pt-3 border-top border-gray-100' : ''}>
                <div className="small fw-semibold text-secondary mb-2">Extra explanation</div>
                <MarkdownContent text={resolvedMessage.extraExplanation} />
              </div>
            )}

            {citations.length > 0 && (
              <div className="pt-3 border-top border-gray-100">
                <div className="small fw-semibold text-secondary mb-2">Sources</div>
                <div className="d-flex flex-wrap gap-2">
                  {citations.map((citation, index) => (
                    <button
                      type="button"
                      key={`${citation.sectionLabel || citation.snippet || 'source'}-${index}`}
                      onClick={() => onSourceClick && onSourceClick(citation, resolvedMessage)}
                      className="bg-orange-50 border border-orange-100 rounded-3 px-3 py-2 small text-primary fw-semibold"
                      style={{ maxWidth: '100%' }}
                    >
                      {citation.lessonName || citation.sectionLabel || 'Source lesson'}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <MarkdownContent text={plainText} />
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
                    <MarkdownContent text={image.description} />
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
