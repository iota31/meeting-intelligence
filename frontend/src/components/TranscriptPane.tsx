
import type { Turn } from '../types';

interface TranscriptPaneProps {
  turns: Turn[];
  isLoading: boolean;
}

function fmt(ms: number): string {
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function TranscriptPane({ turns, isLoading }: TranscriptPaneProps) {
  if (isLoading) {
    return (
      <div className="glass-panel flex-1 p-5 animate-pulse">
        <div className="h-4 w-24 bg-white/10 rounded mb-6" />
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i}>
              <div className="h-3 w-32 bg-white/10 rounded mb-2" />
              <div className="h-3 w-full bg-white/5 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="glass-panel flex-1 p-5 flex flex-col h-[500px]">
      <h3 className="text-sm font-semibold text-white mb-4 tracking-wide">Meeting Transcript</h3>
      
      {turns.length === 0 ? (
        <div className="text-sm text-gray-500 italic">No transcript available.</div>
      ) : (
        <div className="flex-1 overflow-y-auto pr-2 space-y-4">
          {turns.map((t) => (
            <div
              key={t.turn_id}
              data-turn-id={t.turn_id}
              data-speaker={t.speaker}
              className="p-3 rounded-xl bg-white/[0.02] border border-white/5 transition-all duration-300 hover:bg-white/[0.04]"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-xs font-semibold text-accent-cyan">{t.speaker}</span>
                <span className="text-[10px] text-gray-500">{fmt(t.start_ms)} – {fmt(t.end_ms)}</span>
              </div>
              <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                {t.text}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
