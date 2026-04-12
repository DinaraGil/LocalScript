import { useState } from "react";
import { Send, Settings, Trash } from "lucide-react";

export default function LocalLLMFrontend() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hello! I'm your local LLM." },
  ]);
  const [input, setInput] = useState("");

  const sendMessage = () => {
    if (!input.trim()) return;

    const newMessages = [
      ...messages,
      { role: "user", content: input },
      { role: "assistant", content: "(Local LLM response...)" },
    ];

    setMessages(newMessages);
    setInput("");
  };

  const clearChat = () => {
    setMessages([{ role: "assistant", content: "Chat cleared." }]);
  };

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r flex flex-col">
        <div className="p-4 text-lg font-semibold border-b">Local LLM</div>

        <div className="flex-1 overflow-auto p-2 space-y-2">
          <button className="w-full text-left px-3 py-2 rounded-xl hover:bg-gray-100">
            New Chat
          </button>
        </div>

        <div className="p-2 border-t flex gap-2">
          {/* <button className="flex-1 flex items-center justify-center gap-1 px-2 py-2 rounded-xl hover:bg-gray-100">
            <Settings size={16} /> Settings
          </button> */}
          <button
            onClick={clearChat}
            className="flex items-center justify-center px-2 py-2 rounded-xl hover:bg-gray-100"
          >
            <Trash size={16} />
          </button>
        </div>
      </div>

      <div className="flex-1 flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-auto p-6 space-y-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-xl px-4 py-3 rounded-2xl shadow-sm ${
                  msg.role === "user"
                    ? "bg-blue-500 text-white"
                    : "bg-white"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
        </div>

        {/* Input */}
        <div className="p-4 border-t bg-white flex items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder="Type a message..."
            className="flex-1 px-4 py-2 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <button
            onClick={sendMessage}
            className="p-3 bg-blue-500 text-white rounded-xl hover:bg-blue-600"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
1