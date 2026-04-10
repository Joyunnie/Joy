interface SpinnerProps {
  /** Tailwind height class for the wrapper div, e.g. "h-40", "h-64". Defaults to "h-40". */
  containerHeight?: string;
}

/** Full-width centered loading spinner for page/section loading states. */
export default function Spinner({ containerHeight = 'h-40' }: SpinnerProps) {
  return (
    <div className={`flex items-center justify-center ${containerHeight}`}>
      <span className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
