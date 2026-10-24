export type SourceType = 'transcript' | 'audio';

export interface MeetingSummary {
  id: string;
  title: string;
  created_at: string;
  source_type: SourceType;
  source_meta?: any;
  turn_count: number;
  status?: 'processing' | 'ready' | 'error';
}

export interface Turn {
  turn_id: string;
  speaker: string;
  start_ms: number;
  end_ms: number;
  text: string;
}

export interface Citation {
  turn_id?: string | null;
  speaker: string;
  start_ms: number;
  end_ms: number;
}

export interface ExtractedItem {
  id: string;
  meeting_id: string;
  type: 'decision' | 'action_item';
  text: string;
  owner?: string | null;
  due?: string | null;
  status: 'pending' | 'confirmed' | 'dismissed';
  citations: Citation[];
}

export interface ChatCitation extends Citation {}

export interface ChatResult {
  answer: string;
  citations: ChatCitation[];
}
