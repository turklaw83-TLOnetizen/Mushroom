// ---- Markdown Content Renderer -------------------------------------------
// Renders analysis text output with basic formatting.
// Handles markdown-like text (headers, bold, lists) from LLM output.
"use client";

import { useMemo } from "react";

interface MarkdownContentProps {
    content: string;
    className?: string;
}

export function MarkdownContent({ content, className }: MarkdownContentProps) {
    const html = useMemo(() => formatContent(content), [content]);

    return (
        <div
            className={`prose prose-sm dark:prose-invert max-w-none ${className ?? ""}`}
            dangerouslySetInnerHTML={{ __html: html }}
        />
    );
}

function escapeHtml(text: string): string {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function formatContent(text: string): string {
    if (!text) return "";

    const escaped = escapeHtml(text);
    const lines = escaped.split("\n");
    const output: string[] = [];
    let inList = false;

    for (const line of lines) {
        const trimmed = line.trim();

        // Headers
        if (trimmed.startsWith("### ")) {
            if (inList) { output.push("</ul>"); inList = false; }
            output.push(`<h4 class="text-sm font-semibold mt-4 mb-1">${trimmed.slice(4)}</h4>`);
            continue;
        }
        if (trimmed.startsWith("## ")) {
            if (inList) { output.push("</ul>"); inList = false; }
            output.push(`<h3 class="text-base font-semibold mt-5 mb-2">${trimmed.slice(3)}</h3>`);
            continue;
        }
        if (trimmed.startsWith("# ")) {
            if (inList) { output.push("</ul>"); inList = false; }
            output.push(`<h2 class="text-lg font-bold mt-6 mb-2">${trimmed.slice(2)}</h2>`);
            continue;
        }

        // List items
        if (/^[-*]\s/.test(trimmed) || /^\d+\.\s/.test(trimmed)) {
            if (!inList) { output.push('<ul class="list-disc list-inside space-y-1 my-2">'); inList = true; }
            const itemText = trimmed.replace(/^[-*]\s+/, "").replace(/^\d+\.\s+/, "");
            output.push(`<li class="text-sm leading-relaxed">${applyInline(itemText)}</li>`);
            continue;
        }

        // Empty line
        if (trimmed === "") {
            if (inList) { output.push("</ul>"); inList = false; }
            output.push("<br />");
            continue;
        }

        // Regular paragraph
        if (inList) { output.push("</ul>"); inList = false; }
        output.push(`<p class="text-sm leading-relaxed mb-2">${applyInline(trimmed)}</p>`);
    }

    if (inList) output.push("</ul>");
    return output.join("\n");
}

function applyInline(text: string): string {
    // Bold: **text** or __text__
    let result = text.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>');
    result = result.replace(/__(.+?)__/g, '<strong class="font-semibold">$1</strong>');
    // Italic: *text* or _text_
    result = result.replace(/\*([^*]+?)\*/g, "<em>$1</em>");
    result = result.replace(/_([^_]+?)_/g, "<em>$1</em>");
    // Code: `text`
    result = result.replace(/`([^`]+?)`/g, '<code class="bg-muted px-1 py-0.5 rounded text-xs">$1</code>');
    return result;
}
