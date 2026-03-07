import { useState } from "react";
import { Send } from "lucide-react";

export const Sidebar = ({ platformFilters, setPlatformFilters }: any) => {

  const [chatInput, setChatInput] = useState("");
  const [chatHistory, setChatHistory] = useState<any[]>([]);

  const togglePlatform = (key: string) => {
    setPlatformFilters((prev: any) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const sendMessage = () => {
    if (!chatInput.trim()) return;

    setChatHistory((prev) => [
      ...prev,
      { sender: "user", text: chatInput },
      { sender: "bot", text: "Demo assistant response." },
    ]);

    setChatInput("");
  };

  return (
    <div className="h-screen bg-black/30 backdrop-blur-xl border-l border-white/10 p-6 flex flex-col gap-6">

      {/* PLATFORM FILTERS */}
      <div>
        <h2 className="text-xs text-gray-400 uppercase mb-3">Platforms</h2>

        <div className="grid grid-cols-2 gap-2">
          {Object.keys(platformFilters).map((key) => (
            <button
              key={key}
              onClick={() => togglePlatform(key)}
              className={`px-3 py-2 rounded-lg border text-xs
              ${
                platformFilters[key]
                  ? "bg-indigo-500/20 border-indigo-400"
                  : "border-white/10 text-gray-500"
              }`}
            >
              {key}
            </button>
          ))}
        </div>
      </div>

      {/* CHAT */}
      <div className="flex flex-col flex-1">

        <h2 className="text-xs text-gray-400 uppercase mb-3">
          Query Assistant
        </h2>

        <div className="flex-1 overflow-y-auto space-y-2 text-sm text-gray-300">
          {chatHistory.length === 0 && (
            <div className="text-gray-500 text-xs mt-10 text-center">
              Ask things like:
              <br />
              "Show critical alerts"
            </div>
          )}

          {chatHistory.map((msg, i) => (
            <div
              key={i}
              className={`p-2 rounded-lg ${
                msg.sender === "user"
                  ? "bg-indigo-500/20 self-end"
                  : "bg-white/5"
              }`}
            >
              {msg.text}
            </div>
          ))}
        </div>

        <div className="flex mt-3 gap-2">
          <input
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs outline-none"
            placeholder="Ask something..."
          />

          <button
            onClick={sendMessage}
            className="w-8 h-8 flex items-center justify-center bg-indigo-600 rounded-lg"
          >
            <Send size={14} />
          </button>
        </div>

      </div>
    </div>
  );
};