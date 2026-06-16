"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

export function AiWaitingStatus({
  messages,
}: {
  messages: readonly string[];
}) {
  return <AiWaitingStatusSequence key={messages.join("\u0000")} messages={messages} />;
}

function AiWaitingStatusSequence({
  messages,
}: {
  messages: readonly string[];
}) {
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    if (messages.length <= 1) {
      return;
    }
    const intervalId = window.setInterval(() => {
      setMessageIndex((currentIndex) =>
        Math.min(currentIndex + 1, messages.length - 1),
      );
    }, 2500);
    return () => window.clearInterval(intervalId);
  }, [messages]);

  return (
    <div
      className="flex min-h-14 items-center gap-3 rounded-lg bg-[var(--wen-bg)] px-4 py-3 text-sm font-semibold text-[var(--wen-orange)]"
      role="status"
    >
      <Loader2 aria-hidden="true" className="h-4 w-4 shrink-0 animate-spin" />
      <span className="min-w-0">{messages[messageIndex]}</span>
    </div>
  );
}
