// specs/034-format-chat-answers — renders a chat answer's markdown-style
// structure (paragraphs, lists incl. nested, emphasis, headers, links, inline
// code, blockquotes) instead of one raw run-on string. No rehype-raw: embedded
// HTML/script in the answer stays inert text (FR-004).
import ReactMarkdown, { type Components } from "react-markdown";
import remarkBreaks from "remark-breaks";
import { Link } from "react-router-dom";

const components: Components = {
  p: ({ children }) => <p className="text-sm text-zinc-100">{children}</p>,
  ul: ({ children }) => <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-100">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5 text-sm text-zinc-100">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-zinc-100">{children}</strong>,
  em: ({ children }) => <em className="italic text-zinc-300">{children}</em>,
  h1: ({ children }) => <h1 className="text-lg font-semibold text-zinc-100">{children}</h1>,
  h2: ({ children }) => <h2 className="text-base font-semibold text-zinc-100">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-semibold text-zinc-100">{children}</h3>,
  h4: ({ children }) => <h4 className="text-sm font-semibold text-zinc-200">{children}</h4>,
  h5: ({ children }) => <h5 className="text-sm font-medium text-zinc-200">{children}</h5>,
  h6: ({ children }) => <h6 className="text-sm font-medium text-zinc-300">{children}</h6>,
  // 035-chat-and-news-upgrade US4 (FR-013) — a root-relative link (a
  // linkified ticker or news citation, both produced server-side by
  // semantic/linkify.py) navigates in-app via react-router instead of a new
  // tab; every other href (external URLs, any scheme) keeps 034's original
  // behavior unchanged.
  a: ({ href, children }) =>
    href?.startsWith("/") ? (
      <Link to={href} className="text-sky-500 hover:text-sky-400">
        {children}
      </Link>
    ) : (
      <a href={href} target="_blank" rel="noopener noreferrer" className="text-sky-500 hover:text-sky-400">
        {children}
      </a>
    ),
  code: ({ children }) => (
    <code className="rounded bg-zinc-950 px-1 py-0.5 text-xs text-zinc-300">{children}</code>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-zinc-800 pl-3 text-sm text-zinc-400">{children}</blockquote>
  ),
};

// react-markdown sanitizes non-http(s)/mailto/tel URL schemes by default;
// FR-010 explicitly requires no scheme restriction or validation.
function passthroughUrlTransform(url: string): string {
  return url;
}

export default function AnswerText({ text }: { text: string }) {
  return (
    <div className="max-w-full space-y-2 break-words">
      <ReactMarkdown
        remarkPlugins={[remarkBreaks]}
        components={components}
        urlTransform={passthroughUrlTransform}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
