import { useState } from "react"
import ChatInput from "../components/ChatInput"
import ChatMessage from "../components/ChatMessage"
import { askQuery } from "../api"

type Message = {
  role: "user" | "assistant"
  content: string
}

function QueryPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)

  const handleSend = async (question: string) => {
    const newMessage: Message = {
      role: "user",
      content: question,
    }

    setMessages((currentMessages) => [
      ...currentMessages,
      newMessage,
    ])

    setIsLoading(true)

    try {
      const answer = await askQuery(question)

      setMessages((currentMessages) => [
        ...currentMessages,
        {
          role: "assistant",
          content: answer,
        },
      ])
    } catch (error) {
      console.error(error)

      setMessages((currentMessages) => [
        ...currentMessages,
        {
          role: "assistant",
          content: "Sorry, something went wrong.",
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="mx-auto flex min-h-screen max-w-4xl flex-col px-6 py-12">

        {/* Header */}
        <div>
          <h1 className="text-4xl font-bold">
            Query Agent
          </h1>

          <p className="mt-2 text-gray-400">
            Ask a question about government policies.
          </p>
        </div>

        {/* Chat Area */}
        <div className="flex-1 py-10">
          {messages.length === 0 && !isLoading ? (
            <div className="flex h-full items-center justify-center">
              <div className="text-center">
                <h2 className="text-2xl font-semibold">
                  How can I help you?
                </h2>

                <p className="mt-2 text-gray-400">
                  Ask me anything about Singapore government policies.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((message, index) => (
                <ChatMessage
                  key={index}
                  role={message.role}
                  content={message.content}
                />
              ))}

              {isLoading && (
                <ChatMessage
                  role="assistant"
                  content="Thinking..."
                />
              )}
            </div>
          )}
        </div>

        {/* Input */}
        <ChatInput
          onSend={handleSend}
          isLoading={isLoading}
        />

      </div>
    </div>
  )
}

export default QueryPage