import React, { useState } from 'react';
import { Send, Bot as BotIcon, MessageSquare } from 'lucide-react';

interface SidebarProps {
  platformFilters: {
    whatsapp: boolean;
    telegram: boolean;
    slack: boolean;
    others: boolean;
  };
  setPlatformFilters: React.Dispatch<React.SetStateAction<{
    whatsapp: boolean;
    telegram: boolean;
    slack: boolean;
    others: boolean;
  }>>;
}

export const Sidebar: React.FC<SidebarProps> = ({ platformFilters, setPlatformFilters }) => {
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState<{ sender: 'user' | 'bot'; text: string }[]>([]);

  const togglePlatform = (key: keyof typeof platformFilters) => {
    setPlatformFilters(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSendMessage = () => {
    if (!chatInput.trim()) return;
    
    setChatHistory([...chatHistory, { sender: 'user', text: chatInput }]);
    setTimeout(() => {
      setChatHistory(curr => [...curr, { sender: 'bot', text: `You asked: "${chatInput}". This is a placeholder response.` }]);
    }, 1000);
    setChatInput('');
  };

  return (
    <div className="bg-gray-50 border-l border-gray-200 h-screen w-80 p-4 fixed right-0 top-0 overflow-y-auto flex flex-col">
      <div className="mb-8">
        <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
          <MessageSquare size={20} />
          PLATFORM CARDS
        </h2>
        <div className="grid grid-cols-2 gap-3">
          {Object.entries(platformFilters).map(([key, value]) => (
            <button
              key={key}
              onClick={() => togglePlatform(key as keyof typeof platformFilters)}
              className={`p-3 rounded-lg border text-sm font-medium transition-all uppercase flex items-center justify-center gap-2
                ${value ? 'bg-blue-600 text-white border-blue-700 shadow-md' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'}
              `}
            >
              {key}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col border-t pt-6 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
          <BotIcon size={20} />
          QUERY CHATBOT
        </h2>
        
        <div className="flex-1 overflow-y-auto mb-4 space-y-3 pr-2 custom-scrollbar">
          {chatHistory.length === 0 ? (
            <div className="text-center text-gray-400 text-sm italic mt-10">
              Ask me anything about the messages...
            </div>
          ) : (
            chatHistory.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] p-3 rounded-lg text-sm ${
                  msg.sender === 'user' 
                    ? 'bg-blue-600 text-white rounded-br-none' 
                    : 'bg-gray-100 text-gray-800 rounded-bl-none'
                }`}>
                  {msg.text}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="relative">
          <input
            type="text"
            className="w-full p-3 pr-12 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all placeholder-gray-400 text-sm"
            placeholder="Type your query..."
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
          />
          <button
            onClick={handleSendMessage}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-blue-600 hover:bg-blue-50 rounded-full transition-colors"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};
