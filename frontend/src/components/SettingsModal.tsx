import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Settings, X, Server, Code } from 'lucide-react';
import { cn } from '../lib/utils';
import { Cloud, HardDrive, Key } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiBase: string;
}

export function SettingsModal({ isOpen, onClose, apiBase }: SettingsModalProps) {
  const [status, setStatus] = useState<'checking' | 'active' | 'error'>('checking');
  
  const [mode, setMode] = useState<'local' | 'cloud'>('local');
  const [deepgramKey, setDeepgramKey] = useState('');
  const [groqKey, setGroqKey] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setStatus('checking');
      fetch(`${apiBase}/health`)
        .then(res => res.ok ? setStatus('active') : setStatus('error'))
        .catch(() => setStatus('error'));

      // Fetch settings from backend
      fetch(`${apiBase}/api/settings`)
        .then(res => res.json())
        .then(data => {
          setMode(data.service_mode || 'local');
          setDeepgramKey(data.deepgram_api_key || '');
          setGroqKey(data.groq_api_key || '');
        })
        .catch(console.error);
    }
  }, [isOpen, apiBase]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await fetch(`${apiBase}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          service_mode: mode,
          deepgram_api_key: deepgramKey,
          groq_api_key: groqKey,
        })
      });
      onClose();
    } catch (e) {
      console.error('Failed to save settings', e);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md z-50 glass-panel p-6 shadow-2xl shadow-accent-purple/20"
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Settings className="w-5 h-5 text-accent-cyan" />
                Settings
              </h2>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-white transition-colors bg-white/5 hover:bg-white/10 p-1.5 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="bg-black/20 border border-white/5 rounded-xl p-4">
                <div className="flex items-center gap-3 mb-2">
                  <Server className="w-4 h-4 text-accent-purple" />
                  <h3 className="text-sm font-medium text-gray-200">API Endpoint</h3>
                </div>
                <div className="flex items-center justify-between">
                  <code className="text-xs text-accent-cyan bg-accent-cyan/10 px-2 py-1 rounded">
                    {apiBase}
                  </code>
                  <span className={cn(
                    "text-[10px] uppercase tracking-wider font-semibold px-2 py-1 rounded-full",
                    status === 'active' ? "text-green-400 bg-green-500/10" :
                    status === 'error' ? "text-red-400 bg-red-500/10" :
                    "text-gray-400 bg-gray-500/10 animate-pulse"
                  )}>
                    {status === 'checking' ? 'Checking...' : status === 'active' ? 'Active' : 'Offline'}
                  </span>
                </div>
              </div>

              <div className="bg-black/20 border border-white/5 rounded-xl p-4">
                <div className="flex items-center gap-3 mb-2">
                  <Code className="w-4 h-4 text-accent-purple" />
                  <h3 className="text-sm font-medium text-gray-200">System Version</h3>
                </div>
                <div className="text-sm text-gray-400">
                  Meeting Intelligence <span className="text-white font-medium">v1.0</span>
                </div>
              </div>

              <div className="bg-black/20 border border-white/5 rounded-xl p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <HardDrive className="w-4 h-4 text-accent-purple" />
                    <h3 className="text-sm font-medium text-gray-200">Processing Mode</h3>
                  </div>
                  <div className="flex bg-black/40 rounded-lg p-1 border border-white/5">
                    <button
                      onClick={() => setMode('local')}
                      className={cn(
                        "px-3 py-1 text-xs font-medium rounded-md transition-all",
                        mode === 'local' ? "bg-accent-purple text-white shadow-lg" : "text-gray-400 hover:text-white"
                      )}
                    >
                      <div className="flex items-center gap-1.5">
                        <HardDrive className="w-3 h-3" />
                        Local (Slow)
                      </div>
                    </button>
                    <button
                      onClick={() => setMode('cloud')}
                      className={cn(
                        "px-3 py-1 text-xs font-medium rounded-md transition-all",
                        mode === 'cloud' ? "bg-accent-cyan text-white shadow-lg text-black" : "text-gray-400 hover:text-white"
                      )}
                    >
                      <div className="flex items-center gap-1.5">
                        <Cloud className="w-3 h-3" />
                        Cloud (Fast)
                      </div>
                    </button>
                  </div>
                </div>

                <AnimatePresence>
                  {mode === 'cloud' && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden space-y-3 pt-3 border-t border-white/5"
                    >
                      <div className="space-y-1.5">
                        <label className="text-xs font-medium text-gray-400 flex items-center gap-1.5">
                          <Key className="w-3 h-3" />
                          Deepgram API Key (Transcription)
                        </label>
                        <input
                          type="password"
                          value={deepgramKey}
                          onChange={(e) => setDeepgramKey(e.target.value)}
                          placeholder="dg_..."
                          className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-accent-purple transition-colors"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs font-medium text-gray-400 flex items-center gap-1.5">
                          <Key className="w-3 h-3" />
                          Groq API Key (Extraction & Chat)
                        </label>
                        <input
                          type="password"
                          value={groqKey}
                          onChange={(e) => setGroqKey(e.target.value)}
                          placeholder="gsk_..."
                          className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-accent-purple transition-colors"
                        />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            <div className="mt-8 flex justify-end gap-3">
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="bg-accent-purple hover:bg-accent-purple/80 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {isSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
