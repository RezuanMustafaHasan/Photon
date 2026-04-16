export const CHAT_MODEL_OPTIONS = [
  {
    value: 'groq:openai/gpt-oss-120b',
    label: 'Groq · GPT OSS 120B',
  },
  {
    value: 'openai:gpt-4.1-mini',
    label: 'OpenAI · GPT-4.1 Mini',
  },
  {
    value: 'openai:gpt-5.4-nano',
    label: 'OpenAI · GPT-5.4 Nano',
  },
  {
    value: 'openai:gpt-4o-mini',
    label: 'OpenAI · GPT-4o Mini',
  },
];

export const DEFAULT_CHAT_MODEL = CHAT_MODEL_OPTIONS[0].value;

export const normalizeChatModel = (value) => {
  if (CHAT_MODEL_OPTIONS.some((option) => option.value === value)) {
    return value;
  }

  if (typeof value === 'string') {
    const normalized = value.trim();
    if (/^(openai|groq):.+$/i.test(normalized)) {
      return normalized;
    }
  }

  return DEFAULT_CHAT_MODEL;
};
