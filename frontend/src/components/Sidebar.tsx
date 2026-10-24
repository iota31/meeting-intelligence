
import { cn } from '../lib/utils';
import type { MeetingSummary } from '../types';
import { FolderGit2, FileAudio, FileText, Settings, Trash2, Loader2, AlertCircle } from 'lucide-react';

interface SidebarProps {
  meetings: MeetingSummary[];
  selectedId: string | null;
  itemCounts: Record<string, number>;
  onSelect: (id: string) => void;
  onRefresh: () => void;
  onOpenSettings: () => void;
  onDelete?: (id: string) => void;
  isLoading: boolean;
  listError?: string | null;
}

export function Sidebar({ meetings, selectedId, itemCounts, onSelect, onRefresh, onOpenSettings, onDelete, isLoading, listError }: SidebarProps) {
  return (
    <aside className="w-72 flex-shrink-0 glass-panel flex flex-col overflow-hidden h-[calc(100vh-2rem)] sticky top-4">
      <div className="p-5 border-b border-panel-border flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-purple to-accent-cyan flex items-center justify-center shadow-[0_0_15px_rgba(176,97,255,0.4)]">
          <FolderGit2 className="text-white w-5 h-5" />
        </div>
        <h1 className="font-bold text-lg tracking-wide text-white">Meeting Intelligence</h1>
      </div>

      <div className="p-4 flex-1 overflow-y-auto">
        <div className="flex items-center justify-between mb-4 px-1">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Meetings</div>
          <button 
            onClick={onRefresh} 
            className="text-xs text-accent-cyan hover:text-accent-cyan/80 transition-colors"
          >
            Refresh
          </button>
        </div>

        {isLoading && <div className="text-sm text-gray-500 px-1">Loading...</div>}
        {listError && <div className="text-sm text-red-400 px-1 mb-2">{listError}</div>}
        
        <ul className="space-y-1.5">
          {meetings.map((m) => (
            <li key={m.id}>
              <button
                onClick={() => onSelect(m.id)}
                className={cn(
                  "w-full text-left px-3 py-2.5 rounded-lg border transition-all duration-200 group relative overflow-hidden",
                  selectedId === m.id
                    ? "bg-accent-purple/10 border-accent-purple/30 shadow-[0_0_10px_rgba(176,97,255,0.1)]"
                    : "border-transparent hover:bg-white/5 hover:border-white/10"
                )}
              >
                <div className="flex items-start gap-2">
                  {m.status === 'processing' ? (
                    <Loader2 className="w-4 h-4 mt-0.5 shrink-0 text-accent-cyan animate-spin" />
                  ) : m.status === 'error' ? (
                    <span title="Processing failed" className="shrink-0">
                      <AlertCircle className="w-4 h-4 mt-0.5 text-red-400" />
                    </span>
                  ) : m.source_type === 'audio' ? (
                    <FileAudio className={cn("w-4 h-4 mt-0.5 shrink-0", selectedId === m.id ? "text-accent-cyan" : "text-gray-500 group-hover:text-gray-300")} />
                  ) : (
                    <FileText className={cn("w-4 h-4 mt-0.5 shrink-0", selectedId === m.id ? "text-accent-cyan" : "text-gray-500 group-hover:text-gray-300")} />
                  )}
                  <div className="flex-1 min-w-0 pr-8">
                    <div 
                      className={cn("font-medium truncate", selectedId === m.id ? "text-white" : "text-gray-300")}
                      title={m.title || 'Untitled Meeting'}
                    >
                      {m.title || 'Untitled Meeting'}
                    </div>
                    <div className="text-[10px] text-gray-500 mt-1 flex items-center gap-2">
                      <span>{new Date(m.created_at).toLocaleDateString()}</span>
                      <span>•</span>
                      <span>{m.turn_count} turns</span>
                      {itemCounts[m.id] !== undefined && (
                        <>
                          <span>•</span>
                          <span>{itemCounts[m.id]} items</span>
                        </>
                      )}
                    </div>
                  </div>
                  {onDelete && (
                    <div 
                      className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center p-1.5 hover:bg-red-500/20 rounded text-gray-500 hover:text-red-400 absolute right-2 top-1/2 -translate-y-1/2"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(m.id);
                      }}
                      title="Delete meeting"
                    >
                      <Trash2 className="w-4 h-4" />
                    </div>
                  )}
                </div>
              </button>
            </li>
          ))}
          {meetings.length === 0 && !isLoading && (
            <li className="text-sm text-gray-500 px-2 py-4 text-center border border-dashed border-white/10 rounded-lg">
              No meetings found.<br/>Upload one to begin.
            </li>
          )}
        </ul>
      </div>

      <div className="p-4 border-t border-panel-border mt-auto">
        <button 
          onClick={onOpenSettings}
          className="flex items-center gap-3 text-sm text-gray-400 hover:text-white transition-colors w-full px-2 py-2 rounded-lg hover:bg-white/5"
        >
          <Settings className="w-4 h-4" />
          Settings
        </button>
      </div>
    </aside>
  );
}
