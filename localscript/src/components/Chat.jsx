import { Send } from 'lucide-react';
import { useState }  from 'react';
import ChatMessages from './ChatMessages';

const sendPrompt = (() => {
    console.log("Send in the clowns")
    return;
})

const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
        if (!e.shiftKey) {
            e.preventDefault();
            sendPrompt();
        }
    }
};

export default function Chat() {
    const [chatId, setChatId] = useState(() => {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get("id")
    });
    
    return (
        <div className="flex flex-col h-screen w-full items-end">
            <div className="flex flex-1 max-h-[90vh] w-full justify-center items-center">
                {
                    chatId === null || chatId >= localStorage.getItem("nextIndex")
                    ? <div className="text-center text-5xl text-neutral-600 select-none">New Chat...</div> 
                    : <ChatMessages id={chatId}/>
                }
            </div>
            <div className="w-full items-end">
                <div className="flex flex-row w-full items-center mx-auto p-10">
                    <textarea 
                        placeholder="I code in Lua :3"
                        className="flex-1 text-xl bg-neutral-800 rounded-[25px] p-4 pl-8 pd-8
                           resize-none overflow-y-auto max-h-[10vh]
                           outline-none focus:ring-neutral-700 focus:ring-2
                           [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
                        rows={1}
                        onKeyDown={handleKeyDown}
                        onInput={(e) => {
                            e.target.style.height = 'auto';
                            e.target.style.height = e.target.scrollHeight + 'px';
                        }}
                />
                    <div className="ml-2">
                        <button onClick={() => sendPrompt()} className="bg-neutral-800 p-4 rounded-full 
                        hover:bg-neutral-700 transition
                        ">
                            <Send size={24} className="text-amber-50" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}