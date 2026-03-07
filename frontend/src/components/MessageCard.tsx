import React, { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

export const MessageCard = ({ message }: any) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-lg p-5 hover:scale-[1.01] transition">

      <div className="flex justify-between mb-3">

        <div>
          <h3 className="font-semibold text-sm">{message.sender}</h3>
          <span className="text-xs text-gray-400">
            {message.timestamp} · {message.platform}
          </span>
        </div>

        <span className="text-xs px-2 py-1 rounded-md bg-white/10">
          {message.severity}
        </span>

      </div>

      <div className="bg-white/5 rounded-lg px-3 py-2 mb-2 text-sm text-gray-300 italic">
        {message.summary}
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs text-gray-400"
      >
        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        {expanded ? "Hide full message" : "Show full message"}
      </button>

      {expanded && (
        <p className="text-sm text-gray-300 mt-2">{message.content}</p>
      )}
    </div>
  );
};