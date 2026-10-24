
import { motion, AnimatePresence } from 'framer-motion';
import type { ExtractedItem, Citation } from '../types';
import { CheckCircle2, XCircle, Clock } from 'lucide-react';
import { cn } from '../lib/utils';

interface IntelligencePaneProps {
  items: ExtractedItem[];
  onStatus: (id: string, s: 'confirmed' | 'dismissed') => void;
  onCite: (c: Citation) => void;
  isExtracting: boolean;
}

function fmt(ms: number): string {
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function ItemCard({ item, onStatus, onCite }: { item: ExtractedItem, onStatus: (id: string, s: 'confirmed' | 'dismissed') => void, onCite: (c: Citation) => void }) {
  const isDecision = item.type === 'decision';
  const colorClass = isDecision ? "text-accent-purple" : "text-accent-cyan";
  const glowClass = isDecision ? "shadow-[0_0_20px_rgba(176,97,255,0.15)] border-accent-purple/30" : "shadow-[0_0_20px_rgba(59,212,255,0.15)] border-accent-cyan/30";

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className={cn("glow-card glass-panel p-4 mb-3", item.status === 'pending' ? glowClass : "border-white/10 opacity-70")}
    >
      <div className="flex justify-between items-start gap-3">
        <div className="flex-1">
          <div className={cn("text-[10px] uppercase tracking-wider font-bold mb-1", colorClass)}>
            {isDecision ? "Decision" : "Action Item"}
          </div>
          <div className="text-sm text-gray-200 mb-2 leading-relaxed">{item.text}</div>
          
          {(item.owner || item.due) && (
            <div className="flex items-center gap-3 text-xs text-gray-400 mb-3 bg-black/20 rounded p-1.5 w-max">
              {item.owner && <span>👤 {item.owner}</span>}
              {item.due && <span className="flex items-center gap-1"><Clock className="w-3 h-3"/> {item.due}</span>}
            </div>
          )}

          <div className="flex flex-wrap gap-1.5">
            {item.citations.map((c, i) => (
              <button
                key={i}
                onClick={() => onCite(c)}
                className="text-[10px] px-2 py-0.5 rounded-full border border-white/10 bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
              >
                {c.speaker} @ {fmt(c.start_ms)}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col items-end gap-2 shrink-0">
          {item.status === 'pending' ? (
            <div className="flex flex-col gap-1.5">
              <button onClick={() => onStatus(item.id, 'confirmed')} className="text-xs flex items-center gap-1 px-2 py-1 rounded bg-green-500/10 text-green-400 hover:bg-green-500/20 transition-colors">
                <CheckCircle2 className="w-3.5 h-3.5" /> Confirm
              </button>
              <button onClick={() => onStatus(item.id, 'dismissed')} className="text-xs flex items-center gap-1 px-2 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors">
                <XCircle className="w-3.5 h-3.5" /> Dismiss
              </button>
            </div>
          ) : (
            <span className={cn(
              "text-[10px] px-2 py-1 rounded-full uppercase tracking-wider font-semibold",
              item.status === 'confirmed' ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
            )}>
              {item.status}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export function IntelligencePane({ items, onStatus, onCite, isExtracting }: IntelligencePaneProps) {
  const decisions = items.filter((i) => i.type === 'decision');
  const actions = items.filter((i) => i.type === 'action_item');

  return (
    <div className="glass-panel flex-1 p-5 flex flex-col h-[500px]">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white tracking-wide">AI Extraction</h3>
        {isExtracting && <span className="text-xs text-accent-cyan animate-pulse">Extracting...</span>}
      </div>

      <div className="flex-1 overflow-y-auto pr-2">
        <AnimatePresence>
          {items.length === 0 && !isExtracting ? (
            <motion.div initial={{opacity:0}} animate={{opacity:1}} className="text-sm text-gray-500 italic mt-4 text-center">
              No items extracted yet. Run extraction to analyze this meeting.
            </motion.div>
          ) : null}

          {decisions.length > 0 && (
            <div className="mb-6">
              <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">Decisions</h4>
              {decisions.map(it => <ItemCard key={it.id} item={it} onStatus={onStatus} onCite={onCite} />)}
            </div>
          )}

          {actions.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">Action Items</h4>
              {actions.map(it => <ItemCard key={it.id} item={it} onStatus={onStatus} onCite={onCite} />)}
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
