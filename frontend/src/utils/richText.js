const LATEX_COMMAND_PATTERN = String.raw`(?:frac|int|sum|sqrt|cdot|times|left|right|vec|hat|theta|phi|pi|alpha|beta|gamma|lambda|mu|nu|rho|sigma|omega|Delta|delta|tau|sin|cos|tan|log|ln|text|mathrm|mathbf|overrightarrow|overline|quad|qquad|pm|leq|geq|neq|approx)`;
const RAW_LATEX_COMMAND_REGEX = new RegExp(String.raw`\\${LATEX_COMMAND_PATTERN}`);
const EXPLICIT_DISPLAY_MATH_REGEX = /\$\$([\s\S]+?)\$\$/g;
const EXPLICIT_INLINE_MATH_REGEX = /\$([^\n$]+?)\$/g;
const PLAIN_FORMULA_REGEX = /(?<![$\\])((?:[A-Za-z0-9\u0370-\u03FF\u0980-\u09FF_()[\]{}\\^/.]+)(?:\s*(?:=|\+|-|\*|\/|\^|×|·)\s*(?:[A-Za-z0-9\u0370-\u03FF\u0980-\u09FF_()[\]{}\\^/.]+))+)(?=(?:\s+\\[A-Za-z]+|\s+[A-Za-z]{3,}\b|\s+[\u0980-\u09FF]{2,}\b|[.,;:!?]|।|\)|$))/gu;
const DISPLAY_MATH_REGEX = /\\\[((?:.|\n)*?)\\\]/g;
const INLINE_MATH_REGEX = /\\\((.*?)\\\)/g;
const LITERAL_NEWLINE_REGEX = /\\n(?![A-Za-z])/g;
const LITERAL_TAB_REGEX = /\\t(?![A-Za-z])/g;
const GREEK_CHARACTER_REGEX = /[αβγδΔθλμπρστωφτ]/g;
const TEXT_WITH_OPERATOR_REGEX = /\\text\{([^{}]+?)\s*([·•×])\s*([^{}]+?)\}/g;
const KNOWN_DOUBLE_BACKSLASH_REGEX = new RegExp(String.raw`\\\\(?=${LATEX_COMMAND_PATTERN}\b)`, 'g');
const KNOWN_BAD_COMMAND_REGEX = /\\cdotpm\b/g;
const COMMON_FUNCTION_REGEX = /(?<!\\)\b(sin|cos|tan|log|ln)\b/g;
const MATH_OPERATOR_SYMBOL_REGEX = /[·•×]/g;

const GREEK_CHARACTER_MAP = {
  α: String.raw`\alpha`,
  β: String.raw`\beta`,
  γ: String.raw`\gamma`,
  δ: String.raw`\delta`,
  Δ: String.raw`\Delta`,
  θ: String.raw`\theta`,
  λ: String.raw`\lambda`,
  μ: String.raw`\mu`,
  π: String.raw`\pi`,
  ρ: String.raw`\rho`,
  σ: String.raw`\sigma`,
  τ: String.raw`\tau`,
  ω: String.raw`\omega`,
  φ: String.raw`\phi`,
};

const wrapFormulaBody = (value) => {
  const text = String(value || '').trim();
  return text ? `$${normalizeMathExpression(text)}$` : text;
};

function normalizeTextWrappedOperators(value) {
  let current = String(value || '');
  let previous = '';

  while (current !== previous) {
    previous = current;
    current = current.replace(TEXT_WITH_OPERATOR_REGEX, (_, left, operator, right) => {
      const operatorCommand = operator === '×' ? String.raw`\times` : String.raw`\cdot`;
      return String.raw`\text{${left.trim()}} ${operatorCommand} \text{${right.trim()}}`;
    });
  }

  return current;
}

function normalizeMathExpression(value) {
  return normalizeTextWrappedOperators(String(value || ''))
    .replace(KNOWN_DOUBLE_BACKSLASH_REGEX, '\\')
    .replace(KNOWN_BAD_COMMAND_REGEX, String.raw`\cdot`)
    .replace(GREEK_CHARACTER_REGEX, (match) => GREEK_CHARACTER_MAP[match] || match)
    .replace(COMMON_FUNCTION_REGEX, (_match, fnName) => `\\${fnName}`)
    .replace(MATH_OPERATOR_SYMBOL_REGEX, (match) => (match === '×' ? String.raw` \times ` : String.raw` \cdot `))
    .replace(/\s{2,}/g, ' ')
    .trim();
}

function protectExplicitMathSegments(value) {
  const segments = [];
  let index = 0;

  const replaceSegment = (delimiter, content) => {
    const token = `__PHOTON_MATH_${index}__`;
    segments.push({
      token,
      value: `${delimiter}${normalizeMathExpression(content)}${delimiter}`,
    });
    index += 1;
    return token;
  };

  const withDisplayProtected = String(value || '').replace(EXPLICIT_DISPLAY_MATH_REGEX, (_, content) => replaceSegment('$$', content));
  const withAllProtected = withDisplayProtected.replace(EXPLICIT_INLINE_MATH_REGEX, (_, content) => replaceSegment('$', content));

  return { text: withAllProtected, segments };
}

function restoreExplicitMathSegments(value, segments) {
  return segments.reduce(
    (current, segment) => current.replaceAll(segment.token, segment.value),
    String(value || ''),
  );
}

function wrapLeadingLatexSegment(value) {
  const text = String(value || '').trim();
  if (!RAW_LATEX_COMMAND_REGEX.test(text)) {
    return '';
  }

  const proseBoundary = text.match(/\s+(?:(?:[A-Za-z]{3,})|(?:[\u0980-\u09FF]{2,}))/u);
  if (!proseBoundary) {
    return text;
  }

  return text.slice(0, proseBoundary.index).trim();
}

const wrapRawLatexLine = (value) => {
  const line = String(value || '');
  if (!RAW_LATEX_COMMAND_REGEX.test(line)) {
    return line;
  }

  const listPrefixMatch = line.match(/^(\s*(?:[-*+]|\d+\.)\s+)/);
  const prefix = listPrefixMatch ? listPrefixMatch[1] : '';
  const body = listPrefixMatch ? line.slice(prefix.length) : line;
  const separatorIndex = Math.max(body.lastIndexOf(':'), body.lastIndexOf('ঃ'));

  if (separatorIndex >= 0 && separatorIndex < body.length - 1) {
    const before = body.slice(0, separatorIndex + 1);
    const after = body.slice(separatorIndex + 1).trim();
    return after ? `${prefix}${before} ${wrapFormulaBody(after)}` : line;
  }

  const firstMathIndex = body.search(RAW_LATEX_COMMAND_REGEX);
  if (firstMathIndex > 0) {
    const before = body.slice(0, firstMathIndex).trimEnd();
    const after = body.slice(firstMathIndex).trim();
    const leadingMath = wrapLeadingLatexSegment(after);
    if (!leadingMath) {
      return line;
    }

    const trailingText = after.slice(leadingMath.length).trim();
    return trailingText
      ? `${prefix}${before} ${wrapFormulaBody(leadingMath)} ${trailingText}`
      : `${prefix}${before} ${wrapFormulaBody(leadingMath)}`;
  }

  return `${prefix}${wrapFormulaBody(body)}`;
};

const wrapPlainFormulasInLine = (value) => {
  return String(value || '').replace(PLAIN_FORMULA_REGEX, (match, expression) => {
    const compactExpression = expression.trim().replace(/\s+/g, ' ');
    if (!/[=^/+*×·-]/.test(compactExpression)) {
      return match;
    }

    return match.replace(expression, wrapFormulaBody(compactExpression));
  });
};

export const normalizeRichText = (value) => {
  const prepared = String(value || '')
    .replace(/\r\n?/g, '\n')
    .replace(DISPLAY_MATH_REGEX, (_, inner) => `$$${inner}$$`)
    .replace(INLINE_MATH_REGEX, (_, inner) => `$${inner}$`)
    .replace(LITERAL_NEWLINE_REGEX, '\n')
    .replace(LITERAL_TAB_REGEX, ' ');

  const protectedMath = protectExplicitMathSegments(prepared);
  const normalizedLines = protectedMath.text
    .split('\n')
    .map((line) => {
      const plainWrapped = wrapPlainFormulasInLine(line);
      const protectedLine = protectExplicitMathSegments(plainWrapped);
      const rawWrapped = wrapRawLatexLine(protectedLine.text);
      return restoreExplicitMathSegments(rawWrapped, protectedLine.segments);
    })
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  return restoreExplicitMathSegments(normalizedLines, protectedMath.segments);
};
