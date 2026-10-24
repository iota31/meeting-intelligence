import { useState } from 'react';
import { UploadCloud } from 'lucide-react';
import { cn } from '../lib/utils';

interface UploadZoneProps {
  onUpload: (file: File, title: string, force?: 'transcript' | 'audio') => Promise<boolean>;
  isUploading: boolean;
  uploadError: string | null;
}

export function UploadZone({ onUpload, isUploading, uploadError }: UploadZoneProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) setSelectedFile(f);
  };

  const handleUpload = () => {
    if (selectedFile) {
      onUpload(selectedFile, title).then((success) => {
        if (success) {
          setSelectedFile(null);
          setTitle('');
        }
      });
    }
  };

  return (
    <div className="glass-panel p-5 mb-6">
      <div className="flex flex-col md:flex-row items-start md:items-stretch gap-4">
        
        <div 
          className={cn(
            "flex-1 border-2 border-dashed rounded-xl p-6 transition-all duration-200 flex flex-col items-center justify-center text-center",
            isDragging 
              ? "border-accent-purple bg-accent-purple/5" 
              : "border-white/10 hover:border-white/20 bg-white/5"
          )}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
        >
          <input
            type="file"
            accept=".txt,.mp3,.wav,audio/mpeg,audio/wav,text/plain"
            onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
            disabled={isUploading}
            className="hidden"
            id="file-upload"
          />
          <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center">
            <UploadCloud className={cn("w-8 h-8 mb-2", isDragging ? "text-accent-purple" : "text-gray-400")} />
            <span className="text-sm font-medium text-gray-300">
              {selectedFile ? selectedFile.name : "Drop .txt, .mp3, or .wav here"}
            </span>
            {!selectedFile && <span className="text-xs text-gray-500 mt-1">or click to browse</span>}
          </label>
        </div>

        <div className="flex flex-col gap-3 w-full md:w-64 shrink-0 justify-end">
          <input
            type="text"
            placeholder="Meeting title (optional)"
            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-accent-cyan/50 focus:ring-1 focus:ring-accent-cyan/50 transition-all"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={isUploading}
          />
          <button
            onClick={handleUpload}
            disabled={isUploading || !selectedFile}
            className="w-full bg-gradient-to-r from-accent-purple to-accent-cyan text-white font-medium px-4 py-2 rounded-lg shadow-lg shadow-accent-purple/20 hover:shadow-accent-purple/40 disabled:opacity-50 disabled:hover:shadow-accent-purple/20 transition-all"
          >
            {isUploading ? 'Processing...' : 'Upload & Analyze'}
          </button>
        </div>
      </div>
      {uploadError && (
        <div className="mt-3 text-sm text-red-400 flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-red-400" />
          {uploadError}
        </div>
      )}
    </div>
  );
}
