import React, { useEffect, useMemo, useRef, useState } from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import { useAuth } from '../auth/AuthContext.jsx';

const ChatWindow = () => {
  const { token } = useAuth();
  const [messages, setMessages] = useState(() => ([
    {
      id: crypto.randomUUID(),
      sender: 'ai',
      text: 'Ask your question here.',
    },
  ]));
  const [draft, setDraft] = useState('');
  const [isSending, setIsSending] = useState(false);
  const scrollRef = useRef(null);

  const canSend = useMemo(() => !isSending && draft.trim().length > 0, [isSending, draft]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
  }, [messages.length]);

  const send = async () => {
    if (!canSend) return;
    const text = draft.trim();
    setDraft('');

    const userId = crypto.randomUUID();
    const aiId = crypto.randomUUID();

    setMessages((prev) => [
      ...prev,
      { id: userId, sender: 'user', text },
      { id: aiId, sender: 'ai', text: '…' },
    ]);

    setIsSending(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.message || 'Chat failed');
      }

      setMessages((prev) =>
        prev.map((m) => (m.id === aiId ? { ...m, text: data.response || '' } : m)),
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) => (m.id === aiId ? { ...m, text: err?.message || 'Chat failed' } : m)),
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
          {messages.map((m) => (
            <ChatMessage key={m.id} sender={m.sender} text={m.text} />
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
