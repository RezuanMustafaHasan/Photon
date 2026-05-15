export const CHAT_MODEL_OPTIONS = [
  {
    value: 'groq:openai/gpt-oss-120b',
    label: 'Groq · GPT OSS 120B',
  },
];

export const DEFAULT_CHAT_MODEL = CHAT_MODEL_OPTIONS[0].value;

export const normalizeChatModel = (value) => {
  if (CHAT_MODEL_OPTIONS.some((option) => option.value === value)) {
    return value;
  }

  if (typeof value === 'string') {
    const normalized = value.trim();
    if (/^groq:.+$/i.test(normalized)) {
      return normalized;
    }
  }

  return DEFAULT_CHAT_MODEL;
};
