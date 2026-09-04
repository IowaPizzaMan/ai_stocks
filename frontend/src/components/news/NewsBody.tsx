// Renders a news story's body — specs/035-chat-and-news-upgrade (FR-006a,
// research.md R8). FMP articles carry real HTML (lists, bold); the general
// and stock feeds carry plain text only.
//
// Deliberately a SEPARATE component/plugin set from ../chat/AnswerText: that
// one renders a partly model-controlled chat answer and must keep 034
// FR-004's guarantee that embedded HTML stays inert (no rehype-raw). This
// component renders provider-controlled article HTML, so rehype-raw +
// rehype-sanitize is the correct, safe choice here and nowhere else.
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";

const components: Components = {
  p: ({ children }) => <p className="text-sm text-zinc-300">{children}</p>,
  ul: ({ children }) => <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-300">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5 text-sm text-zinc-300">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-zinc-200">{children}</strong>,
  em: ({ children }) => <em className="italic text-zinc-400">{children}</em>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-sky-500 hover:text-sky-400">
      {children}
    </a>
  ),
};

export default function NewsBody({ bodyHtml, bodyText }: { bodyHtml: string | null; bodyText: string | null }) {
  if (bodyHtml) {
    return (
      <div className="max-w-full space-y-2 break-words">
        <ReactMarkdown rehypePlugins={[rehypeRaw, rehypeSanitize]} components={components}>
          {bodyHtml}
        </ReactMarkdown>
      </div>
    );
  }

  if (!bodyText) return null;
  return <p className="text-sm text-zinc-300">{bodyText}</p>;
}
