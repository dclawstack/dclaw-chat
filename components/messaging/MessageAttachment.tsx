"use client";

import { MessageAttachment, FileAttachment, LinkPreview } from "@/types/chat";
import { FileText, Download, Film, ExternalLink } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090/api/v1";

function fmt(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function resolveUrl(url: string) {
  if (url.startsWith("/api/")) return `http://localhost:8090${url}`;
  return url;
}

function ImageCard({ att }: { att: FileAttachment }) {
  return (
    <a href={resolveUrl(att.url)} target="_blank" rel="noopener noreferrer" className="block">
      <img
        src={resolveUrl(att.url)}
        alt={att.name}
        className="max-w-xs max-h-48 rounded-lg border object-cover hover:opacity-90 transition-opacity"
      />
    </a>
  );
}

function VideoCard({ att }: { att: FileAttachment }) {
  return (
    <video
      src={resolveUrl(att.url)}
      controls
      className="max-w-xs max-h-48 rounded-lg border"
    />
  );
}

function FileCard({ att }: { att: FileAttachment }) {
  return (
    <a
      href={resolveUrl(att.url)}
      download={att.name}
      className="flex items-center gap-3 px-3 py-2.5 border rounded-lg bg-muted/30 hover:bg-muted/60 transition-colors max-w-xs"
    >
      {att.type === "video" ? (
        <Film className="h-8 w-8 text-muted-foreground shrink-0" />
      ) : (
        <FileText className="h-8 w-8 text-muted-foreground shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium truncate">{att.name}</p>
        <p className="text-xs text-muted-foreground">{fmt(att.size)}</p>
      </div>
      <Download className="h-4 w-4 text-muted-foreground shrink-0" />
    </a>
  );
}

function LinkCard({ att }: { att: LinkPreview }) {
  return (
    <a
      href={att.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex gap-3 border rounded-lg overflow-hidden bg-muted/20 hover:bg-muted/40 transition-colors max-w-sm"
    >
      {att.image && (
        <img
          src={att.image}
          alt=""
          className="w-20 h-20 object-cover shrink-0"
          onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
        />
      )}
      <div className="flex-1 min-w-0 p-2.5">
        <div className="flex items-center gap-1.5 mb-0.5">
          {att.favicon && (
            <img src={att.favicon} alt="" className="h-3.5 w-3.5 shrink-0"
              onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />
          )}
          <p className="text-xs text-muted-foreground truncate">
            {new URL(att.url).hostname}
          </p>
        </div>
        <p className="text-xs font-semibold line-clamp-2">{att.title || att.url}</p>
        {att.description && (
          <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">{att.description}</p>
        )}
        <ExternalLink className="h-3 w-3 text-muted-foreground mt-1" />
      </div>
    </a>
  );
}

export function AttachmentList({ attachments }: { attachments: MessageAttachment[] }) {
  if (!attachments?.length) return null;
  return (
    <div className="mt-2 flex flex-col gap-2">
      {attachments.map((att, i) => {
        if (att.type === "image") return <ImageCard key={i} att={att as FileAttachment} />;
        if (att.type === "video") return <VideoCard key={i} att={att as FileAttachment} />;
        if (att.type === "link") return <LinkCard key={i} att={att as LinkPreview} />;
        return <FileCard key={i} att={att as FileAttachment} />;
      })}
    </div>
  );
}
