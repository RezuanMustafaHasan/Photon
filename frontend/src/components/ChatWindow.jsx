import React, { useEffect, useMemo, useRef, useState } from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import { useAuth } from '../auth/AuthContext.jsx';
import {
  createRateLimitNotice,
  formatRateLimitWait,
  getRateLimitRemainingSeconds,
} from '../utils/rateLimit.js';
import { createAssistantMessage } from '../utils/chatMessages.js';

const ChatWindow = ({
  messages,
  setMessages,
  chapterName,
  lessonName,
  rateLimitNotice,
  setRateLimitNotice,
  onSourceClick,
}) => {
  const { token, showRateLimitNotice } = useAuth();
  const [draft, setDraft] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [now, setNow] = useState(Date.now());
  const scrollRef = useRef(null);

  const safeMessages = messages || [];
  const remainingSeconds = useMemo(
    () => getRateLimitRemainingSeconds(rateLimitNotice, now),
    [rateLimitNotice, now],
  );
  const isRateLimited = remainingSeconds > 0;
  const canSend = useMemo(
    () => !isSending && !isRateLimited && draft.trim().length > 0,
    [isSending, isRateLimited, draft],
  );

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
  }, [safeMessages.length]);

  useEffect(() => {
    if (!rateLimitNotice) {
      return undefined;
    }

    if (remainingSeconds <= 0) {
      setRateLimitNotice(null);
      return undefined;
    }

    const intervalId = setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => {
      clearInterval(intervalId);
    };
  }, [rateLimitNotice, remainingSeconds, setRateLimitNotice]);

  const send = async () => {
    if (!canSend) return;
    const text = draft.trim();
    setDraft('');

    const userMsgId = crypto.randomUUID();
    const aiId = crypto.randomUUID();

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, sender: 'user', text },
      { id: aiId, sender: 'ai', text: '…' },
    ]);

    setIsSending(true);

    try {
      if (!token) {
        throw new Error('Please sign in again.');
      }
      if (!chapterName || !lessonName) {
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
          chapterName,
          lessonName,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 429) {
        const notice = createRateLimitNotice(
          data,
          res.headers,
          'You are sending messages too quickly. Please wait a moment and try again.',
        );
        setRateLimitNotice(notice);
        showRateLimitNotice(notice);
        throw new Error(notice.message);
      }
      if (!res.ok) {
        throw new Error(data?.message || 'Chat failed');
      }

      setMessages((prev) => prev.map((m) => (
        m.id === aiId
          ? createAssistantMessage(data, { id: aiId, chapterName, lessonName, relatedUserText: text })
          : m
      )));
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) => (m.id === aiId ? {
          ...m,
          text: err?.message || 'Chat failed',
          textbookAnswer: '',
          extraExplanation: '',
          citations: [],
        } : m)),
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
            <ChatMessage
              key={m.id}
              message={m}
              sender={m.sender}
              text={m.text}
              onSourceClick={onSourceClick}
            />
          ))}
          <div ref={scrollRef} />
        </div>
      </div>

      {/* Input Area - Sticky Bottom */}
      <div className="sticky-bottom w-100 backdrop-blur-sm pb-4 px-4 px-md-5 px-lg-5 pt-2">
         {isRateLimited && rateLimitNotice && (
            <div className="container-sm mw-100 mb-3" style={{ maxWidth: '48rem' }}>
              <div className="bg-red-50 border border-red-100 rounded-3 p-3 text-red-700 small shadow-sm">
                <div className="fw-semibold">{rateLimitNotice.message}</div>
                <div className="mt-1">
                  Try again in {formatRateLimitWait(remainingSeconds)}.
                </div>
              </div>
            </div>
         )}
         <div className="container-sm mw-100 shadow-lg rounded-2xl bg-white" style={{ maxWidth: '48rem' }}>
            <ChatInput
              value={draft}
              onChange={setDraft}
              onSend={send}
              disabled={isSending || isRateLimited}
            />
         </div>
      </div>
    </div>
  );
};

export default ChatWindow;
