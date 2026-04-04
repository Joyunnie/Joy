interface Highlight {
  start: number;
  end: number;
  type: 'date' | 'time';
  parsed: string;
}

interface DateHighlighterProps {
  text: string;
  highlights: Highlight[];
}

export default function DateHighlighter({ text, highlights }: DateHighlighterProps) {
  if (highlights.length === 0) {
    return <span>{text}</span>;
  }

  const sorted = [...highlights].sort((a, b) => a.start - b.start);
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;

  sorted.forEach((h, i) => {
    if (h.start > lastIndex) {
      parts.push(<span key={`t-${i}`}>{text.slice(lastIndex, h.start)}</span>);
    }
    const color = h.type === 'date' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700';
    parts.push(
      <span
        key={`h-${i}`}
        className={`${color} rounded px-1 text-xs font-medium`}
        title={h.parsed}
      >
        {text.slice(h.start, h.end)}
      </span>,
    );
    lastIndex = h.end;
  });

  if (lastIndex < text.length) {
    parts.push(<span key="tail">{text.slice(lastIndex)}</span>);
  }

  return <span>{parts}</span>;
}
