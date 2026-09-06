// Shared types keep API responses, saved sessions, and components consistent.
export type Lang =
  | "English"
  | "Chinese"
  | "Malay"
  | "Tamil"
  | "Singlish";

export const LANGUAGES: { code: Lang; label: string }[] = [
  { code: "English", label: "English" },
  { code: "Chinese", label: "中文" },
  { code: "Malay", label: "Bahasa Melayu" },
  { code: "Tamil", label: "தமிழ்" },
  { code: "Singlish", label: "Singlish" },
];

export interface DebateSummary {
  date: string;
  title: string;
  youtube_url: string;
}

export interface Sitting {
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
  timestamp?: number;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  topics_used: string[];
  grounded: boolean;
}

export interface Flashcard {
  id: string;
  title: string;
  body: string;
}

export type FlashcardSource = "topic" | "chat";

export interface FlashcardDeck {
  date: string;
  topic_id?: string | null;
  source: FlashcardSource;
  cards: Flashcard[];
  generated_at: string;
}

export interface SavedDeck extends FlashcardDeck {
  savedAt: number;
  topicTitle?: string;
}

export interface ApiError {
  status: number;
  error: string;
  message: string;
}

export interface PolicyKeyFact {
  label: string;
  value: string;
  note?: string;
}

export interface PolicyOfficialSource {
  title: string;
  url: string;
  authority: string;
}

export type PolicyCategory =
  | "Housing"
  | "CPF & Finance"
  | "Healthcare"
  | "Jobs & Skills"
  | "Grants & Families"
  | "Parliament & Hansard"
  | "Transport & Infrastructure";

export interface Policy {
  id: string;
  title: string;
  headline: string;
  category: PolicyCategory;
  ministry: string;
  publishedAt: string;
  effectiveDate: string;
  status: "Active" | "Gazetted" | "Upcoming Revision" | "Implemented";
  badge?: string;
  summary: string;
  leadParagraph: string;
  readTime: string;
  keyFacts: PolicyKeyFact[];
  officialSources: PolicyOfficialSource[];
  suggestedQuestions: string[];
  initialBriefing: string;
  relatedPolicyIds?: string[];
}
