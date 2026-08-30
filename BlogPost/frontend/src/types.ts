export interface DebateSummary {
  date: string;
  title: string;
  youtube_url: string;
}

export interface Topic {
  topic_id: string;
  title: string;
  speakers: string[];
  source_url: string;
  format: "pdf" | "html";
}

export interface InterestingTopic {
  topic_id: string;
  reason: string;
}

export interface Digest {
  date: string;
  title: string;
  youtube_url: string;
  summary: string;
  topic_count: number;
  category_breakdown: Record<string, number>;
  interesting_topics: InterestingTopic[];
  topics: Topic[];
  scraped_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  grounded?: boolean;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  topics_used: string[];
  grounded: boolean;
}

export interface ApiError {
  status: number;
  error: string;
  message: string;
}
