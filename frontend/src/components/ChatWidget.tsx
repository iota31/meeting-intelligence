
import type { ChatResult, Citation } from '../types';
import { Send, Bot, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface ChatWidgetProps {
  question: string;
  setQuestion: (q: string) => void;
  onSend: () => void;
  isChatting: boolean;
  result: ChatResult | null;
  error: string | null;
  onCite: (c: Citation) => void;
  disabled: boolean;
}

function fmt(ms: number): string {
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function ChatWidget({ question, setQuestion, onSend, isChatting, result, error, onCite, disabled }: ChatWidgetProps) {
  return (
    <div className="glass-panel p-4 mt-4 relative overflow-hidden">
      {/* Decorative gradient blur */}
      <div className="absolute -bottom-20 -right-20 w-64 h-64 bg-accent-purple/10 blur-[100px] pointer-events-none" />

      <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2 tracking-wide">
        <Sparkles className="w-4 h-4 text-accent-cyan" /> 
        AI Chat Assistant
      </h3>

      <div className="flex gap-2 relative z-10">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
          placeholder="Ask a question about this meeting..."
          className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-accent-purple/50 focus:ring-1 focus:ring-accent-purple/50 transition-all"
          disabled={disabled || isChatting}
        />
        <button
          onClick={onSend}
          disabled={disabled || isChatting || !question.trim()}
          className="bg-accent-purple hover:bg-accent-purple/80 text-white rounded-xl px-4 py-2.5 disabled:opacity-50 transition-colors flex items-center justify-center shadow-lg shadow-accent-purple/20"
        >
          {isChatting ? <span className="animate-pulse">...</span> : <Send className="w-4 h-4" />}
        </button>
      </div>
      
      {error && <div className="text-red-400 text-xs mt-2">{error}</div>}

      <AnimatePresence>
        {result && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-4 pt-4 border-t border-white/10 relative z-10"
          >
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded bg-gradient-to-br from-accent-purple/20 to-accent-cyan/20 border border-white/10 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-accent-cyan" />
              </div>
              <div className="flex-1">
                <div className="text-sm text-gray-200 whitespace-pre-wrap leading-relaxed">{result.answer}</div>
                
                {result.citations.length > 0 && (
                  <div className="mt-3 bg-black/20 rounded-lg p-2 border border-white/5">
                    <div className="text-[10px] uppercase tracking-widest text-gray-500 mb-1.5 font-semibold">Citations</div>
                    <div className="flex flex-wrap gap-1.5">
                      {result.citations.map((c, idx) => (
                        <button
                          key={idx}
                          onClick={() => onCite(c)}
                          className="text-[10px] px-2 py-0.5 rounded border border-accent-cyan/20 bg-accent-cyan/10 hover:bg-accent-cyan/20 text-accent-cyan transition-colors"
                        >
                          {c.speaker} @ {fmt(c.start_ms)}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
