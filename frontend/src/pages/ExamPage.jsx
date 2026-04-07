import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import { useLocation, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext.jsx';
import { createRateLimitNotice } from '../utils/rateLimit.js';

const QUESTION_COUNT_OPTIONS = [20, 30, 40, 50];
const MIN_QUESTION_COUNT = 1;
const MAX_QUESTION_COUNT = 50;
const OPTION_LABELS = ['A', 'B', 'C', 'D'];
const BANGLA_REGEX = /[\u0980-\u09FF]/;

const getBanglaClass = (value) => (BANGLA_REGEX.test(String(value || '')) ? 'font-bangla' : '');

const normalizeMathText = (value) => String(value || '')
  .replace(/\\\[((?:.|\n)*?)\\\]/g, (_, inner) => `$$\n${inner}\n$$`)
  .replace(/\\\((.*?)\\\)/g, (_, inner) => `$${inner}$`);

const getScoreComment = (percentage) => {
  if (percentage >= 95) return 'Excellent';
  if (percentage >= 90) return 'Very Good';
  if (percentage >= 80) return 'Good';
  return 'Need improvements';
};

const buildWrongQuestions = (questions, answers) => (
  (questions || [])
    .map((question) => {
      const selectedOptionIndex = answers?.[question.id];
      if (selectedOptionIndex === undefined || selectedOptionIndex === question.correctOptionIndex) {
        return null;
      }

      return {
        id: question.id,
        chapterName: question.chapterName,
        topicName: question.topicName,
        question: question.question,
        options: question.options,
        correctOptionIndex: question.correctOptionIndex,
        selectedOptionIndex,
      };
    })
    .filter(Boolean)
);

const buildFallbackSummary = (scoreComment, wrongQuestions) => {
  const recommendedTopicsMap = new Map();
  wrongQuestions.forEach((question) => {
    const key = `${question.chapterName}::${question.topicName}`;
    if (!recommendedTopicsMap.has(key)) {
      recommendedTopicsMap.set(key, {
        chapterName: question.chapterName,
        topicName: question.topicName,
        reason: 'Review this topic again because at least one question from it was answered incorrectly.',
      });
    }
  });

  return {
    headline: 'Performance summary is unavailable',
    overallComment: `${scoreComment}. Your answers are shown below, but the AI summary could not be loaded this time.`,
    weaknesses: wrongQuestions.length
      ? ['Review the incorrect questions below and revisit the related topics.']
      : ['No weaknesses were detected in this attempt.'],
    recommendedTopics: Array.from(recommendedTopicsMap.values()),
    studyAdvice: wrongQuestions.length
      ? ['Focus on the missed topics first, then try another short mixed-topic exam.']
      : ['Keep practicing to maintain this level of accuracy.'],
  };
};

const formatAttemptDate = (value) => {
  if (!value) {
    return 'Saved exam';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Saved exam';
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
};

const getAttemptChapterNames = (selections) => (
  Array.isArray(selections)
    ? selections
      .map((selection) => String(selection?.chapterName || '').trim())
      .filter(Boolean)
    : []
);

const formatAttemptTitle = (chapterNames) => {
  const names = Array.isArray(chapterNames) ? chapterNames.filter(Boolean) : [];
  if (!names.length) {
    return 'Saved exam';
  }

  if (names.length <= 2) {
    return names.join(', ');
  }

  return `${names.slice(0, 2).join(', ')} + ${names.length - 2} others`;
};

const ExamRichText = ({ text, inline = false }) => {
  const normalizedText = normalizeMathText(text);

  return (
    <div className={`exam-rich-text ${inline ? 'exam-rich-text-inline' : ''} ${getBanglaClass(normalizedText)}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          p: ({ children }) => <p className="mb-0">{children}</p>,
          ul: ({ children }) => <ul className="mb-0 ps-4">{children}</ul>,
          ol: ({ children }) => <ol className="mb-0 ps-4">{children}</ol>,
        }}
      >
        {normalizedText}
      </ReactMarkdown>
    </div>
  );
};

const ExamPage = () => {
  const { token, showRateLimitNotice } = useAuth();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const preselectedChapter = searchParams.get('chapter')?.trim() || '';
  const recommendedExam = useMemo(() => {
    const candidate = location.state?.recommendedExam;
    if (!candidate || typeof candidate !== 'object') {
      return null;
    }

    const chapterName = String(candidate.chapterName || '').trim();
    const lessonNames = Array.isArray(candidate.lessonNames)
      ? candidate.lessonNames.map((lessonName) => String(lessonName || '').trim()).filter(Boolean)
      : [];

    if (!chapterName || !lessonNames.length) {
      return null;
    }

    return {
      chapterName,
      lessonNames: Array.from(new Set(lessonNames)),
    };
  }, [location.state]);
  const resultSummaryRef = useRef(null);

  const [chapters, setChapters] = useState([]);
  const [chaptersStatus, setChaptersStatus] = useState('idle');
  const [chaptersError, setChaptersError] = useState('');

  const [selectedChapters, setSelectedChapters] = useState([]);
  const [topicsByChapter, setTopicsByChapter] = useState({});
  const [topicStatusByChapter, setTopicStatusByChapter] = useState({});
  const [topicErrorsByChapter, setTopicErrorsByChapter] = useState({});
  const [selectedTopicsByChapter, setSelectedTopicsByChapter] = useState({});
  const [topicSearchByChapter, setTopicSearchByChapter] = useState({});

  const [questionCountMode, setQuestionCountMode] = useState('preset');
  const [questionCount, setQuestionCount] = useState(20);
  const [customQuestionCount, setCustomQuestionCount] = useState('20');
  const [builderError, setBuilderError] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  const [activeAttempt, setActiveAttempt] = useState(null);
  const [currentCompletedAttempt, setCurrentCompletedAttempt] = useState(null);
  const [openedHistoryAttempt, setOpenedHistoryAttempt] = useState(null);
  const [completionStatus, setCompletionStatus] = useState('idle');
  const [completionError, setCompletionError] = useState('');
  const [completionRetryKey, setCompletionRetryKey] = useState(0);
  const [isHydratingCurrentAttempt, setIsHydratingCurrentAttempt] = useState(false);

  const [history, setHistory] = useState([]);
  const [historyStatus, setHistoryStatus] = useState('idle');
  const [historyError, setHistoryError] = useState('');
  const [historyLoadingAttemptId, setHistoryLoadingAttemptId] = useState('');

  const showExamRateLimit = useCallback((data, headers, fallbackMessage) => {
    showRateLimitNotice(createRateLimitNotice(data, headers, fallbackMessage));
  }, [showRateLimitNotice]);

  const fetchExamAttempt = useCallback(async (attemptId) => {
    const response = await fetch(`/api/exams/${encodeURIComponent(attemptId)}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    const data = await response.json().catch(() => ({}));
    if (response.status === 429) {
      showExamRateLimit(data, response.headers, 'Too many requests right now. Please wait before loading that exam again.');
      throw new Error(data.message || 'Rate limited.');
    }
    if (!response.ok) {
      throw new Error(data.message || 'Failed to load that exam.');
    }

    return data.attempt || null;
  }, [showExamRateLimit, token]);

  const fetchExamHistory = useCallback(async () => {
    if (!token) {
      setHistory([]);
      setHistoryStatus('idle');
      setHistoryError('');
      return;
    }

    setHistoryStatus('loading');
    setHistoryError('');

    try {
      const response = await fetch('/api/exams/history', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await response.json().catch(() => ({}));
      if (response.status === 429) {
        showExamRateLimit(data, response.headers, 'Too many requests right now. Please wait before loading exam history again.');
        return;
      }
      if (!response.ok) {
        throw new Error(data.message || 'Failed to load previous exams.');
      }

      setHistory(Array.isArray(data.history) ? data.history : []);
      setHistoryStatus('ready');
    } catch (error) {
      setHistory([]);
      setHistoryStatus('error');
      setHistoryError(error.message || 'Failed to load previous exams.');
    }
  }, [showExamRateLimit, token]);

  useEffect(() => {
    let mounted = true;

    const loadChapters = async () => {
      setChaptersStatus('loading');
      setChaptersError('');

      try {
        const response = await fetch('/api/chapters');
        const data = await response.json().catch(() => ({}));
        if (response.status === 429) {
          showExamRateLimit(data, response.headers, 'Too many requests right now. Please wait before loading chapters again.');
          return;
        }
        if (!response.ok) {
          throw new Error(data.message || 'Failed to load chapters.');
        }

        if (!mounted) {
          return;
        }

        const items = Array.isArray(data.chapters) ? data.chapters : [];
        const mapped = items
          .map((chapter) => chapter.chapter_name_bn || chapter.chapter_name || '')
          .filter(Boolean);

        setChapters(mapped);
        setChaptersStatus('ready');
      } catch (error) {
        if (!mounted) {
          return;
        }

        setChaptersError(error.message || 'Failed to load chapters.');
        setChaptersStatus('error');
      }
    };

    loadChapters();

    return () => {
      mounted = false;
    };
  }, [showExamRateLimit]);

  useEffect(() => {
    fetchExamHistory();
  }, [fetchExamHistory]);

  useEffect(() => {
    if (!preselectedChapter) {
      return;
    }

    setSelectedChapters((prev) => (
      prev.includes(preselectedChapter) ? prev : [preselectedChapter, ...prev]
    ));
  }, [preselectedChapter]);

  const fetchTopicsForChapter = useCallback(async (chapterTitle) => {
    setTopicStatusByChapter((prev) => ({ ...prev, [chapterTitle]: 'loading' }));
    setTopicErrorsByChapter((prev) => ({ ...prev, [chapterTitle]: '' }));

    try {
      const response = await fetch(`/api/chapters/${encodeURIComponent(chapterTitle)}/lessons`);
      const data = await response.json().catch(() => ({}));
      if (response.status === 429) {
        showExamRateLimit(data, response.headers, 'Too many requests right now. Please wait before loading topics again.');
        return;
      }
      if (!response.ok) {
        throw new Error(data.message || 'Failed to load topics.');
      }

      const topics = Array.isArray(data.lessons) ? data.lessons : [];
      setTopicsByChapter((prev) => ({ ...prev, [chapterTitle]: topics }));
      setTopicStatusByChapter((prev) => ({ ...prev, [chapterTitle]: 'ready' }));
      setSelectedTopicsByChapter((prev) => ({
        ...prev,
        [chapterTitle]: Array.isArray(prev[chapterTitle])
          ? topics.filter((topicName) => prev[chapterTitle].includes(topicName))
          : [],
      }));
    } catch (error) {
      setTopicStatusByChapter((prev) => ({ ...prev, [chapterTitle]: 'error' }));
      setTopicErrorsByChapter((prev) => ({
        ...prev,
        [chapterTitle]: error.message || 'Failed to load topics.',
      }));
    }
  }, [showExamRateLimit]);

  useEffect(() => {
    selectedChapters.forEach((chapterTitle) => {
      if (topicsByChapter[chapterTitle]) {
        return;
      }

      if (topicStatusByChapter[chapterTitle] === 'loading') {
        return;
      }

      fetchTopicsForChapter(chapterTitle);
    });
  }, [fetchTopicsForChapter, selectedChapters, topicStatusByChapter, topicsByChapter]);

  const selections = useMemo(() => {
    return selectedChapters
      .map((chapterTitle) => ({
        chapterName: chapterTitle,
        topicNames: selectedTopicsByChapter[chapterTitle] || [],
      }))
      .filter((selection) => selection.topicNames.length > 0);
  }, [selectedChapters, selectedTopicsByChapter]);

  const totalSelectedTopics = useMemo(() => (
    selectedChapters.reduce(
      (count, chapterTitle) => count + (selectedTopicsByChapter[chapterTitle]?.length || 0),
      0,
    )
  ), [selectedChapters, selectedTopicsByChapter]);
  const recommendedSelectedCount = useMemo(() => {
    if (!recommendedExam) {
      return 0;
    }

    const selectedTopics = selectedTopicsByChapter[recommendedExam.chapterName] || [];
    return recommendedExam.lessonNames.filter((lessonName) => selectedTopics.includes(lessonName)).length;
  }, [recommendedExam, selectedTopicsByChapter]);

  const parsedCustomQuestionCount = Number(customQuestionCount);
  const isCustomQuestionCountValid = Number.isInteger(parsedCustomQuestionCount)
    && parsedCustomQuestionCount >= MIN_QUESTION_COUNT
    && parsedCustomQuestionCount <= MAX_QUESTION_COUNT;
  const resolvedQuestionCount = questionCountMode === 'custom'
    ? (isCustomQuestionCountValid ? parsedCustomQuestionCount : null)
    : questionCount;

  const answeredCount = activeAttempt ? Object.keys(activeAttempt.answers).length : 0;
  const hasFinishedActiveAttempt = Boolean(activeAttempt && answeredCount === activeAttempt.questions.length);

  const localCompletedAttempt = useMemo(() => {
    if (!hasFinishedActiveAttempt || !activeAttempt) {
      return null;
    }

    const percentage = activeAttempt.questions.length
      ? Math.round((activeAttempt.score / activeAttempt.questions.length) * 100)
      : 0;
    const scoreComment = getScoreComment(percentage);
    const wrongQuestions = buildWrongQuestions(activeAttempt.questions, activeAttempt.answers);

    return {
      id: 'local-completed-attempt',
      title: formatAttemptTitle(getAttemptChapterNames(activeAttempt.selections)),
      chapterNames: getAttemptChapterNames(activeAttempt.selections),
      selections: activeAttempt.selections,
      questionCount: activeAttempt.questionCount,
      questions: activeAttempt.questions,
      answers: activeAttempt.answers,
      score: activeAttempt.score,
      percentage,
      scoreComment,
      wrongQuestions,
      aiSummary: null,
      createdAt: new Date().toISOString(),
    };
  }, [activeAttempt, hasFinishedActiveAttempt]);

  const displayedAttempt = openedHistoryAttempt || currentCompletedAttempt || localCompletedAttempt;
  const isAttemptView = Boolean(activeAttempt && !hasFinishedActiveAttempt);
  const isResultView = Boolean(displayedAttempt);
  const historyInteractionDisabled = Boolean(activeAttempt && !hasFinishedActiveAttempt) || completionStatus === 'saving';

  useEffect(() => {
    if (!isResultView) {
      return;
    }

    const scrollTarget = resultSummaryRef.current;
    if (scrollTarget) {
      scrollTarget.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [isResultView, displayedAttempt?.id, completionStatus]);

  useEffect(() => {
    if (!token || !activeAttempt || !hasFinishedActiveAttempt || completionStatus === 'saving') {
      return undefined;
    }

    const controller = new AbortController();

    const completeExam = async () => {
      setCompletionStatus('saving');
      setCompletionError('');
      setIsHydratingCurrentAttempt(false);

      try {
        const response = await fetch('/api/exams/complete', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            selections: activeAttempt.selections,
            questionCount: activeAttempt.questionCount,
            questions: activeAttempt.questions,
            answers: activeAttempt.answers,
          }),
          signal: controller.signal,
        });

        const data = await response.json().catch(() => ({}));
        if (response.status === 429) {
          showExamRateLimit(data, response.headers, 'Too many submissions right now. Please wait before saving this exam again.');
          return;
        }
        if (!response.ok) {
          throw new Error(data.message || 'Failed to save your exam result.');
        }

        const savedAttempt = data.attempt || null;
        setCurrentCompletedAttempt(savedAttempt);
        setCompletionStatus('saved');
        setActiveAttempt(null);
        fetchExamHistory().catch(() => {});

        if (savedAttempt?.id && !savedAttempt.aiSummary) {
          const savedAttemptId = savedAttempt.id;
          setIsHydratingCurrentAttempt(true);
          fetchExamAttempt(savedAttemptId)
            .then((detailedAttempt) => {
              if (!detailedAttempt) {
                return;
              }

              setCurrentCompletedAttempt((prev) => (
                prev?.id === savedAttemptId ? detailedAttempt : prev
              ));
            })
            .catch(() => {})
            .finally(() => {
              setIsHydratingCurrentAttempt(false);
            });
        }
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }

        setCompletionStatus('error');
        setCompletionError(error.message || 'Failed to save your exam result.');
        setIsHydratingCurrentAttempt(false);
      }
    };

    completeExam();

    return () => {
      controller.abort();
    };
  }, [activeAttempt, completionRetryKey, fetchExamAttempt, fetchExamHistory, hasFinishedActiveAttempt, showExamRateLimit, token]);

  const handleChapterToggle = (chapterTitle) => {
    setBuilderError('');

    if (selectedChapters.includes(chapterTitle)) {
      setSelectedChapters((prev) => prev.filter((title) => title !== chapterTitle));
      setSelectedTopicsByChapter((prev) => {
        const next = { ...prev };
        delete next[chapterTitle];
        return next;
      });
      setTopicSearchByChapter((prev) => {
        const next = { ...prev };
        delete next[chapterTitle];
        return next;
      });
      return;
    }

    setSelectedChapters((prev) => [...prev, chapterTitle]);
  };

  const handleTopicToggle = (chapterTitle, topicName) => {
    setBuilderError('');

    setSelectedTopicsByChapter((prev) => {
      const current = Array.isArray(prev[chapterTitle]) ? prev[chapterTitle] : [];
      const nextTopicNames = current.includes(topicName)
        ? current.filter((name) => name !== topicName)
        : [...current, topicName];
      const orderedTopics = (topicsByChapter[chapterTitle] || []).filter((name) => nextTopicNames.includes(name));

      return {
        ...prev,
        [chapterTitle]: orderedTopics,
      };
    });
  };

  const handleSelectAllTopics = (chapterTitle) => {
    setBuilderError('');
    setSelectedTopicsByChapter((prev) => ({
      ...prev,
      [chapterTitle]: topicsByChapter[chapterTitle] || [],
    }));
  };

  const handleClearTopics = (chapterTitle) => {
    setBuilderError('');
    setSelectedTopicsByChapter((prev) => ({
      ...prev,
      [chapterTitle]: [],
    }));
  };

  const handleApplyRecommendedTopics = () => {
    if (!recommendedExam) {
      return;
    }

    setBuilderError('');
    setSelectedChapters((prev) => (
      prev.includes(recommendedExam.chapterName) ? prev : [recommendedExam.chapterName, ...prev]
    ));
    setSelectedTopicsByChapter((prev) => ({
      ...prev,
      [recommendedExam.chapterName]: recommendedExam.lessonNames,
    }));
  };

  const handleGenerateExam = async () => {
    if (!selections.length || !token) {
      setBuilderError('Select at least one topic before generating an exam.');
      return;
    }

    if (!resolvedQuestionCount) {
      setBuilderError(`Enter a custom question count between ${MIN_QUESTION_COUNT} and ${MAX_QUESTION_COUNT}.`);
      return;
    }

    setBuilderError('');
    setCompletionStatus('idle');
    setCompletionError('');
    setCompletionRetryKey(0);
    setIsHydratingCurrentAttempt(false);
    setCurrentCompletedAttempt(null);
    setOpenedHistoryAttempt(null);
    setIsGenerating(true);

    try {
      const response = await fetch('/api/exams/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          selections,
          questionCount: resolvedQuestionCount,
        }),
      });

      const data = await response.json().catch(() => ({}));
      if (response.status === 429) {
        showExamRateLimit(data, response.headers, 'Too many exam requests right now. Please wait before generating another one.');
        return;
      }
      if (!response.ok) {
        throw new Error(data.message || 'Failed to generate exam.');
      }

      const questions = Array.isArray(data.questions) ? data.questions : [];
      if (!questions.length) {
        throw new Error('The exam service returned no questions.');
      }

      setActiveAttempt({
        selections,
        questionCount: resolvedQuestionCount,
        questions: questions.map((question, index) => ({
          id: question.id || `${index + 1}`,
          chapterName: question.chapterName || '',
          topicName: question.topicName || '',
          question: question.question || '',
          options: Array.isArray(question.options) ? question.options : [],
          correctOptionIndex: Number(question.correctOptionIndex),
        })),
        answers: {},
        score: 0,
      });
    } catch (error) {
      setBuilderError(error.message || 'Failed to generate exam.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleAnswerSelect = (questionId, optionIndex) => {
    setActiveAttempt((prev) => {
      if (!prev || prev.answers[questionId] !== undefined) {
        return prev;
      }

      const question = prev.questions.find((entry) => entry.id === questionId);
      if (!question) {
        return prev;
      }

      return {
        ...prev,
        answers: {
          ...prev.answers,
          [questionId]: optionIndex,
        },
        score: prev.score + (question.correctOptionIndex === optionIndex ? 1 : 0),
      };
    });
  };

  const handleCreateAnotherExam = () => {
    setActiveAttempt(null);
    setCurrentCompletedAttempt(null);
    setOpenedHistoryAttempt(null);
    setCompletionStatus('idle');
    setCompletionError('');
    setCompletionRetryKey(0);
    setIsHydratingCurrentAttempt(false);
    setBuilderError('');
  };

  const handleRetryCompletion = () => {
    if (!hasFinishedActiveAttempt) {
      return;
    }

    setCompletionError('');
    setCompletionStatus('idle');
    setCompletionRetryKey((prev) => prev + 1);
  };

  const handleHistoryOpen = useCallback(async (attemptId) => {
    if (!attemptId || !token || historyInteractionDisabled) {
      return;
    }

    setHistoryLoadingAttemptId(attemptId);
    setHistoryError('');

    try {
      const attempt = await fetchExamAttempt(attemptId);
      setOpenedHistoryAttempt(attempt);
    } catch (error) {
      setHistoryError(error.message || 'Failed to load that exam.');
    } finally {
      setHistoryLoadingAttemptId('');
    }
  }, [fetchExamAttempt, historyInteractionDisabled, token]);

  const renderBuilder = () => (
    <>
      <div className="row g-4 mb-4">
        <div className="col-lg-8">
          <div className="bg-white rounded-2xl p-4 p-lg-5 shadow-sm border border-gray-100 h-100">
            <div className="d-flex flex-column flex-lg-row justify-content-between gap-4">
              <div>
                <div className="small fw-semibold text-secondary text-uppercase mb-2">Exam Builder</div>
                <h1 className="fw-bold text-primary mb-3">Create an AI-powered MCQ exam</h1>
                <p className="text-secondary mb-0">
                  Pick one or more chapters, choose the exact topics you want, and Photon will generate
                  a focused multiple-choice exam for you.
                </p>
              </div>
              <div className="bg-orange-50 border border-orange-100 rounded-2xl p-3 p-lg-4" style={{ minWidth: '16rem' }}>
                <div className="small fw-semibold text-secondary text-uppercase mb-2">Selection Summary</div>
                <div className="fs-4 fw-bold text-primary">{selectedChapters.length} chapter(s)</div>
                <div className="text-secondary mb-3">{totalSelectedTopics} topic(s) selected</div>
                {preselectedChapter && (
                  <div className="small fw-medium text-primary">
                    {/* Prefilled from chapter: <span className={getBanglaClass(preselectedChapter)}>{preselectedChapter}</span> */}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="col-lg-4">
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 h-100 d-flex flex-column">
            <div className="small fw-semibold text-secondary text-uppercase mb-2">Question Count</div>
            <div className="d-flex flex-wrap gap-2 mb-4">
              {QUESTION_COUNT_OPTIONS.map((count) => (
                <button
                  key={count}
                  type="button"
                  onClick={() => {
                    setQuestionCountMode('preset');
                    setQuestionCount(count);
                    setBuilderError('');
                  }}
                  className={`px-3 py-2 rounded-pill border-0 small fw-semibold ${
                    questionCountMode === 'preset' && questionCount === count
                      ? 'bg-primary text-white shadow-sm'
                      : 'bg-gray-50 text-secondary'
                  }`}
                >
                  {count}
                </button>
              ))}
              <button
                type="button"
                onClick={() => {
                  setQuestionCountMode('custom');
                  setCustomQuestionCount((prev) => prev || String(questionCount));
                  setBuilderError('');
                }}
                className={`px-3 py-2 rounded-pill border-0 small fw-semibold ${
                  questionCountMode === 'custom'
                    ? 'bg-primary text-white shadow-sm'
                    : 'bg-gray-50 text-secondary'
                }`}
              >
                Custom
              </button>
            </div>

            {questionCountMode === 'custom' && (
              <div className="mb-4">
                <label className="form-label small fw-semibold text-secondary text-uppercase">
                  Custom Question Count
                </label>
                <input
                  type="number"
                  min={MIN_QUESTION_COUNT}
                  max={MAX_QUESTION_COUNT}
                  step="1"
                  value={customQuestionCount}
                  onChange={(event) => {
                    setCustomQuestionCount(event.target.value);
                    setBuilderError('');
                  }}
                  placeholder={`Enter a number from ${MIN_QUESTION_COUNT} to ${MAX_QUESTION_COUNT}`}
                  className="form-control border-gray-200 rounded-3 focus-ring-orange"
                />
                <div className="small text-secondary mt-2">
                  Choose any whole number from {MIN_QUESTION_COUNT} to {MAX_QUESTION_COUNT}.
                </div>
              </div>
            )}

            <div className="small fw-semibold text-secondary text-uppercase mb-2">Ready to generate</div>
            <div className="text-secondary mb-4">
              Photon will create exactly <span className="fw-semibold text-primary">{resolvedQuestionCount || '...'}</span> MCQ
              questions from your selected topics.
            </div>

            {builderError && (
              <div className="bg-red-50 border border-red-100 text-red-700 rounded-3 p-3 small mb-3">
                {builderError}
              </div>
            )}

            <button
              type="button"
              onClick={handleGenerateExam}
              disabled={!selections.length || isGenerating || !resolvedQuestionCount}
              className={`mt-auto w-100 py-3 rounded-xl fw-semibold border-0 ${
                !selections.length || isGenerating || !resolvedQuestionCount
                  ? 'bg-gray-100 text-secondary'
                  : 'custom-gradient-btn text-white'
              }`}
            >
              {isGenerating ? 'Generating Exam…' : 'Generate Exam'}
            </button>
          </div>
        </div>
      </div>

      {recommendedExam && (
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 mb-4">
          <div className="d-flex flex-column flex-lg-row justify-content-between gap-3 align-items-lg-center">
            <div>
              <div className="small fw-semibold text-secondary text-uppercase mb-2">Recommended from your weak areas</div>
              <h2 className={`fs-4 fw-bold text-primary mb-1 ${getBanglaClass(recommendedExam.chapterName)}`}>
                {recommendedExam.chapterName}
              </h2>
              <div className="text-secondary">
                Photon noticed these lessons need more practice before your next mixed exam.
              </div>
            </div>

            <button
              type="button"
              onClick={handleApplyRecommendedTopics}
              className="px-4 py-2 rounded-pill border-0 custom-gradient-btn text-white fw-semibold"
            >
              Select recommended topics
            </button>
          </div>

          <div className="d-flex flex-wrap gap-2 mt-3">
            {recommendedExam.lessonNames.map((lessonName) => {
              const isSelected = (selectedTopicsByChapter[recommendedExam.chapterName] || []).includes(lessonName);
              return (
                <span
                  key={`${recommendedExam.chapterName}-${lessonName}`}
                  className={`px-3 py-2 rounded-pill small fw-semibold border font-bangla ${
                    isSelected
                      ? 'bg-primary text-white border-0'
                      : 'bg-orange-50 text-primary border-orange-100'
                  }`}
                >
                  {lessonName}
                </span>
              );
            })}
          </div>

          <div className="small text-secondary mt-3">
            {recommendedSelectedCount} / {recommendedExam.lessonNames.length} recommended topic(s) selected
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 mb-4">
        <div className="d-flex flex-column flex-lg-row justify-content-between align-items-lg-center gap-3 mb-4">
          <div>
            <div className="small fw-semibold text-secondary text-uppercase mb-2">Step 1</div>
            <h2 className="fs-4 fw-bold text-primary mb-1">Choose chapters</h2>
            <div className="text-secondary">You can select one chapter or combine multiple chapters in the same exam.</div>
          </div>
          {chaptersStatus === 'ready' && (
            <div className="small fw-medium text-secondary">{chapters.length} chapters available</div>
          )}
        </div>

        {chaptersError && (
          <div className="bg-red-50 border border-red-100 text-red-700 rounded-3 p-3 small mb-3">
            {chaptersError}
          </div>
        )}

        {chaptersStatus === 'loading' && <div className="text-secondary">Loading chapters…</div>}

        {chaptersStatus !== 'loading' && !chaptersError && (
          <div className="d-flex flex-wrap gap-3">
            {chapters.map((chapterTitle) => {
              const isSelected = selectedChapters.includes(chapterTitle);
              return (
                <button
                  key={chapterTitle}
                  type="button"
                  onClick={() => handleChapterToggle(chapterTitle)}
                  className={`px-4 py-3 rounded-4 border text-start ${
                    isSelected
                      ? 'bg-primary text-white border-0 shadow-sm'
                      : 'bg-orange-50 border-orange-100 text-primary'
                  }`}
                >
                  <div className={`fw-semibold ${getBanglaClass(chapterTitle)}`}>{chapterTitle}</div>
                  <div className={`small ${isSelected ? 'text-white-50' : 'text-secondary'}`}>
                    {isSelected ? 'Selected for exam' : 'Tap to include'}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="d-flex flex-column gap-4">
        {selectedChapters.length === 0 && (
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 text-secondary">
            Select a chapter to start choosing topics.
          </div>
        )}

        {selectedChapters.map((chapterTitle) => {
          const searchTerm = topicSearchByChapter[chapterTitle] || '';
          const allTopics = topicsByChapter[chapterTitle] || [];
          const filteredTopics = allTopics.filter((topicName) => (
            topicName.toLowerCase().includes(searchTerm.trim().toLowerCase())
          ));
          const selectedTopics = selectedTopicsByChapter[chapterTitle] || [];
          const status = topicStatusByChapter[chapterTitle] || 'idle';
          const error = topicErrorsByChapter[chapterTitle] || '';

          return (
            <div key={chapterTitle} className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
              <div className="d-flex flex-column flex-lg-row justify-content-between gap-3 mb-4">
                <div>
                  <div className="small fw-semibold text-secondary text-uppercase mb-2">Step 2</div>
                  <h3 className={`fs-4 fw-bold text-primary mb-1 ${getBanglaClass(chapterTitle)}`}>{chapterTitle}</h3>
                  <div className="text-secondary">
                    Select all topics or search and choose them manually.
                  </div>
                </div>
                <div className="d-flex flex-wrap gap-2 align-self-start">
                  <button
                    type="button"
                    onClick={() => handleSelectAllTopics(chapterTitle)}
                    disabled={!allTopics.length}
                    className="px-3 py-2 rounded-pill border border-gray-200 bg-white text-primary small fw-semibold"
                  >
                    Select all
                  </button>
                  <button
                    type="button"
                    onClick={() => handleClearTopics(chapterTitle)}
                    disabled={!selectedTopics.length}
                    className="px-3 py-2 rounded-pill border border-gray-200 bg-white text-secondary small fw-semibold"
                  >
                    Clear
                  </button>
                </div>
              </div>

              <div className="row g-4 align-items-start">
                <div className="col-lg-5">
                  <label className="form-label small fw-semibold text-secondary text-uppercase">Search topic</label>
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(event) => setTopicSearchByChapter((prev) => ({
                      ...prev,
                      [chapterTitle]: event.target.value,
                    }))}
                    placeholder="Search by topic name"
                    className="form-control border-gray-200 rounded-3 focus-ring-orange"
                  />
                  <div className="small text-secondary mt-2">
                    {selectedTopics.length} / {allTopics.length} topic(s) selected
                  </div>
                </div>

                <div className="col-lg-7">
                  <div className="small fw-semibold text-secondary text-uppercase mb-2">Topics</div>
                  <div
                    className="border border-gray-200 rounded-4 bg-orange-50 p-2 overflow-y-auto custom-scrollbar"
                    style={{ maxHeight: '20rem' }}
                  >
                    {status === 'loading' && <div className="p-3 text-secondary">Loading topics…</div>}
                    {status === 'error' && <div className="p-3 text-danger">{error}</div>}
                    {status === 'ready' && filteredTopics.length === 0 && (
                      <div className="p-3 text-secondary">
                        {searchTerm ? 'No topics matched your search.' : 'No topics available yet.'}
                      </div>
                    )}

                    {status === 'ready' && filteredTopics.map((topicName) => {
                      const isSelected = selectedTopics.includes(topicName);
                      return (
                        <label
                          key={topicName}
                          className={`d-flex align-items-center gap-3 p-3 rounded-3 mb-2 ${
                            isSelected ? 'bg-white shadow-sm' : ''
                          }`}
                          style={{ cursor: 'pointer' }}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleTopicToggle(chapterTitle, topicName)}
                          />
                          <span className={`${getBanglaClass(topicName)} ${isSelected ? 'fw-semibold text-primary' : 'text-secondary'}`}>
                            {topicName}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );

  const renderAttemptView = () => (
    <>
      <div className="bg-white rounded-2xl p-4 p-lg-5 shadow-sm border border-gray-100 mb-4">
        <div className="d-flex flex-column flex-lg-row justify-content-between gap-4">
          <div>
            <div className="small fw-semibold text-secondary text-uppercase mb-2">Exam In Progress</div>
            <h1 className="fw-bold text-primary mb-2">Answer each MCQ once</h1>
            <div className="text-secondary">
              Your answers are being scored silently. The result will appear automatically after the last question.
            </div>
          </div>
          <div className="bg-orange-50 border border-orange-100 rounded-2xl p-3 p-lg-4">
            <div className="small fw-semibold text-secondary text-uppercase mb-2">Progress</div>
            <div className="fs-4 fw-bold text-primary">{answeredCount} / {activeAttempt.questions.length}</div>
            <div className="text-secondary">questions answered</div>
          </div>
        </div>
      </div>

      <div className="d-flex flex-column gap-4">
        {activeAttempt.questions.map((question, questionIndex) => {
          const selectedOptionIndex = activeAttempt.answers[question.id];
          const isLocked = selectedOptionIndex !== undefined;

          return (
            <div key={question.id} className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
              <div className="d-flex flex-column flex-lg-row justify-content-between gap-3 mb-4">
                <div>
                  <div className="small fw-semibold text-secondary text-uppercase mb-2">
                    Question {questionIndex + 1}
                  </div>
                  <div className="fw-bold text-primary fs-5 mb-2">
                    <ExamRichText text={question.question} />
                  </div>
                  <div className="d-flex flex-wrap gap-2">
                    <span className={`px-3 py-1 rounded-pill bg-orange-50 border border-orange-100 text-primary small fw-medium ${getBanglaClass(question.chapterName)}`}>
                      {question.chapterName}
                    </span>
                    <span className={`px-3 py-1 rounded-pill bg-gray-50 text-secondary small fw-medium ${getBanglaClass(question.topicName)}`}>
                      {question.topicName}
                    </span>
                  </div>
                </div>
                <div className={`small fw-semibold ${isLocked ? 'text-primary' : 'text-secondary'}`}>
                  {isLocked ? 'Answer locked' : 'Choose one option'}
                </div>
              </div>

              <div className="d-grid gap-3">
                {question.options.map((optionText, optionIndex) => {
                  const isSelected = selectedOptionIndex === optionIndex;
                  return (
                    <button
                      key={`${question.id}-${optionIndex}`}
                      type="button"
                      onClick={() => handleAnswerSelect(question.id, optionIndex)}
                      disabled={isLocked}
                      className={`w-100 text-start p-3 rounded-4 border ${
                        isSelected
                          ? 'bg-primary text-white border-0 shadow-sm'
                          : isLocked
                          ? 'bg-gray-50 text-secondary border-gray-200'
                          : 'bg-white text-primary border-gray-200'
                      }`}
                    >
                      <span className="fw-bold me-2">{OPTION_LABELS[optionIndex]}.</span>
                      <ExamRichText text={optionText} inline />
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );

  const renderAiSummary = (attemptData) => {
    const fallbackSummary = completionStatus === 'error' && attemptData?.id === 'local-completed-attempt'
      ? buildFallbackSummary(attemptData.scoreComment, attemptData.wrongQuestions || [])
      : null;
    const summary = attemptData?.aiSummary || fallbackSummary;
    const isLiveLocalPreview = Boolean(
      attemptData
      && !openedHistoryAttempt
      && attemptData.id === 'local-completed-attempt',
    );
    const isLiveSavedAttempt = Boolean(
      attemptData
      && !openedHistoryAttempt
      && currentCompletedAttempt
      && attemptData.id === currentCompletedAttempt.id,
    );
    const isPendingSummary = Boolean(
      attemptData
      && !summary
      && !completionError
      && (
        (completionStatus === 'saving' && isLiveLocalPreview)
        || (isHydratingCurrentAttempt && isLiveSavedAttempt)
      ),
    );

    if (isPendingSummary) {
      return (
        <div className="bg-orange-50 border border-orange-100 rounded-4 p-4">
          <div className="small fw-semibold text-secondary text-uppercase mb-2">AI Performance Summary</div>
          <div className="fw-semibold text-primary mb-2">Analyzing your performance…</div>
          <div className="text-secondary">
            Photon is reviewing the questions you got wrong and preparing topic-wise suggestions for revision.
          </div>
        </div>
      );
    }
    if (!summary) {
      return null;
    }

    return (
      <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
        <div className="small fw-semibold text-secondary text-uppercase mb-2">AI Performance Summary</div>
        <h2 className={`fs-4 fw-bold text-primary mb-2 ${getBanglaClass(summary.headline)}`}>{summary.headline}</h2>
        <p className={`text-secondary mb-4 ${getBanglaClass(summary.overallComment)}`}>{summary.overallComment}</p>

        <div className="row g-4">
          <div className="col-lg-6">
            <div className="bg-orange-50 border border-orange-100 rounded-4 p-3 h-100">
              <div className="small fw-semibold text-secondary text-uppercase mb-2">Weaknesses</div>
              {(summary.weaknesses || []).length > 0 ? (
                <div className="d-flex flex-column gap-2">
                  {summary.weaknesses.map((weakness, index) => (
                    <div key={`${summary.headline}-weakness-${index}`} className={`text-primary ${getBanglaClass(weakness)}`}>
                      {weakness}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-secondary">No weakness summary was provided.</div>
              )}
            </div>
          </div>

          <div className="col-lg-6">
            <div className="bg-gray-50 rounded-4 p-3 h-100">
              <div className="small fw-semibold text-secondary text-uppercase mb-2">Study Advice</div>
              {(summary.studyAdvice || []).length > 0 ? (
                <div className="d-flex flex-column gap-2">
                  {summary.studyAdvice.map((advice, index) => (
                    <div key={`${summary.headline}-advice-${index}`} className={`text-primary ${getBanglaClass(advice)}`}>
                      {advice}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-secondary">No study advice was provided.</div>
              )}
            </div>
          </div>
        </div>

        <div className="mt-4">
          <div className="small fw-semibold text-secondary text-uppercase mb-2">Topics To Revisit</div>
          {(summary.recommendedTopics || []).length > 0 ? (
            <div className="d-flex flex-column gap-3">
              {summary.recommendedTopics.map((topic, index) => (
                <div key={`${topic.chapterName}-${topic.topicName}-${index}`} className="border border-gray-200 rounded-4 p-3">
                  <div className="d-flex flex-wrap gap-2 mb-2">
                    <span className={`px-3 py-1 rounded-pill bg-orange-50 border border-orange-100 text-primary small fw-medium ${getBanglaClass(topic.chapterName)}`}>
                      {topic.chapterName}
                    </span>
                    <span className={`px-3 py-1 rounded-pill bg-gray-50 text-secondary small fw-medium ${getBanglaClass(topic.topicName)}`}>
                      {topic.topicName}
                    </span>
                  </div>
                  <div className={`text-secondary ${getBanglaClass(topic.reason)}`}>{topic.reason}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-secondary">No extra revision topics were recommended for this attempt.</div>
          )}
        </div>
      </div>
    );
  };

  const renderResultsView = () => {
    const attemptData = displayedAttempt;
    if (!attemptData) {
      return null;
    }

    const isLocalAttempt = attemptData.id === 'local-completed-attempt';

    return (
      <>
        <div ref={resultSummaryRef} className="row g-4 mb-4">
          <div className="col-lg-8">
            <div className="bg-white rounded-2xl p-4 p-lg-5 shadow-sm border border-gray-100 h-100">
              <div className="small fw-semibold text-secondary text-uppercase mb-2">Exam Completed</div>
              <h1 className="fw-bold text-primary mb-3">Your score is {attemptData.score} / {attemptData.questions.length}</h1>
              <p className="text-secondary mb-3">
                {completionStatus === 'saving' && attemptData.id === 'local-completed-attempt'
                  ? 'You answered all questions. Photon is now saving your result and preparing a weakness summary.'
                  : 'You answered all questions. Here is your final score, topic-wise feedback, and a review of each answer.'}
              </p>

              <div className="d-flex flex-wrap gap-3 mb-4">
                <span className="px-3 py-2 rounded-pill bg-orange-50 border border-orange-100 text-primary fw-semibold">
                  {attemptData.percentage}% score
                </span>
                <span className="px-3 py-2 rounded-pill bg-gray-50 text-secondary fw-semibold">
                  {attemptData.scoreComment}
                </span>
                <span className="px-3 py-2 rounded-pill bg-gray-50 text-secondary fw-semibold">
                  {formatAttemptDate(attemptData.createdAt)}
                </span>
              </div>

              {completionError && isLocalAttempt && (
                <div className="bg-red-50 border border-red-100 text-red-700 rounded-4 p-3 mb-3">
                  <div className="fw-semibold mb-1">Could not save this attempt yet</div>
                  <div className="small">{completionError}</div>
                </div>
              )}

              <div className="d-flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={handleCreateAnotherExam}
                  className="custom-gradient-btn text-white px-4 py-3 rounded-xl fw-semibold"
                >
                  Create Another Exam
                </button>

                {completionStatus === 'error' && hasFinishedActiveAttempt && isLocalAttempt && (
                  <button
                    type="button"
                    onClick={handleRetryCompletion}
                    className="px-4 py-3 rounded-xl fw-semibold border border-gray-200 bg-white text-primary"
                  >
                    Retry Save & Analysis
                  </button>
                )}
              </div>
            </div>
          </div>

          <div className="col-lg-4">
            <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 h-100">
              <div className="small fw-semibold text-secondary text-uppercase mb-3">Result Summary</div>
              <div className="d-flex flex-column gap-3">
                <div className="bg-orange-50 border border-orange-100 rounded-4 p-3">
                  <div className="small text-secondary">Percentage</div>
                  <div className="fs-3 fw-bold text-primary">{attemptData.percentage}%</div>
                </div>
                <div className="bg-green-100 rounded-4 p-3">
                  <div className="small text-secondary">Correct</div>
                  <div className="fs-4 fw-bold text-green-700">{attemptData.score}</div>
                </div>
                <div className="bg-red-50 border border-red-100 rounded-4 p-3">
                  <div className="small text-secondary">Wrong</div>
                  <div className="fs-4 fw-bold text-red-700">{attemptData.questions.length - attemptData.score}</div>
                </div>
                <div className="bg-gray-50 rounded-4 p-3">
                  <div className="small text-secondary">Comment</div>
                  <div className={`fs-5 fw-bold text-primary ${getBanglaClass(attemptData.scoreComment)}`}>
                    {attemptData.scoreComment}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="mb-4">
          {renderAiSummary(attemptData)}
        </div>

        <div className="d-flex flex-column gap-4">
          {attemptData.questions.map((question, questionIndex) => {
            const selectedOptionIndex = attemptData.answers?.[question.id];

            return (
              <div key={question.id} className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
                <div className="mb-4">
                  <div className="small fw-semibold text-secondary text-uppercase mb-2">
                    Review {questionIndex + 1}
                  </div>
                  <div className="fw-bold text-primary fs-5 mb-2">
                    <ExamRichText text={question.question} />
                  </div>
                  <div className="d-flex flex-wrap gap-2">
                    <span className={`px-3 py-1 rounded-pill bg-orange-50 border border-orange-100 text-primary small fw-medium ${getBanglaClass(question.chapterName)}`}>
                      {question.chapterName}
                    </span>
                    <span className={`px-3 py-1 rounded-pill bg-gray-50 text-secondary small fw-medium ${getBanglaClass(question.topicName)}`}>
                      {question.topicName}
                    </span>
                  </div>
                </div>

                <div className="d-grid gap-3">
                  {question.options.map((optionText, optionIndex) => {
                    const isSelected = selectedOptionIndex === optionIndex;
                    const isCorrect = question.correctOptionIndex === optionIndex;

                    let classes = 'bg-white text-primary border-gray-200';
                    if (isCorrect) {
                      classes = 'bg-green-100 text-green-700 border-0';
                    } else if (isSelected) {
                      classes = 'bg-red-50 text-red-700 border-red-100';
                    }

                    return (
                      <div
                        key={`${question.id}-result-${optionIndex}`}
                        className={`w-100 text-start p-3 rounded-4 border ${classes}`}
                      >
                        <div className="d-flex flex-column flex-lg-row justify-content-between gap-2">
                          <div>
                            <span className="fw-bold me-2">{OPTION_LABELS[optionIndex]}.</span>
                            <ExamRichText text={optionText} inline />
                          </div>
                          <div className="small fw-semibold">
                            {isCorrect && 'Correct answer'}
                            {!isCorrect && isSelected && 'Your answer'}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </>
    );
  };

  const renderHistory = () => (
    <div className="bg-white rounded-2xl p-4 p-lg-5 shadow-sm border border-gray-100 mt-4">
      <div className="d-flex flex-column flex-lg-row justify-content-between align-items-lg-center gap-3 mb-4">
        <div>
          <div className="small fw-semibold text-secondary text-uppercase mb-2">Previous Exams</div>
          <h2 className="fs-4 fw-bold text-primary mb-1">Review earlier attempts</h2>
          <div className="text-secondary">
            Open any saved exam to revisit your score, wrong answers, and the AI study suggestions.
          </div>
        </div>
        {historyInteractionDisabled && (
          <div className="small fw-medium text-secondary">
            Finish the current exam before opening previous attempts.
          </div>
        )}
      </div>

      {historyError && (
        <div className="bg-red-50 border border-red-100 text-red-700 rounded-3 p-3 small mb-3">
          {historyError}
        </div>
      )}

      {historyStatus === 'loading' && <div className="text-secondary">Loading previous exams…</div>}

      {historyStatus !== 'loading' && history.length === 0 && !historyError && (
        <div className="bg-orange-50 border border-orange-100 rounded-4 p-4 text-secondary">
          No saved exams yet. Once you finish an exam, it will appear here automatically.
        </div>
      )}

      {history.length > 0 && (
        <div className="d-flex flex-column gap-3">
          {history.map((item) => {
            const isSelected = displayedAttempt?.id === item.id;
            const isLoading = historyLoadingAttemptId === item.id;
            const title = item.title || formatAttemptTitle(item.chapterNames);
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleHistoryOpen(item.id)}
                disabled={historyInteractionDisabled || isLoading}
                className={`w-100 text-start p-4 rounded-4 border ${
                  isSelected
                    ? 'bg-orange-50 border-orange-100'
                    : 'bg-white border-gray-200'
                } ${historyInteractionDisabled || isLoading ? 'cursor-not-allowed' : ''}`}
              >
                <div className="d-flex flex-column flex-lg-row justify-content-between gap-3">
                  <div>
                    <div className="small fw-semibold text-secondary text-uppercase mb-2">
                      {isLoading ? 'Opening exam…' : formatAttemptDate(item.createdAt)}
                    </div>
                    <div className={`fs-5 fw-bold text-primary mb-2 ${getBanglaClass(title)}`}>
                      {title}
                    </div>
                    <div className="fs-5 fw-bold text-primary mb-2">
                      {item.score} / {item.questionCount} correct
                    </div>
                    <div className="d-flex flex-wrap gap-2">
                      <span className="px-3 py-1 rounded-pill bg-gray-50 text-secondary small fw-semibold">
                        {item.percentage}% score
                      </span>
                      <span className="px-3 py-1 rounded-pill bg-gray-50 text-secondary small fw-semibold">
                        {item.scoreComment}
                      </span>
                      <span className="px-3 py-1 rounded-pill bg-gray-50 text-secondary small fw-semibold">
                        {item.chapterCount} chapter(s)
                      </span>
                      <span className="px-3 py-1 rounded-pill bg-gray-50 text-secondary small fw-semibold">
                        {item.topicCount} topic(s)
                      </span>
                    </div>
                  </div>

                  <div className="align-self-start">
                    <span className={`px-3 py-2 rounded-pill small fw-semibold ${
                      isSelected ? 'bg-primary text-white' : 'bg-gray-50 text-secondary'
                    }`}>
                      {isSelected ? 'Currently opened' : 'Open review'}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-background pb-5">
      <Navbar />

      <main className="container-xl px-4 px-sm-5 py-5">
        {!activeAttempt && !openedHistoryAttempt && !currentCompletedAttempt && renderBuilder()}
        {isAttemptView && renderAttemptView()}
        {isResultView && renderResultsView()}
        {renderHistory()}
      </main>
    </div>
  );
};

export default ExamPage;
