import { useState } from 'react';
import { MessageCard } from './components/MessageCard';
import { Sidebar } from './components/Sidebar';
import { Filter } from 'lucide-react';

// Mock Data
const MOCK_MESSAGES = [
  {
    id: '1',
    category: 'PERSONAL',
    content: "Hey, can we reschedule tomorrow's lunch? Something came up with the kids.",
    summary: "Request to reschedule lunch meeting due to family matter.",
    sender: "Alice Johnson",
    timestamp: "10:30 AM",
    hasMultimedia: false,
    severity: 'low',
    platform: 'WHATSAPP'
  },
  {
    id: '2',
    category: 'WORK',
    content: "Please review the attached Q3 financial report by EOD. It's critical for the board meeting tomorrow.",
    summary: "Urgent review request for Q3 financial report.",
    sender: "Finance Dept (Bob)",
    timestamp: "09:15 AM",
    hasMultimedia: true,
    multimediaType: 'image',
    severity: 'high',
    platform: 'SLACK'
  },
  {
    id: '3',
    category: 'SOCIETY',
    content: "Community notice: Water supply will be interrupted tomorrow from 2 PM to 5 PM for maintenance.",
    summary: "Water supply interruption notice for tomorrow afternoon.",
    sender: "City Council",
    timestamp: "Yesterday",
    hasMultimedia: false,
    severity: 'medium',
    platform: 'TELEGRAM'
  },
  {
    id: '4',
    category: 'WORK',
    content: "Great job on the presentation! The client was very impressed.",
    summary: "Positive feedback from client on presentation.",
    sender: "Sarah Manager",
    timestamp: "2 hours ago",
    hasMultimedia: false,
    severity: 'low',
    platform: 'SLACK'
  },
  {
    id: '5',
    category: 'PERSONAL',
    content: "Don't forget to buy milk on your way home!",
    summary: "Reminder to buy milk.",
    sender: "Wife",
    timestamp: "Just now",
    hasMultimedia: false,
    severity: 'low',
    platform: 'WHATSAPP'
  },
] as const;

type Category = 'PERSONAL' | 'SOCIETY' | 'WORK';
type TimeFilter = 'LAST 7 DAYS' | 'TODAY' | 'LAST 1 HOUR' | 'TOP 10';

function App() {
  const [activeCategory, setActiveCategory] = useState<Category>('PERSONAL');
  const [activeTimeFilter, setActiveTimeFilter] = useState<TimeFilter>('TODAY');
  
  const [platformFilters, setPlatformFilters] = useState<{
    whatsapp: boolean;
    telegram: boolean;
    slack: boolean;
    others: boolean;
  }>({
    whatsapp: true,
    telegram: true,
    slack: true,
    others: true
  });

  // Filter Logic
  const filteredMessages = MOCK_MESSAGES.filter(msg => {
    // 1. Category Filter
    if (msg.category !== activeCategory) return false;

    // 2. Platform Filter
    const platformKey = msg.platform.toLowerCase() as keyof typeof platformFilters;
    if (!platformFilters[platformKey]) return false;

    // 3. Time Filter (Mock logic for demo purposes)
    // In a real app, you'd compare timestamps.
    return true; 
  });

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Main Content Area */}
      <div className="flex-1 mr-80"> 
        <header className="bg-white shadow-sm sticky top-0 z-10 px-8 py-6">
          <div className="max-w-4xl mx-auto space-y-6">
            
            {/* Main Categories */}
            <div className="flex justify-center">
              <div className="bg-gray-100 p-1 rounded-xl inline-flex shadow-inner">
                {(['PERSONAL', 'SOCIETY', 'WORK'] as Category[]).map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(cat)}
                    className={`px-8 py-3 rounded-lg text-sm font-bold transition-all duration-200 uppercase tracking-wide
                      ${activeCategory === cat 
                        ? 'bg-white text-blue-600 shadow-md transform scale-105' 
                        : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200'
                      }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>

            {/* Time Filters */}
            <div className="flex justify-center gap-3 overflow-x-auto pb-2">
              {(['LAST 7 DAYS', 'TODAY', 'LAST 1 HOUR', 'TOP 10'] as TimeFilter[]).map((filter) => (
                <button
                  key={filter}
                  onClick={() => setActiveTimeFilter(filter)}
                  className={`px-4 py-1.5 rounded-full text-xs font-semibold border transition-colors whitespace-nowrap
                    ${activeTimeFilter === filter
                      ? 'bg-gray-800 text-white border-gray-800'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-gray-400'
                    }`}
                >
                  {filter}
                </button>
              ))}
            </div>

          </div>
        </header>

        <main className="max-w-3xl mx-auto px-6 py-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
              <Filter className="text-blue-600" />
              MESSAGES
            </h2>
            <span className="text-sm text-gray-500 bg-white px-3 py-1 rounded-full border shadow-sm">
              Showing {filteredMessages.length} results
            </span>
          </div>

          <div className="space-y-6">
            {filteredMessages.length > 0 ? (
              filteredMessages.map((msg) => (
                <MessageCard key={msg.id} message={msg} />
              ))
            ) : (
              <div className="text-center py-20 bg-white rounded-xl border border-dashed border-gray-300">
                <div className="text-gray-400 mb-2">No messages found</div>
                <p className="text-sm text-gray-500">Try adjusting your filters.</p>
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Sidebar - Fixed Position */}
      <Sidebar 
        platformFilters={platformFilters}
        setPlatformFilters={setPlatformFilters}
      />
    </div>
  );
}

export default App;
