"use client";

import { HuddleList } from "@/components/huddles/HuddleList";

export default function HuddlesPage() {
  return (
    <div className="flex h-screen bg-gray-950">
      <div className="flex-1 max-w-2xl mx-auto">
        <HuddleList userId="local-user" displayName="You" />
      </div>
    </div>
  );
}
