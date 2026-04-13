

export default function ChatMessages({ id }) {
    const chatHistory = JSON.parse(localStorage.getItem("chats"));
    const messages = Object.entries(chatHistory).map(([id, msg]) => {
        return msg;
    })[id];
    return (
        //<div>Existing chat... ID = {`${id}`}</div>
        <div className="flex flex-col gap-4 p-4 w-[80%] max-w-[85vw] h-full">
      {messages.map((msg, index) => (
        <div 
          key={index} 
          className={`p-3 rounded-lg overflow-clip max-w-[80%] ${
            msg.role === 'user' 
              ? 'bg-amber-100 self-end text-right text-black' 
              : 'bg-neutral-800 self-start text-left text-white'
          }`}
        >
          {/* Accessing the role and content */}
          <p className="text-lg">{msg.content}</p>
        </div>
      ))}
    </div>
    )
}