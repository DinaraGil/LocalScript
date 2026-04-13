import ChatInstance from "./ChatInstance";
import { useState } from 'react';

export default function ChatHistory() {
    const [chatHistory, setChatHistory] = useState(() => {
    const saved = localStorage.getItem("chats");
        
    if (!saved || saved === "[object Object]") {
        const initialData = {};
        localStorage.setItem("chats", JSON.stringify(initialData));
        localStorage.setItem("nextIndex", "0");
        return initialData;
    }

    try {
        return JSON.parse(saved);
    } catch (e) {
        return {};
    }
    });
    return (
        <div className="flex-col justify-center items-center">
            {Object.entries(chatHistory).map(([chatId, history]) => (
                <section key={chatId} className="m-1 mr-5 ml-5">
                    <ChatInstance id={`${chatId}`} title={history[0].content} />
                </section>
            ))}
        </div>
    )
}