import React, { useEffect, useMemo, useRef, useState } from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import { useAuth } from '../auth/AuthContext.jsx';

const ChatWindow = ({ messages, setMessages, chapterName, lessonName }) => {
  const { token, user } = useAuth();
  const [draft, setDraft] = useState('');
  const [isSending, setIsSending] = useState(false);
  const scrollRef = useRef(null);

  const safeMessages = messages || [];
  const canSend = useMemo(() => !isSending && draft.trim().length > 0, [isSending, draft]);

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

  return (
    <div className="d-flex flex-column h-100 bg-background position-relative">
      {/* Messages Area - Scrollable */}
      <div className="flex-grow-1 overflow-y-auto px-4 px-md-5 px-lg-5 py-4 vstack gap-4 custom-scrollbar">
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
              disabled={isSending}
            />
         </div>
      </div>
    </div>
  );
};

export default ChatWindow;
