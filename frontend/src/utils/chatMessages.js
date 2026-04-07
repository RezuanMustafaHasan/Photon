const normalizeString = (value) => (typeof value === 'string' ? value.trim() : '');

export const normalizeCitation = (value, chapterFallback = '', lessonFallback = '') => {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const chapterName = normalizeString(value.chapterName ?? value.chapter_name) || chapterFallback;
  const lessonName = normalizeString(value.lessonName ?? value.lesson_name) || lessonFallback;
  const sectionLabel = normalizeString(value.sectionLabel ?? value.section_label);
  const snippet = normalizeString(value.snippet);

  if (!chapterName && !lessonName && !sectionLabel && !snippet) {
    return null;
  }

  return {
    chapterName,
    lessonName,
    sectionLabel,
    snippet,
  };
};

const citationKey = (citation) => [
  normalizeString(citation?.chapterName).toLowerCase(),
  normalizeString(citation?.lessonName).toLowerCase(),
].join('::');

export const normalizeCitations = (values, chapterFallback = '', lessonFallback = '') => {
  const seen = new Set();
  const currentLessonKey = `${normalizeString(chapterFallback).toLowerCase()}::${normalizeString(lessonFallback).toLowerCase()}`;

  return (Array.isArray(values) ? values : [])
    .map((citation) => normalizeCitation(citation, chapterFallback, lessonFallback))
    .filter(Boolean)
    .filter((citation) => {
      const key = citationKey(citation);
      if (!citation.lessonName || key === currentLessonKey || seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
};

export const normalizeAssistantPayload = (value, chapterFallback = '', lessonFallback = '') => {
  const response = normalizeString(value?.response ?? value?.content);
  const textbookAnswer = normalizeString(value?.textbookAnswer ?? value?.textbook_answer);
  const extraExplanation = normalizeString(value?.extraExplanation ?? value?.extra_explanation);
  const citations = normalizeCitations(value?.citations, chapterFallback, lessonFallback);

  return {
    text: response,
    textbookAnswer,
    extraExplanation,
    citations,
  };
};

export const createAssistantMessage = (value, options = {}) => ({
  id: options.id || crypto.randomUUID(),
  sender: 'ai',
  relatedUserText: normalizeString(options.relatedUserText ?? value?.relatedUserText),
  ...normalizeAssistantPayload(value, options.chapterName, options.lessonName),
});

export const normalizeHistoryMessage = (value, options = {}) => {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const sender = value.role === 'assistant' ? 'ai' : 'user';
  if (sender === 'ai') {
    return createAssistantMessage(value, options);
  }

  const text = normalizeString(value.content);
  if (!text) {
    return null;
  }

  return {
    id: options.id || crypto.randomUUID(),
    sender: 'user',
    text,
  };
};

export const hasStructuredAssistantContent = (value) => (
  Boolean(value?.textbookAnswer)
  || Boolean(value?.extraExplanation)
  || (Array.isArray(value?.citations) && value.citations.length > 0)
);
