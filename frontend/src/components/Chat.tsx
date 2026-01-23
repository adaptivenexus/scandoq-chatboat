import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { endpoints } from "../config";

interface Message {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
}

interface Conversation {
  id: number;
  title: string;
  messages: Message[];
}

export default function Chat() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<
    number | null
  >(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [editingConversationId, setEditingConversationId] = useState<
    number | null
  >(null);
  const [editTitle, setEditTitle] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchConversations();
    fetchSuggestions();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const fetchSuggestions = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const response = await fetch(`${endpoints.conversations}suggestions/`, {
        headers: { Authorization: `Token ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setSuggestions(data);
      }
    } catch (error) {
      console.error("Error fetching suggestions:", error);
    }
  };

  const fetchConversations = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;

    try {
      const response = await fetch(endpoints.conversations, {
        headers: {
          Authorization: `Token ${token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setConversations(data);
        if (data.length > 0 && !currentConversationId) {
          selectConversation(data[0]);
        }
      }
    } catch (error) {
      console.error("Error fetching conversations:", error);
    }
  };

  const selectConversation = (conversation: Conversation) => {
    setCurrentConversationId(conversation.id);
    setMessages(conversation.messages || []);
  };

  const deleteConversation = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this conversation?"))
      return;

    const token = localStorage.getItem("token");
    try {
      const response = await fetch(`${endpoints.conversations}${id}/`, {
        method: "DELETE",
        headers: { Authorization: `Token ${token}` },
      });
      if (response.ok) {
        setConversations(conversations.filter((c) => c.id !== id));
        if (currentConversationId === id) {
          setCurrentConversationId(null);
          setMessages([]);
        }
      }
    } catch (error) {
      console.error("Error deleting conversation:", error);
    }
  };

  const createNewConversation = async () => {
    const token = localStorage.getItem("token");
    try {
      const response = await fetch(endpoints.conversations, {
        method: "POST",
        headers: {
          Authorization: `Token ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ title: "New Chat" }),
      });
      if (response.ok) {
        const newConv = await response.json();
        setConversations([newConv, ...conversations]);
        selectConversation(newConv);
      }
    } catch (error) {
      console.error("Error creating conversation:", error);
    }
  };

  const startEditing = (conv: Conversation, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingConversationId(conv.id);
    setEditTitle(conv.title);
  };

  const saveTitle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingConversationId) return;

    const token = localStorage.getItem("token");
    try {
      const response = await fetch(
        `${endpoints.conversations}${editingConversationId}/`,
        {
          method: "PATCH",
          headers: {
            Authorization: `Token ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ title: editTitle }),
        },
      );

      if (response.ok) {
        setConversations(
          conversations.map((c) =>
            c.id === editingConversationId ? { ...c, title: editTitle } : c,
          ),
        );
        setEditingConversationId(null);
        setEditTitle("");
      }
    } catch (error) {
      console.error("Error updating conversation title:", error);
    }
  };

  const sendMessage = async (
    e?: React.FormEvent,
    suggestionContent?: string,
  ) => {
    if (e) e.preventDefault();
    const contentToSend = suggestionContent || input;

    if (!contentToSend.trim() || !currentConversationId) return;

    const userMessage: Message = {
      id: Date.now(),
      role: "user",
      content: contentToSend,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    const token = localStorage.getItem("token");
    try {
      const response = await fetch(
        `${endpoints.conversations}${currentConversationId}/message/`,
        {
          method: "POST",
          headers: {
            Authorization: `Token ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ content: userMessage.content }),
        },
      );

      if (response.ok) {
        const aiMessage = await response.json();
        setMessages((prev) => [...prev, aiMessage]);
        fetchConversations();
        // Refresh suggestions after sending a message to update user behavior
        fetchSuggestions();
      }
    } catch (error) {
      console.error("Error sending message:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full">
      {/* Sidebar for Conversations */}
      <div className="w-64 border-r border-gray-200 bg-gray-50 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <button
            onClick={createNewConversation}
            className="w-full px-4 py-2 bg-black text-white text-sm font-medium hover:bg-gray-800 transition-colors"
          >
            + New Chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {conversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => selectConversation(conv)}
              className={`w-full text-left px-4 py-3 text-sm hover:bg-gray-100 border-b border-gray-100 cursor-pointer flex justify-between items-center group ${
                currentConversationId === conv.id
                  ? "bg-gray-200 font-medium"
                  : ""
              }`}
            >
              {editingConversationId === conv.id ? (
                <form
                  onSubmit={saveTitle}
                  className="flex-1 flex items-center gap-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="flex-1 px-2 py-1 text-sm border rounded focus:outline-none focus:ring-1 focus:ring-black min-w-0"
                    autoFocus
                  />
                  <button
                    type="submit"
                    className="p-1 text-green-600 hover:bg-green-100 rounded"
                    title="Save"
                  >
                    ✓
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setEditingConversationId(null);
                    }}
                    className="p-1 text-gray-500 hover:bg-gray-200 rounded"
                    title="Cancel"
                  >
                    ✕
                  </button>
                </form>
              ) : (
                <>
                  <div className="flex-1 overflow-hidden mr-2">
                    <div className="truncate font-medium">
                      {conv.title || "Chat"}
                    </div>
                    <div className="text-xs text-gray-400">ID: {conv.id}</div>
                  </div>
                  <div className="flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => startEditing(conv, e)}
                      className="p-1.5 text-gray-500 hover:bg-gray-200 rounded-full transition-colors mr-1"
                      title="Rename conversation"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-4 w-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                        />
                      </svg>
                    </button>
                    <button
                      onClick={(e) => deleteConversation(e, conv.id)}
                      className="p-1.5 text-red-500 hover:bg-red-100 rounded-full transition-colors"
                      title="Delete conversation"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-4 w-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col bg-white h-full min-h-0">
        {currentConversationId ? (
          <>
            {/* Header */}
            <div className="h-16 border-b border-gray-200 flex items-center px-6 bg-white shrink-0">
              <h2 className="text-lg font-medium truncate">
                {conversations.find((c) => c.id === currentConversationId)
                  ?.title || "Chat"}
              </h2>
            </div>

            {/* Messages */}
            <div className="flex-1 p-6 overflow-y-auto">
              <div className="max-w-3xl mx-auto space-y-6">
                {messages.length === 0 && suggestions.length > 0 && (
                  <div className="mt-10 mb-6">
                    <p className="text-center text-gray-500 mb-6 text-sm font-medium">
                      Suggested prompts based on your activity
                    </p>
                    <div className="grid grid-cols-1 gap-3 max-w-lg mx-auto">
                      {suggestions.map((suggestion, index) => (
                        <button
                          key={index}
                          onClick={() => sendMessage(undefined, suggestion)}
                          className="p-3 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-black text-left text-sm text-gray-700 transition-all shadow-sm group flex items-center justify-between"
                        >
                          <span>{suggestion}</span>
                          <span className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400">
                            →
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {messages.map((msg, index) => (
                  <div
                    key={index}
                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[80%] p-4 rounded-lg text-sm leading-relaxed text-left ${
                        msg.role === "user"
                          ? "bg-black text-white"
                          : "bg-gray-100 text-black border border-gray-200"
                      }`}
                    >
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          ul: ({ node, ...props }) => (
                            <ul
                              className="list-disc list-inside my-2"
                              {...props}
                            />
                          ),
                          ol: ({ node, ...props }) => (
                            <ol
                              className="list-decimal list-inside my-2"
                              {...props}
                            />
                          ),
                          p: ({ node, ...props }) => (
                            <p className="mb-2 last:mb-0" {...props} />
                          ),
                          a: ({ node, ...props }) => (
                            <a
                              className="text-blue-600 underline"
                              target="_blank"
                              rel="noopener noreferrer"
                              {...props}
                            />
                          ),
                          hr: ({ node, ...props }) => (
                            <hr className="my-4 border-gray-300" {...props} />
                          ),
                          h1: ({ node, ...props }) => (
                            <h1 className="text-xl font-bold my-2" {...props} />
                          ),
                          h2: ({ node, ...props }) => (
                            <h2 className="text-lg font-bold my-2" {...props} />
                          ),
                          h3: ({ node, ...props }) => (
                            <h3 className="text-md font-bold my-2" {...props} />
                          ),
                          table: ({ node, ...props }) => (
                            <div className="overflow-x-auto my-4">
                              <table
                                className="min-w-full divide-y divide-gray-200 border border-gray-200"
                                {...props}
                              />
                            </div>
                          ),
                          thead: ({ node, ...props }) => (
                            <thead className="bg-gray-50" {...props} />
                          ),
                          th: ({ node, ...props }) => (
                            <th
                              className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-200"
                              {...props}
                            />
                          ),
                          tbody: ({ node, ...props }) => (
                            <tbody
                              className="bg-white divide-y divide-gray-200"
                              {...props}
                            />
                          ),
                          tr: ({ node, ...props }) => (
                            <tr className="hover:bg-gray-50" {...props} />
                          ),
                          td: ({ node, ...props }) => (
                            <td
                              className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 border-b border-gray-200"
                              {...props}
                            />
                          ),
                          blockquote: ({ node, ...props }) => (
                            <blockquote
                              className="border-l-4 border-gray-300 pl-4 italic my-4 text-gray-600"
                              {...props}
                            />
                          ),
                          code: ({
                            node,
                            className,
                            children,
                            ...props
                          }: any) => {
                            const match = /language-(\w+)/.exec(
                              className || "",
                            );
                            const isInline =
                              !match && !className?.includes("language-");
                            return isInline ? (
                              <code
                                className="bg-gray-200 px-1 py-0.5 rounded text-sm font-mono text-red-500"
                                {...props}
                              >
                                {children}
                              </code>
                            ) : (
                              <div className="my-4 rounded-lg overflow-hidden bg-gray-900 text-white">
                                <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
                                  <span className="text-xs text-gray-400">
                                    {match?.[1] || "code"}
                                  </span>
                                </div>
                                <div className="p-4 overflow-x-auto">
                                  <code
                                    className={`font-mono text-sm ${className || ""}`}
                                    {...props}
                                  >
                                    {children}
                                  </code>
                                </div>
                              </div>
                            );
                          },
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 text-black border border-gray-200 p-4 rounded-lg text-sm italic">
                      Thinking...
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Input */}
            <div className="p-4 border-t border-gray-200 bg-white">
              <div className="max-w-3xl mx-auto">
                {/* Suggestion Chips - Only show when chat is not empty */}
                {messages.length > 0 && suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {suggestions.slice(0, 3).map((suggestion, index) => (
                      <button
                        key={index}
                        onClick={() => sendMessage(undefined, suggestion)}
                        className="px-3 py-1 bg-gray-100 hover:bg-gray-200 border border-gray-200 rounded-full text-xs text-gray-700 transition-colors truncate max-w-50"
                        title={suggestion}
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                )}
                <form onSubmit={sendMessage} className="flex gap-4">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Type your message..."
                    className="flex-1 p-3 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent text-sm"
                    disabled={loading || !currentConversationId}
                  />
                  <button
                    type="submit"
                    disabled={loading || !currentConversationId}
                    className="px-6 py-2 bg-black text-white font-medium hover:bg-gray-800 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                  >
                    Send
                  </button>
                </form>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center flex-col text-gray-400">
            <p className="text-lg font-medium mb-2">Welcome to Chatbot</p>
            <p className="text-sm">Select a conversation or start a new one.</p>
          </div>
        )}
      </div>
    </div>
  );
}
