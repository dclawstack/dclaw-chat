"use client";

const TOPIC_STYLES: Record<string, string> = {
  frontend: "bg-blue-100 text-blue-700 border-blue-200",
  backend:  "bg-green-100 text-green-700 border-green-200",
  devops:   "bg-orange-100 text-orange-700 border-orange-200",
  design:   "bg-purple-100 text-purple-700 border-purple-200",
  bug:      "bg-red-100 text-red-700 border-red-200",
  feature:  "bg-yellow-100 text-yellow-800 border-yellow-200",
  question: "bg-cyan-100 text-cyan-700 border-cyan-200",
  general:  "bg-gray-100 text-gray-500 border-gray-200",
};

interface TopicBadgeProps {
  topic: string;
  small?: boolean;
  onClick?: () => void;
}

export function TopicBadge({ topic, small, onClick }: TopicBadgeProps) {
  const style = TOPIC_STYLES[topic] ?? "bg-gray-100 text-gray-500 border-gray-200";
  const base = `inline-flex items-center border rounded-full font-medium transition-opacity ${style}`;
  const size = small ? "px-1.5 py-0 text-[10px]" : "px-2 py-0.5 text-xs";
  const cursor = onClick ? "cursor-pointer hover:opacity-80" : "";

  return (
    <span
      className={`${base} ${size} ${cursor}`}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      {topic}
    </span>
  );
}
