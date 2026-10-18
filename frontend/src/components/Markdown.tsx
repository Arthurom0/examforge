import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkBreaks from "remark-breaks";
import remarkMath from "remark-math";

/** Normalizes \( \) and \[ \] delimiters to $ / $$ so KaTeX picks them up. */
function normalizeMath(src: string) {
  return src
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => `$$${m}$$`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => `$${m}$`);
}

export default function Markdown({
  children,
  className = "",
  breaks = false,
  compact = false,
}: {
  children: string;
  className?: string;
  /** No paragraph margins: for table cells, choices and inline answers. */
  compact?: boolean;
  /** Keep single line breaks (useful for text extracted from PDFs). */
  breaks?: boolean;
}) {
  return (
    <div className={`prose prose-slate max-w-none dark:prose-invert ${compact ? "prose-p:my-0" : "prose-p:my-2"} prose-pre:bg-slate-800 ${className}`}>
      <ReactMarkdown
        remarkPlugins={breaks ? [remarkMath, remarkBreaks] : [remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: "ignore" }]]}
      >
        {normalizeMath(children || "")}
      </ReactMarkdown>
    </div>
  );
}

export function InlineMath({ children }: { children: string }) {
  return <Markdown compact className="inline-block">{children}</Markdown>;
}
