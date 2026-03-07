import React from 'react';
import { User, Image as ImageIcon, Video, Clock } from 'lucide-react';

interface Message {
  id: string;
  category: 'PERSONAL' | 'SOCIETY' | 'WORK';
  content: string;
  summary: string;
  sender: string;
  timestamp: string;
  hasMultimedia: boolean;
  multimediaType?: 'image' | 'video' | 'audio';
  severity: 'low' | 'medium' | 'high';
  platform: 'WHATSAPP' | 'TELEGRAM' | 'SLACK' | 'OTHERS';
}

interface MessageCardProps {
  message: Message;
}

const severityColors = {
  low: 'bg-green-100 text-green-800 border-green-200',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  high: 'bg-red-100 text-red-800 border-red-200',
};

export const MessageCard: React.FC<MessageCardProps> = ({ message }) => {
  return (
    <div className={`p-4 mb-4 rounded-lg border bg-white shadow-sm hover:shadow-md transition-shadow ${severityColors[message.severity]}`}>
      <div className="flex justify-between items-start mb-2">
        <div className="flex items-center space-x-2">
          <div className="bg-gray-200 p-2 rounded-full">
            <User size={16} className="text-gray-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{message.sender}</h3>
            <div className="flex items-center text-xs text-gray-500">
              <Clock size={12} className="mr-1" />
              <span>{message.timestamp}</span>
              <span className="mx-2">•</span>
              <span className="uppercase font-bold tracking-wider">{message.platform}</span>
            </div>
          </div>
        </div>
        <div className={`px-2 py-0.5 rounded text-xs font-bold uppercase border ${severityColors[message.severity]}`}>
          {message.severity} severity
        </div>
      </div>

      <div className="mb-3">
        <h4 className="text-sm font-semibold text-gray-700 mb-1">Summary</h4>
        <p className="text-gray-600 text-sm italic">{message.summary}</p>
      </div>

      <div className="mb-3">
        <h4 className="text-sm font-semibold text-gray-700 mb-1">Content</h4>
        <p className="text-gray-800">{message.content}</p>
      </div>

      {message.hasMultimedia && (
        <div className="mt-3 p-3 bg-gray-50 rounded border border-gray-200 flex items-center gap-2 text-sm text-gray-600">
          {message.multimediaType === 'video' ? <Video size={16} /> : <ImageIcon size={16} />}
          <span>Multimedia content attached ({message.multimediaType || 'unknown'})</span>
        </div>
      )}
    </div>
  );
};
