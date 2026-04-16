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

const createClearedMessages = () => ([
  {
    id: crypto.randomUUID(),
    sender: 'ai',
    text: 'Ask your question here.',
    images: [],
  },
]);

const ChatWindow = ({
  messages,
  setMessages,
  chapterName,
  lessonName,
  chatModel,
  chatModelOptions,
  onChatModelChange,
  rateLimitNotice,
  setRateLimitNotice,
  onSourceClick,
}) => {
  const { token, user, showRateLimitNotice } = useAuth();
  const [draft, setDraft] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [now, setNow] = useState(Date.now());
  const scrollRef = useRef(null);

  const safeMessages = messages || [];
  const remainingSeconds = useMemo(
    () => getRateLimitRemainingSeconds(rateLimitNotice, now),
    [rateLimitNotice, now],
  );
  const isRateLimited = remainingSeconds > 0;
  const canSend = useMemo(
    () => !isSending && !isClearing && !isRateLimited && draft.trim().length > 0,
    [draft, isClearing, isRateLimited, isSending],
  );
  const canClear = useMemo(
    () => Boolean(!isSending && !isClearing && user?.id && chapterName && lessonName),
    [chapterName, isClearing, isSending, lessonName, user?.id],
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
      { id: aiId, sender: 'ai', text: '…', images: [] },
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
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: text,
          chapterName,
          lessonName,
          chatModel,
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

      setMessages((prev) => prev.map((message) => (
        message.id === aiId
          ? createAssistantMessage(data, {
            id: aiId,
            chapterName,
            lessonName,
            relatedUserText: text,
          })
          : message
      )));
    } catch (err) {
      setMessages((prev) => prev.map((message) => (
        message.id === aiId
          ? {
            ...message,
            text: err?.message || 'Chat failed',
            textbookAnswer: '',
            extraExplanation: '',
            citations: [],
            images: [],
          }
          : message
      )));
    } finally {
      setIsSending(false);
    }
  };

  const clearChatHistory = async () => {
    if (!canClear || !token) return;

    const confirmed = window.confirm(`Delete the chat history for "${lessonName}"?`);
    if (!confirmed) return;

    setIsClearing(true);

    try {
      const res = await fetch('/api/chat/history', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          chapterName,
          lessonName,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 429) {
        const notice = createRateLimitNotice(
          data,
          res.headers,
          'Chat history is cooling down. Please wait a moment and try again.',
        );
        setRateLimitNotice(notice);
        showRateLimitNotice(notice);
        throw new Error(notice.message);
      }
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
          className="container-sm mw-100 d-flex align-items-center justify-content-between gap-3 flex-wrap"
          style={{ maxWidth: '48rem' }}
        >
          <div className="min-w-0">
            <div className="small text-secondary">Lesson chat</div>
            <div className="fw-semibold text-primary text-truncate">{lessonName || 'Select a lesson'}</div>
          </div>
          <div className="d-flex align-items-center gap-2 flex-wrap justify-content-end">
            <label className="small text-secondary d-flex align-items-center gap-2 mb-0">
              <span>Model</span>
              <select
                value={chatModel}
                onChange={(e) => onChatModelChange(e.target.value)}
                disabled={isSending || isClearing}
                className="form-select form-select-sm"
                style={{ minWidth: '14rem' }}
              >
                {chatModelOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
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
      </div>

      <div className="flex-grow-1 overflow-y-auto px-4 px-md-5 px-lg-5 py-2 vstack gap-4 custom-scrollbar">
        <div className="container-sm mw-100 vstack gap-4 pb-4" style={{ maxWidth: '48rem' }}>
          {safeMessages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              sender={message.sender}
              text={message.text}
              onSourceClick={onSourceClick}
            />
          ))}
          <div ref={scrollRef} />
        </div>
      </div>

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
            disabled={isSending || isClearing || isRateLimited}
          />
        </div>
      </div>
    </div>
  );
};

export default ChatWindow;
