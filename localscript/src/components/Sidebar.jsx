import ChatHistory from "./ChatHistory"
import ChatInstance from "./ChatInstance"

export default function Sidebar() {
    return (
        <div className="flex-col bg-neutral-900 h-screen w-[15vw]">
            <div className="flex items-center p-5 gap-3">
                <img src="logo.svg" alt="LocalScript" className="" />
                <p className="flex-1 font-bold text-3xl truncate select-none">
                    LocalScript
                </p>
            </div>
            <a href='/' className="flex justify-center text-3xl m-5 border text-neutral-300 border-neutral-600 rounded-[7px] 
            hover:backdrop-brightness-150 mt-6 mb-6">
                <div className="pt-2 pb-2 select-none">
                    + New Chat
                </div>
                </a>
            <ChatHistory />
        </div>
    )
}