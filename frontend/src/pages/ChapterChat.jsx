import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Navbar from '../components/Navbar';
import LessonSidebar from '../components/LessonSidebar';
import ChatWindow from '../components/ChatWindow';
import { useAuth } from '../auth/AuthContext.jsx';
import { createRateLimitNotice, getRateLimitRemainingSeconds } from '../utils/rateLimit.js';
import { createAssistantMessage, normalizeHistoryMessage } from '../utils/chatMessages.js';

const createInitialMessages = () => ([
  {
    id: crypto.randomUUID(),
    sender: 'ai',
    text: 'Ask your question here.',
    images: [],
  },
]);

const mapHistoryMessages = (history, { chapterName, lessonName }) => {
  let lastUserText = '';

  return (Array.isArray(history) ? history : [])
    .map((item) => {
      const mapped = normalizeHistoryMessage(item, { chapterName, lessonName });
      if (!mapped) {
        return null;
      }

      if (mapped.sender === 'user') {
        lastUserText = mapped.text;
        return mapped;
      }

      return {
        ...mapped,
        relatedUserText: mapped.relatedUserText || lastUserText,
      };
    })
    .filter((item) => item && (
      item.text
      || item.textbookAnswer
      || item.extraExplanation
      || item.citations?.length
      || item.images?.length
    ));
};

const ChapterChat = ({ chapterTitle, onBack }) => {
  const { token, showRateLimitNotice } = useAuth();
  const [selectedLesson, setSelectedLesson] = useState('');
  const [messagesByLesson, setMessagesByLesson] = useState({});
  const [rateLimitNotice, setRateLimitNotice] = useState(null);
  const lessonActivityRef = useRef({
    chapterName: '',
    lessonName: '',
    bufferedMs: 0,
    activeSince: null,
  });

  const activeLesson = selectedLesson || 'general';
  const currentMessages = useMemo(() => {
    return messagesByLesson[activeLesson] || createInitialMessages();
  }, [activeLesson, messagesByLesson]);

  const setCurrentMessages = (updater) => {
    setMessagesByLesson((prev) => {
      const previousMessages = prev[activeLesson] || createInitialMessages();
      const nextMessages = typeof updater === 'function' ? updater(previousMessages) : updater;
      return { ...prev, [activeLesson]: nextMessages };
    });
  };

  const handleSelectLesson = (lesson) => {
    const nextLesson = lesson || '';
    setSelectedLesson(nextLesson);
  };

  const postLessonActivity = useCallback(async ({
    chapterName,
    lessonName,
    seconds,
    keepalive = false,
  }) => {
    if (!token || !chapterName || !lessonName || seconds <= 0) {
      return;
    }

    await fetch('/api/mastery/lesson-activity', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        chapterName,
        lessonName,
        seconds,
      }),
      keepalive,
    });
  }, [token]);

  const loadLessonHistory = useCallback(async (lessonName) => {
    if (!token || !chapterTitle || !lessonName) {
      return createInitialMessages();
    }

    try {
      const url = new URL('/api/chat/history', window.location.origin);
      url.searchParams.set('chapterName', chapterTitle);
      url.searchParams.set('lessonName', lessonName);
      const res = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
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
        return null;
      }
      if (!res.ok) {
        return createInitialMessages();
      }

      const mapped = mapHistoryMessages(data.history, { chapterName: chapterTitle, lessonName });
      const nextMessages = mapped.length ? mapped : createInitialMessages();
      setMessagesByLesson((prev) => ({
        ...prev,
        [lessonName]: nextMessages,
      }));
      return nextMessages;
    } catch {
      const fallbackMessages = createInitialMessages();
      setMessagesByLesson((prev) => ({
        ...prev,
        [lessonName]: fallbackMessages,
      }));
      return fallbackMessages;
    }
  }, [chapterTitle, showRateLimitNotice, token]);

  const handleSourceClick = useCallback(async (citation, sourceMessage) => {
    const targetLesson = typeof citation?.lessonName === 'string' ? citation.lessonName.trim() : '';
    if (!token || !chapterTitle || !targetLesson) {
      return;
    }

    if (chapterTitle) {
      localStorage.setItem(`photon_last_lesson_${chapterTitle}`, targetLesson);
    }

    if (!messagesByLesson[targetLesson]) {
      const loadedMessages = await loadLessonHistory(targetLesson);
      if (loadedMessages === null) {
        return;
      }
    }

    setSelectedLesson(targetLesson);

    const requestPrompt = 'Please introduce this lesson simply for a student. Explain what this lesson is mainly about, what the core idea is, and include the most important formula or definition only if it is relevant. Keep it clear, grounded, and easy to understand.';
    const aiId = crypto.randomUUID();

    setMessagesByLesson((prev) => {
      const existingMessages = prev[targetLesson] || createInitialMessages();
      const withoutInitialPrompt = (
        existingMessages.length === 1
        && existingMessages[0]?.sender === 'ai'
        && existingMessages[0]?.text === 'Ask your question here.'
      ) ? [] : existingMessages;
      return {
        ...prev,
        [targetLesson]: [
          ...withoutInitialPrompt,
          { id: aiId, sender: 'ai', text: '…' },
        ],
      };
    });

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: requestPrompt,
          chapterName: chapterTitle,
          lessonName: targetLesson,
          historyMode: 'assistant_only',
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

      setMessagesByLesson((prev) => ({
        ...prev,
        [targetLesson]: (prev[targetLesson] || []).map((message) => (
          message.id === aiId
            ? createAssistantMessage(data, {
              id: aiId,
              chapterName: chapterTitle,
              lessonName: targetLesson,
              relatedUserText: typeof sourceMessage?.relatedUserText === 'string' ? sourceMessage.relatedUserText.trim() : '',
            })
            : message
        )),
      }));
    } catch (error) {
      setMessagesByLesson((prev) => ({
        ...prev,
        [targetLesson]: (prev[targetLesson] || []).map((message) => (
          message.id === aiId
            ? {
              ...message,
              text: error?.message || 'Chat failed',
              textbookAnswer: '',
              extraExplanation: '',
              citations: [],
              images: [],
            }
            : message
        )),
      }));
    }
  }, [chapterTitle, loadLessonHistory, messagesByLesson, showRateLimitNotice, token]);

  const pauseLessonTracking = useCallback(() => {
    const state = lessonActivityRef.current;
    if (state.activeSince !== null) {
      state.bufferedMs += Date.now() - state.activeSince;
      state.activeSince = null;
    }
  }, []);

  const canTrackLesson = useCallback(() => (
    Boolean(token && chapterTitle && selectedLesson)
    && typeof document !== 'undefined'
    && document.visibilityState === 'visible'
    && document.hasFocus()
  ), [chapterTitle, selectedLesson, token]);

  const resumeLessonTracking = useCallback(() => {
    const state = lessonActivityRef.current;
    if (!canTrackLesson()) {
      return;
    }

    if (state.chapterName !== chapterTitle || state.lessonName !== selectedLesson) {
      return;
    }

    if (state.activeSince === null) {
      state.activeSince = Date.now();
    }
  }, [canTrackLesson, chapterTitle, selectedLesson]);

  const flushLessonSnapshot = useCallback(async (snapshot, { force = false, keepalive = false } = {}) => {
    const seconds = Math.floor((snapshot?.bufferedMs || 0) / 1000);
    if (!snapshot?.chapterName || !snapshot?.lessonName || seconds < 1) {
      return;
    }
    if (!force && seconds < 15) {
      return;
    }

    try {
      await postLessonActivity({
        chapterName: snapshot.chapterName,
        lessonName: snapshot.lessonName,
        seconds,
        keepalive,
      });
    } catch {
      // Best effort only. Mastery tracking must not interrupt the chat flow.
    }
  }, [postLessonActivity]);

  const flushCurrentLessonActivity = useCallback(async ({ force = false, keepalive = false } = {}) => {
    pauseLessonTracking();
    const snapshot = {
      ...lessonActivityRef.current,
    };
    const seconds = Math.floor((snapshot.bufferedMs || 0) / 1000);
    if (!snapshot.chapterName || !snapshot.lessonName || seconds < 1 || (!force && seconds < 15)) {
      resumeLessonTracking();
      return;
    }

    lessonActivityRef.current.bufferedMs = Math.max(0, lessonActivityRef.current.bufferedMs - (seconds * 1000));

    try {
      await postLessonActivity({
        chapterName: snapshot.chapterName,
        lessonName: snapshot.lessonName,
        seconds,
        keepalive,
      });
    } catch {
      lessonActivityRef.current.bufferedMs += seconds * 1000;
    } finally {
      if (!keepalive) {
        resumeLessonTracking();
      }
    }
  }, [pauseLessonTracking, postLessonActivity, resumeLessonTracking]);

  useEffect(() => {
    if (!rateLimitNotice) {
      return undefined;
    }

    const remainingSeconds = getRateLimitRemainingSeconds(rateLimitNotice);
    if (remainingSeconds <= 0) {
      setRateLimitNotice(null);
      return undefined;
    }

    const timeoutId = setTimeout(() => {
      setRateLimitNotice(null);
    }, remainingSeconds * 1000);

    return () => {
      clearTimeout(timeoutId);
    };
  }, [rateLimitNotice]);

  useEffect(() => {
    if (!selectedLesson || messagesByLesson[selectedLesson]) {
      return;
    }

    loadLessonHistory(selectedLesson);
  }, [loadLessonHistory, messagesByLesson, selectedLesson]);

  useEffect(() => {
    const previousState = lessonActivityRef.current;
    pauseLessonTracking();

    if (previousState.chapterName && previousState.lessonName) {
      flushLessonSnapshot(
        {
          ...previousState,
          bufferedMs: previousState.bufferedMs,
        },
        { force: true },
      );
    }

    lessonActivityRef.current = {
      chapterName: chapterTitle || '',
      lessonName: selectedLesson || '',
      bufferedMs: 0,
      activeSince: null,
    };

    resumeLessonTracking();
  }, [chapterTitle, flushLessonSnapshot, pauseLessonTracking, resumeLessonTracking, selectedLesson]);

  useEffect(() => {
    const intervalId = setInterval(() => {
      flushCurrentLessonActivity();
    }, 15000);

    return () => {
      clearInterval(intervalId);
    };
  }, [flushCurrentLessonActivity]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'visible' && document.hasFocus()) {
        resumeLessonTracking();
        return;
      }

      pauseLessonTracking();
      flushCurrentLessonActivity({ force: true });
    };

    const handleFocus = () => {
      resumeLessonTracking();
    };

    const handleBlur = () => {
      pauseLessonTracking();
      flushCurrentLessonActivity({ force: true });
    };

    const handlePageHide = () => {
      pauseLessonTracking();
      flushCurrentLessonActivity({ force: true, keepalive: true });
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);
    window.addEventListener('blur', handleBlur);
    window.addEventListener('pagehide', handlePageHide);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleFocus);
      window.removeEventListener('blur', handleBlur);
      window.removeEventListener('pagehide', handlePageHide);
      handlePageHide();
    };
  }, [flushCurrentLessonActivity, pauseLessonTracking, resumeLessonTracking]);

  return (
    <div className="vh-100 d-flex flex-column bg-background overflow-hidden">
      <Navbar examPrefillChapter={chapterTitle} />
      
      <main className="flex-grow-1 d-flex overflow-hidden position-relative">
        {/* Left Sidebar - Fixed Width & Scrollable */}
        <div className="d-none d-lg-block w-sidebar-lg w-sidebar-xl h-100 flex-shrink-0 border-end border-gray-100 bg-white">
          <LessonSidebar
            chapterTitle={chapterTitle}
            selectedLesson={selectedLesson}
            onSelectLesson={handleSelectLesson}
          />
        </div>
        
        {/* Right Chat Area - Flex Grow & Independent Scroll */}
        <div className="flex-grow-1 h-100 position-relative d-flex flex-column" style={{ minWidth: 0 }}>
           {/* Back Button for Mobile/Tablet */}
           <div className="d-lg-none p-3 border-bottom border-gray-100 bg-white d-flex align-items-center gap-2">
              <button onClick={onBack} className="small fw-medium text-secondary d-flex align-items-center gap-1 border-0 bg-transparent">
                ← Back
              </button>
              <span className="fw-bold text-primary">{chapterTitle || 'Chapter'}</span>
           </div>

           <ChatWindow
             messages={currentMessages}
             setMessages={setCurrentMessages}
             chapterName={chapterTitle}
             lessonName={selectedLesson}
             rateLimitNotice={rateLimitNotice}
             setRateLimitNotice={setRateLimitNotice}
             onSourceClick={handleSourceClick}
           />
        </div>
      </main>
    </div>
  );
};

export default ChapterChat;
