import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";
import katex from "katex";

type ChatMessageRendererProps = {
  content: string;
};

type MathIssue = {
  expression: string;
  mode: "inline" | "block";
  error: string;
};

const BLOCK_MATH_REGEX = /\$\$([\s\S]+?)\$\$/g;
const INLINE_MATH_REGEX = /(^|[^$])\$([^\n$][^$]*?)\$/g;

function collectMathIssues(markdown: string): MathIssue[] {
  const issues: MathIssue[] = [];

  for (const match of markdown.matchAll(BLOCK_MATH_REGEX)) {
    const expression = match[1]?.trim();
    if (!expression) continue;

    try {
      katex.renderToString(expression, { displayMode: true, throwOnError: true, strict: "error" });
    } catch (error) {
      issues.push({
        expression,
        mode: "block",
        error: error instanceof Error ? error.message : "Invalid block-math expression.",
      });
    }
  }

  for (const match of markdown.matchAll(INLINE_MATH_REGEX)) {
    const expression = match[2]?.trim();
    if (!expression) continue;

    try {
      katex.renderToString(expression, { displayMode: false, throwOnError: true, strict: "error" });
    } catch (error) {
      issues.push({
        expression,
        mode: "inline",
        error: error instanceof Error ? error.message : "Invalid inline-math expression.",
      });
    }
  }

  return issues;
}

export default function ChatMessageRenderer({ content }: ChatMessageRendererProps) {
  const mathIssues = useMemo(() => collectMathIssues(content), [content]);

  if (mathIssues.length > 0) {
    return (
      <div className="chat-renderer-fallback" role="status" aria-live="polite">
        <p className="chat-renderer-warning">
          Some math could not be rendered. Showing plain text for this message.
        </p>
        <pre className="chat-renderer-raw">{content}</pre>
      </div>
    );
  }

  return (
    <div className="chat-markdown-content">
      <ReactMarkdown
        skipHtml
        remarkPlugins={[remarkMath]}
        rehypePlugins={[[rehypeKatex, { strict: "error", throwOnError: true }]]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
