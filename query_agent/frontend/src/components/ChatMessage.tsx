import ReactMarkdown from "react-markdown"

type ChatMessageProps = {
  role: "user" | "assistant"
  content: string
}

export default function ChatMessage({
  role,
  content,
}: ChatMessageProps) {
  const isUser = role === "user"

  return (
    <div
      className={`flex w-full ${
        isUser ? "justify-end" : "justify-start"
      }`}
    >
      <div
        className={`max-w-3xl rounded-2xl px-6 py-4 ${
          isUser
            ? "bg-slate-900 text-white"
            : "bg-slate-800 text-white"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap break-words">
            {content}
          </p>
        ) : (
          <div className="prose-chat break-words">
            <ReactMarkdown>
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}