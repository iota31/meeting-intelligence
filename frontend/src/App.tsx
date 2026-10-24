import { useEffect, useState, useRef } from 'react';
import type { MeetingSummary, Turn, Citation, ExtractedItem, ChatResult } from './types';
import { Sidebar } from './components/Sidebar';
import { UploadZone } from './components/UploadZone';
import { TranscriptPane } from './components/TranscriptPane';
import { IntelligencePane } from './components/IntelligencePane';
import { ChatWidget } from './components/ChatWidget';
import { SettingsModal } from './components/SettingsModal';
import { ConfirmModal } from './components/ConfirmModal';

const API_BASE: string = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export default function App() {
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [items, setItems] = useState<ExtractedItem[]>([]);
  const [itemCounts, setItemCounts] = useState<Record<string, number>>({});

  const [isLoadingList, setIsLoadingList] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const loadCounter = useRef(0);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [isExtracting, setIsExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);

  const [chatQuestion, setChatQuestion] = useState('');
  const [isChatting, setIsChatting] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatResult, setChatResult] = useState<ChatResult | null>(null);

  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [meetingToDelete, setMeetingToDelete] = useState<string | null>(null);

  useEffect(() => {
    loadMeetings();
  }, []);

  useEffect(() => {
    let interval: number;
    const hasProcessing = meetings.some(m => m.status === 'processing');
    if (hasProcessing) {
      interval = window.setInterval(() => {
        loadMeetings();
        if (selectedId && meetings.find(m => m.id === selectedId)?.status === 'processing') {
          loadDetail(selectedId);
        }
      }, 3000);
    }
    return () => {
      if (interval) window.clearInterval(interval);
    };
  }, [meetings, selectedId]);

  async function loadMeetings() {
    setIsLoadingList(true);
    setListError(null);
    try {
      const res = await fetch(`${API_BASE}/api/meetings`);
      if (!res.ok) throw new Error('Failed to load meetings');
      const data = await res.json();
      if (Array.isArray(data)) setMeetings(data);
    } catch (e: any) {
      setListError(e?.message || 'Failed to load meetings');
    } finally {
      setIsLoadingList(false);
    }
  }

  async function loadDetail(id: string) {
    const seq = ++loadCounter.current;
    setIsLoadingDetail(true);
    setDetailError(null);
    setChatResult(null);
    setChatError(null);
    try {
      const res = await fetch(`${API_BASE}/api/meetings/${id}`);
      if (!res.ok) throw new Error('Failed to load meeting');
      const data = await res.json();
      if (seq !== loadCounter.current) return;
      setTurns(Array.isArray(data.turns) ? data.turns : []);
      setItems(Array.isArray(data.items) ? data.items : []);
      setItemCounts((c) => ({ ...c, [id]: data.items?.length || 0 }));
      setSelectedId(id);
    } catch (e: any) {
      if (seq !== loadCounter.current) return;
      setDetailError(e?.message || 'Failed to load meeting');
      setTurns([]);
      setItems([]);
    } finally {
      if (seq === loadCounter.current) setIsLoadingDetail(false);
    }
  }

  function selectMeeting(id: string) {
    if (id === selectedId) return;
    setSelectedId(id);
    loadDetail(id);
  }

  function confirmDelete(id: string) {
    setMeetingToDelete(id);
  }

  async function deleteMeeting(id: string) {
    setMeetingToDelete(null);
    try {
      const res = await fetch(`${API_BASE}/api/meetings/${id}`, { method: 'DELETE' });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j?.error?.message || `Delete failed (${res.status})`);
      }
      
      if (id === selectedId) {
        setSelectedId(null);
        setTurns([]);
        setItems([]);
        setChatResult(null);
      }
      await loadMeetings();
    } catch (e: any) {
      alert(e?.message || 'Failed to delete meeting');
    }
  }

  async function handleUpload(file: File, title: string, force?: 'transcript' | 'audio'): Promise<boolean> {
    setIsUploading(true);
    setUploadError(null);

    const form = new FormData();
    form.append('file', file);
    if (title.trim()) form.append('title', title.trim());

    const name = file.name.toLowerCase();
    const ext = name.includes('.') ? name.split('.').pop() || '' : '';

    let endpoint = '';
    if (force === 'transcript' || (!force && ext === 'txt')) {
      endpoint = '/api/meetings/upload/transcript';
    } else if (force === 'audio' || (!force && (ext === 'mp3' || ext === 'wav'))) {
      endpoint = '/api/meetings/upload/audio';
    } else {
      setUploadError('Unsupported file type. Use .txt, .mp3, or .wav');
      setIsUploading(false);
      return false;
    }

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, { method: 'POST', body: form });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json?.error?.message || `Upload failed (${res.status})`);
      
      const newId: string = json.meeting_id;
      await loadMeetings();
      if (newId) {
        setSelectedId(newId);
        await loadDetail(newId);
      }
      return true;
    } catch (e: any) {
      setUploadError(e?.message || 'Upload failed');
      return false;
    } finally {
      setIsUploading(false);
    }
  }

  async function triggerExtract() {
    if (!selectedId) return;
    setIsExtracting(true);
    setExtractError(null);
    try {
      const res = await fetch(`${API_BASE}/api/meetings/${selectedId}/extract`, { method: 'POST' });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(payload?.error?.message || `Extract failed (${res.status})`);
      }
      if (res.status === 202) {
        await loadMeetings();
        await loadDetail(selectedId);
      } else if (Array.isArray(payload?.items)) {
        setItems(payload.items);
        setItemCounts((c) => ({ ...c, [selectedId]: payload.items.length }));
      } else {
        await loadDetail(selectedId);
      }
    } catch (e: any) {
      setExtractError(e?.message || 'Extraction failed');
    } finally {
      setIsExtracting(false);
    }
  }

  async function setItemStatus(itemId: string, status: 'confirmed' | 'dismissed') {
    try {
      const res = await fetch(`${API_BASE}/api/items/${itemId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
      if (res.ok) {
         setItems((prev) => prev.map((it) => (it.id === itemId ? { ...it, status } : it)));
      } else {
         const j = await res.json().catch(() => ({}));
         setDetailError(j?.error?.message || `Failed to update item (${res.status})`);
      }
    } catch (e: any) {
       setDetailError(e?.message || 'Failed to update item');
    }
  }

  async function sendChat() {
    if (!selectedId || !chatQuestion.trim()) return;
    setIsChatting(true);
    setChatError(null);
    setChatResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/meetings/${selectedId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: chatQuestion.trim() }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json?.error?.message || `Chat failed (${res.status})`);
      setChatResult({ answer: json.answer ?? '', citations: Array.isArray(json.citations) ? json.citations : [] });
    } catch (e: any) {
      setChatError(e?.message || 'Chat failed');
    } finally {
      setIsChatting(false);
    }
  }

  function goToCitation(c: Citation) {
    const tid = c.turn_id || undefined;
    if (tid) {
      const el = document.querySelector(`[data-turn-id="${CSS.escape(tid)}"]`) as HTMLElement | null;
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('!bg-accent-purple/30', 'shadow-[0_0_15px_rgba(176,97,255,0.3)]', 'border-accent-purple/50');
        window.setTimeout(() => {
          el.classList.remove('!bg-accent-purple/30', 'shadow-[0_0_15px_rgba(176,97,255,0.3)]', 'border-accent-purple/50');
        }, 1600);
        return;
      }
    }
    const els = Array.from(document.querySelectorAll('[data-turn-id]')) as HTMLElement[];
    const match = els.find((el) => el.getAttribute('data-speaker') === c.speaker);
    if (match) {
      match.scrollIntoView({ behavior: 'smooth', block: 'center' });
      match.classList.add('!bg-accent-purple/30');
      window.setTimeout(() => match.classList.remove('!bg-accent-purple/30'), 1600);
    }
  }

  const selectedMeta = meetings.find((m) => m.id === selectedId);

  return (
    <div className="min-h-screen bg-background text-gray-200 flex font-sans">
      <Sidebar 
        meetings={meetings} 
        selectedId={selectedId} 
        itemCounts={itemCounts} 
        onSelect={selectMeeting} 
        onDelete={confirmDelete}
        onRefresh={loadMeetings} 
        onOpenSettings={() => setIsSettingsOpen(true)}
        isLoading={isLoadingList} 
        listError={listError}
      />
      
      <main className="flex-1 overflow-y-auto p-8 h-screen">
        <div className="max-w-6xl mx-auto">
          <UploadZone onUpload={handleUpload} isUploading={isUploading} uploadError={uploadError} />

          {selectedId ? (
            <div className="space-y-6">
              <div className="flex items-center justify-between glass-panel p-4">
                <div>
                  <h2 className="text-xl font-bold text-white tracking-wide">{selectedMeta?.title || 'Untitled Meeting'}</h2>
                  <p className="text-xs text-gray-500 mt-1 uppercase tracking-widest">{selectedId}</p>
                </div>
                <button
                  onClick={triggerExtract}
                  disabled={isExtracting || selectedMeta?.status === 'processing'}
                  className="bg-white/5 hover:bg-white/10 border border-white/10 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
                >
                  {isExtracting ? 'Extracting...' : (selectedMeta?.status === 'processing' ? 'Processing...' : 'Run Extraction')}
                </button>
              </div>

              {detailError && <div className="text-red-400 text-sm">{detailError}</div>}
              {extractError && <div className="text-amber-400 text-sm">Extract: {extractError}</div>}

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <TranscriptPane turns={turns} isLoading={isLoadingDetail} />
                <IntelligencePane 
                  items={items} 
                  onStatus={setItemStatus} 
                  onCite={goToCitation} 
                  isExtracting={isExtracting} 
                />
              </div>

              <ChatWidget 
                question={chatQuestion}
                setQuestion={setChatQuestion}
                onSend={sendChat}
                isChatting={isChatting}
                result={chatResult}
                error={chatError}
                onCite={goToCitation}
                disabled={!selectedId}
              />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500 border border-dashed border-white/10 rounded-xl">
              <p>Select a meeting from the sidebar or upload a new one to begin.</p>
            </div>
          )}
        </div>
      </main>

      <SettingsModal 
        isOpen={isSettingsOpen} 
        onClose={() => setIsSettingsOpen(false)} 
        apiBase={API_BASE} 
      />

      <ConfirmModal
        isOpen={meetingToDelete !== null}
        title="Delete Meeting"
        message="Are you sure you want to delete this meeting? This action cannot be undone and will permanently remove all associated intelligence."
        onConfirm={() => {
          if (meetingToDelete) deleteMeeting(meetingToDelete);
        }}
        onCancel={() => setMeetingToDelete(null)}
      />
    </div>
  );
}
