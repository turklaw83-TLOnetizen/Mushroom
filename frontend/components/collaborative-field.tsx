"use client";

import { useState, useEffect, useRef } from "react";
import { Lock, User } from "lucide-react";

interface CollaborativeFieldProps {
  value: string;
  onChange: (value: string) => void;
  fieldName: string;
  lockedBy?: string | null;
  updatedBy?: string | null;
  multiline?: boolean;
  placeholder?: string;
  className?: string;
}

export function CollaborativeField({
  value,
  onChange,
  fieldName,
  lockedBy,
  updatedBy,
  multiline = false,
  placeholder = "",
  className = "",
}: CollaborativeFieldProps) {
  const [flash, setFlash] = useState(false);
  const prevValue = useRef(value);

  useEffect(() => {
    if (value !== prevValue.current && updatedBy) {
      setFlash(true);
      const timer = setTimeout(() => setFlash(false), 1500);
      prevValue.current = value;
      return () => clearTimeout(timer);
    }
    prevValue.current = value;
  }, [value, updatedBy]);

  const isLocked = !!lockedBy;
  const Tag = multiline ? "textarea" : "input";

  return (
    <div className="relative">
      {isLocked && (
        <div className="absolute -top-6 left-0 flex items-center gap-1 text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded">
          <Lock className="w-3 h-3" />
          Being edited by {lockedBy}
        </div>
      )}
      {updatedBy && flash && (
        <div className="absolute -top-6 right-0 flex items-center gap-1 text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded animate-pulse">
          <User className="w-3 h-3" />
          Updated by {updatedBy}
        </div>
      )}
      <Tag
        value={value}
        onChange={(e: any) => onChange(e.target.value)}
        disabled={isLocked}
        placeholder={placeholder}
        className={`w-full px-3 py-2 border rounded-lg transition-all duration-300 ${
          flash ? "ring-2 ring-blue-400 bg-blue-50" : ""
        } ${isLocked ? "bg-gray-100 cursor-not-allowed" : "bg-white"} ${className}`}
        rows={multiline ? 4 : undefined}
      />
    </div>
  );
}
