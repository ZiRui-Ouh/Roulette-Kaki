import { useState, type KeyboardEvent } from "react"

type ChatInputProps = {
  onSend: (question: string) => void
  isLoading: boolean
}

function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [question, setQuestion] = useState("")

  const handleSubmit = () => {
    if (!question.trim() || isLoading) return

    onSend(question)
    setQuestion("")
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      handleSubmit()
    }
  }

  return (
    <div className="flex gap-3">
      <input
        type="text"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question about Singapore policies..."
        disabled={isLoading}
        className="flex-1 rounded-lg border border-gray-700 bg-gray-900 px-4 py-3 text-white placeholder-gray-500 outline-none focus:border-gray-500 disabled:opacity-50"
      />

      <button
        onClick={handleSubmit}
        disabled={isLoading}
        className="rounded-lg bg-white px-6 py-3 font-medium text-black hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isLoading ? "Thinking..." : "Send"}
      </button>
    </div>
  )
}

export default ChatInput
