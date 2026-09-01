export async function askQuery(question: string): Promise<string> {
  const response = await fetch("http://127.0.0.1:8000/query", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question,
    }),
  })

  if (!response.ok) {
    throw new Error("Failed to get response from Query Agent")
  }

  const data = await response.json()

  return data.answer
}
