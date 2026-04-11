import React, { useEffect, useMemo, useRef, useState } from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import { useAuth } from '../auth/AuthContext.jsx';

const createClearedMessages = () => ([
  {
    id: crypto.randomUUID(),
    sender: 'ai',
    text: 'Ask your question here.',
    images: [],
  },
]);

const ChatWindow = ({ messages, setMessages, chapterName, lessonName }) => {
  const { token, user } = useAuth();
  const [draft, setDraft] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const scrollRef = useRef(null);

  const safeMessages = messages || [];
  const canSend = useMemo(() => !isSending && !isClearing && draft.trim().length > 0, [isSending, isClearing, draft]);
  const canClear = useMemo(
    () => Boolean(!isSending && !isClearing && user?.id && chapterName && lessonName),
    [isSending, isClearing, user?.id, chapterName, lessonName],
  );

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
  }, [safeMessages.length]);

  const send = async () => {
    if (!canSend) return;
    const text = draft.trim();
    setDraft('');

    const userMsgId = crypto.randomUUID();
    const aiId = crypto.randomUUID();

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, sender: 'user', text },
      { id: aiId, sender: 'ai', text: '…', images: [] },
    ]);

    setIsSending(true);

    try {
      if (!user?.id || !chapterName || !lessonName) {
        throw new Error('Select a chapter and lesson first');
      }
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message: text,
          userId: user.id,
          chapterName,
          lessonName,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.message || 'Chat failed');
      }

      const responseImages = Array.isArray(data?.images)
        ? data.images
            .map((item) => {
              const imageURL = typeof item?.imageURL === 'string' ? item.imageURL.trim() : '';
              const description = typeof item?.description === 'string' ? item.description : '';
              const topic = Array.isArray(item?.topic)
                ? item.topic.filter((entry) => typeof entry === 'string' && entry.trim().length > 0)
                : [];

              return {
                imageURL,
                description,
                topic,
              };
            })
            .filter((item) => item.imageURL)
        : [];

      setMessages((prev) =>
        prev.map((m) => (m.id === aiId ? { ...m, text: data.response || '', images: responseImages } : m)),
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) => (m.id === aiId ? { ...m, text: err?.message || 'Chat failed', images: [] } : m)),
      );
    } finally {
      setIsSending(false);
    }
  };

  const clearChatHistory = async () => {
    if (!canClear) return;

    const confirmed = window.confirm(`Delete the chat history for "${lessonName}"?`);
    if (!confirmed) return;

    setIsClearing(true);

    try {
      const res = await fetch('/api/chat/history', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          userId: user.id,
          chapterName,
          lessonName,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.deleted) {
        throw new Error(data?.message || 'Failed to delete chat history');
      }

      setMessages(createClearedMessages());
      setDraft('');
    } catch (err) {
      window.alert(err?.message || 'Failed to delete chat history');
    } finally {
      setIsClearing(false);
    }
  };

  return (
    <div className="d-flex flex-column h-100 bg-background position-relative">
      <div className="px-4 px-md-5 px-lg-5 pt-4 pb-2">
        <div
          className="container-sm mw-100 d-flex align-items-center justify-content-between gap-3"
          style={{ maxWidth: '48rem' }}
        >
          <div className="min-w-0">
            <div className="small text-secondary">Lesson chat</div>
            <div className="fw-semibold text-primary text-truncate">{lessonName || 'Select a lesson'}</div>
          </div>
          <button
            type="button"
            className="btn btn-sm btn-outline-danger flex-shrink-0"
            onClick={clearChatHistory}
            disabled={!canClear}
          >
            {isClearing ? 'Deleting…' : 'Clear chat'}
          </button>
        </div>
      </div>

      {/* Messages Area - Scrollable */}
      <div className="flex-grow-1 overflow-y-auto px-4 px-md-5 px-lg-5 py-2 vstack gap-4 custom-scrollbar">
        <div className="container-sm mw-100 vstack gap-4 pb-4" style={{ maxWidth: '48rem' }}>
          {safeMessages.map((m) => (
            <ChatMessage key={m.id} sender={m.sender} text={m.text} images={m.images} />
          ))}
          <div ref={scrollRef} />
        </div>
      </div>

      {/* Input Area - Sticky Bottom */}
      <div className="sticky-bottom w-100 backdrop-blur-sm pb-4 px-4 px-md-5 px-lg-5 pt-2">
         <div className="container-sm mw-100 shadow-lg rounded-2xl bg-white" style={{ maxWidth: '48rem' }}>
            <ChatInput
              value={draft}
              onChange={setDraft}
              onSend={send}
              disabled={isSending || isClearing}
            />
         </div>
      </div>
    </div>
  );
};

export default ChatWindow;
