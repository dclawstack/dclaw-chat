"use client";

import { useState } from "react";
import { ChannelMessage, FileAttachment } from "@/types/chat";
import { X, Images, ZoomIn } from "lucide-react";
import { Button } from "@/components/ui/button";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function resolveUrl(url: string) {
  if (url.startsWith("/api/")) return `http://localhost:8000${url}`;
  return url;
}

interface MediaGalleryProps {
  messages: ChannelMessage[];
  onClose: () => void;
}

export function MediaGallery({ messages, onClose }: MediaGalleryProps) {
  const [lightbox, setLightbox] = useState<string | null>(null);

  const images: { url: string; name: string; from: string }[] = [];
  for (const m of messages) {
    for (const att of m.attachments ?? []) {
      if (att.type === "image") {
        const fa = att as FileAttachment;
        images.push({ url: resolveUrl(fa.url), name: fa.name, from: m.user_name });
      }
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="h-14 border-b flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-2">
          <Images className="h-4 w-4 text-dclaw-500" />
          <span className="text-sm font-semibold">Media Gallery</span>
          <span className="text-xs text-muted-foreground">({images.length} images)</span>
        </div>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {images.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
          No images shared yet
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-3 grid grid-cols-3 gap-2 content-start">
          {images.map((img, i) => (
            <button
              key={i}
              onClick={() => setLightbox(img.url)}
              className="relative aspect-square rounded-md overflow-hidden border hover:opacity-90 transition-opacity group"
            >
              <img src={img.url} alt={img.name} className="w-full h-full object-cover" />
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                <ZoomIn className="h-5 w-5 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Lightbox */}
      {lightbox && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center"
          onClick={() => setLightbox(null)}
        >
          <img
            src={lightbox}
            alt="Preview"
            className="max-w-[90vw] max-h-[90vh] object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />
          <button
            onClick={() => setLightbox(null)}
            className="absolute top-4 right-4 text-white hover:text-gray-300"
          >
            <X className="h-6 w-6" />
          </button>
        </div>
      )}
    </div>
  );
}
