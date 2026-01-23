import { useState, useEffect, useRef } from 'react';
import { endpoints } from '../config';

interface Message {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
}

interface Conversation {
  id: number;
  title: string;
  messages: Message[];
}

export default function ChatSidebar({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
        fetchConversations();
    }
  }, [isOpen]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isOpen]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchConversations = async () => {
    const token = localStorage.getItem('token');
    if (!token) return;

    try {
      const response = await fetch(endpoints.conversations, {
        headers: {
          'Authorization': `Token ${token}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setConversations(data);
        if (data.length > 0 && !currentConversationId) {
          selectConversation(data[0]);
        }
      }
    } catch (error) {
      console.error('Error fetching conversations:', error);
    }
  };

  const selectConversation = (conversation: Conversation) => {
    setCurrentConversationId(conversation.id);
    setMessages(conversation.messages || []);
  };

  const createNewConversation = async () => {
    const token = localStorage.getItem('token');
    try {
      const response = await fetch(endpoints.conversations, {
        method: 'POST',
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ title: 'New Chat' })
      });
      if (response.ok) {
        const newConv = await response.json();
        setConversations([newConv, ...conversations]);
        selectConversation(newConv);
      }
    } catch (error) {
      console.error('Error creating conversation:', error);
    }
  };

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !currentConversationId) return;

    const userMessage: Message = {
      id: Date.now(),
      role: 'user',
      content: input
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    const token = localStorage.getItem('token');
    try {
      const response = await fetch(`${endpoints.conversations}${currentConversationId}/message/`, {
        method: 'POST',
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ content: userMessage.content })
      });

      if (response.ok) {
        const aiMessage = await response.json();
        setMessages(prev => [...prev, aiMessage]);
        fetchConversations(); 
      }
    } catch (error) {
      console.error('Error sending message:', error);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-white border-l border-black shadow-lg z-50 flex flex-col transform transition-transform duration-300 ease-in-out">
        {/* Header */}
        <div className="p-4 border-b border-black flex justify-between items-center bg-gray-50">
            <h2 className="font-bold text-lg">Chatbot</h2>
            <button onClick={onClose} className="text-gray-500 hover:text-black">
                Close &times;
            </button>
        </div>

        {/* Conversation List (Collapsed View or separate tab? For now simpler) */}
        {/* Let's put a small bar at top for New Chat */}
        <div className="p-2 border-b border-gray-200 flex gap-2 overflow-x-auto">
             <button 
                onClick={createNewConversation}
                className="px-3 py-1 bg-black text-white text-sm whitespace-nowrap"
            >
                + New
            </button>
            {conversations.map(conv => (
                <button
                    key={conv.id}
                    onClick={() => selectConversation(conv)}
                    className={`px-3 py-1 border text-sm whitespace-nowrap ${
                        currentConversationId === conv.id ? 'bg-gray-200 border-black' : 'border-gray-300'
                    }`}
                >
                    {conv.title || 'Chat'}
                </button>
            ))}
        </div>

      {/* Messages */}
      <div className="flex-1 p-4 overflow-y-auto bg-white">
        {currentConversationId ? (
            <>
                {messages.map((msg, index) => (
                <div 
                    key={index} 
                    className={`mb-4 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}
                >
                    <div 
                    className={`inline-block p-2 rounded-lg text-sm ${
                        msg.role === 'user' 
                        ? 'bg-black text-white' 
                        : 'bg-gray-100 text-black border border-gray-200'
                    }`}
                    >
                    {msg.content}
                    </div>
                </div>
                ))}
                {loading && <div className="text-xs text-gray-500 italic">Thinking...</div>}
                <div ref={messagesEndRef} />
            </>
        ) : (
            <div className="flex h-full items-center justify-center text-gray-400 text-sm">
                Start a conversation
            </div>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-black bg-gray-50">
        <form onSubmit={sendMessage} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type..."
            className="flex-1 p-2 border border-black focus:outline-none focus:ring-1 focus:ring-black text-sm"
            disabled={loading || !currentConversationId}
          />
          <button 
            type="submit"
            disabled={loading || !currentConversationId}
            className="px-4 py-2 bg-black text-white text-sm hover:bg-gray-800 disabled:bg-gray-400"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
