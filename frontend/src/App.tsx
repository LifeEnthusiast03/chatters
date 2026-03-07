import { useState } from "react";
import { MessageCard } from "./components/MessageCard";
import { Sidebar } from "./components/Sidebar";
import { SlidersHorizontal } from "lucide-react";
import  Login from "./components/Login.tsx";

type Category = "PERSONAL" | "EVENT" | "WORK" | "NOTICE" | "CRITICAL";
type TimeFilter = "LAST 7 DAYS" | "TODAY" | "LAST 1 HOUR" | "TOP 10";

const MOCK_MESSAGES = [
  {
    id: "1",
    category: "PERSONAL",
    content: "Hey, can we reschedule tomorrow's lunch?",
    summary: "Request to reschedule lunch meeting.",
    sender: "Alice Johnson",
    timestamp: "10:30 AM",
    severity: "low",
    platform: "WHATSAPP",
  },
  {
    id: "2",
    category: "WORK",
    content: "Please review the Q3 financial report.",
    summary: "Urgent financial report review.",
    sender: "Finance Dept",
    timestamp: "09:15 AM",
    severity: "high",
    platform: "SLACK",
  },
  {
    id: "3",
    category: "NOTICE",
    content: "Water supply will stop tomorrow 2–5 PM.",
    summary: "Water maintenance notice.",
    sender: "City Council",
    timestamp: "Yesterday",
    severity: "medium",
    platform: "TELEGRAM",
  },
  {
    id: "4",
    category: "WORK",
    content: "Client loved the presentation!",
    summary: "Positive feedback.",
    sender: "Sarah Manager",
    timestamp: "2 hours ago",
    severity: "low",
    platform: "SLACK",
  },
  {
    id: "5",
    category: "PERSONAL",
    content: "Don't forget to buy milk.",
    summary: "Reminder to buy milk.",
    sender: "Wife",
    timestamp: "Just now",
    severity: "low",
    platform: "WHATSAPP",
  },
  {
    id: "6",
    category: "CRITICAL",
    content: "Server CPU usage 98%. Immediate action needed.",
    summary: "Production server overload.",
    sender: "Monitoring Bot",
    timestamp: "5 min ago",
    severity: "high",
    platform: "SLACK",
  },
] as const;

function App() {
  const [activeCategory, setActiveCategory] = useState<Category>("PERSONAL");
  const [activeTimeFilter, setActiveTimeFilter] = useState<TimeFilter>("TODAY");
  const [user, setUser] = useState<string | null>(null);
  if (!user) {
  return <Login onLogin={(email) => setUser(email)} />;
}

  const [platformFilters, setPlatformFilters] = useState({
    whatsapp: true,
    telegram: true,
    slack: true,
    others: true,
  });

  const filteredMessages = MOCK_MESSAGES.filter((msg) => {
    if (msg.category !== activeCategory) return false;

    const key = msg.platform.toLowerCase();
    const platformKey = key in platformFilters ? key : "others";

    if (!platformFilters[platformKey as keyof typeof platformFilters])
      return false;

    return true;
  });

  return (
    <div className="min-h-screen grid grid-cols-[1fr_340px] bg-gradient-to-br from-[#0b0d1a] via-[#0f1225] to-[#070812] text-white">
      
      {/* MAIN FEED */}
      <div className="flex flex-col">

        {/* HEADER */}
        <header className="sticky top-0 z-10 px-10 py-6 backdrop-blur-xl border-b border-white/10 bg-black/30">
          
          <div className="max-w-5xl mx-auto space-y-5">

            {/* Title */}
            <div className="flex items-center justify-between">

              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-900/40">
                  <SlidersHorizontal size={16} />
                </div>

                <span className="font-bold text-lg tracking-tight">
                  MessageHub
                </span>
              </div>

              <span className="text-xs text-gray-400">
                {filteredMessages.length} messages
              </span>
            </div>

            {/* CATEGORY FILTERS */}
            <div className="flex gap-2 flex-wrap">
              {["PERSONAL","EVENT","WORK","NOTICE","CRITICAL"].map((cat) => (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat as Category)}
                  className={`px-4 py-1.5 rounded-xl text-xs font-semibold border transition
                  ${
                    activeCategory === cat
                      ? "bg-indigo-500/20 border-indigo-400 text-indigo-300"
                      : "border-white/10 text-gray-400 hover:text-white"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* TIME FILTER */}
            <div className="flex gap-2">
              {["LAST 7 DAYS","TODAY","LAST 1 HOUR","TOP 10"].map((f) => (
                <button
                  key={f}
                  onClick={() => setActiveTimeFilter(f as TimeFilter)}
                  className={`px-3 py-1 text-xs rounded-full border
                  ${
                    activeTimeFilter === f
                      ? "bg-white/10 border-white/20"
                      : "border-white/10 text-gray-400"
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
        </header>

        {/* MESSAGE FEED */}
        <main className="flex-1 overflow-y-auto">

          <div className="max-w-5xl mx-auto px-8 py-8">

            <div className="space-y-6">

              {filteredMessages.length > 0 ? (
                filteredMessages.map((msg) => (
                  <MessageCard key={msg.id} message={msg} />
                ))
              ) : (
                <div className="text-center text-gray-500 py-20">
                  No messages in this category
                </div>
              )}

            </div>

          </div>

        </main>
      </div>

      {/* SIDEBAR */}
      <Sidebar
        platformFilters={platformFilters}
        setPlatformFilters={setPlatformFilters}
      />
    </div>
  );
}

export default App;