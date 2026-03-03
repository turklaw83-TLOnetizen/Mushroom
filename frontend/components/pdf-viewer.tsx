// ---- Enhanced Document Viewer Component ------------------------------------
// Supports PDFs (iframe), images (img tag), text files (pre block), and
// fallback download for other types. Includes toolbar with zoom, page nav,
// download, print, fullscreen. Annotation overlay with highlight/note markers.
"use client";

import { useState, useCallback, useRef } from "react";
import { useAuth } from "@clerk/nextjs";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { isDevAuthMode, getDevToken } from "@/lib/dev-auth";
import { cn } from "@/lib/utils";
import {
    ZoomInIcon,
    ZoomOutIcon,
    ChevronLeftIcon,
    ChevronRightIcon,
    DownloadIcon,
    PrinterIcon,
    MaximizeIcon,
    MinimizeIcon,
    HighlighterIcon,
    XIcon,
    MessageSquareIcon,
    StickyNoteIcon,
    PanelRightOpenIcon,
    PanelRightCloseIcon,
    FileTextIcon,
    ImageIcon,
    FileIcon,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---- Types ----------------------------------------------------------------

interface PdfViewerProps {
    /** Case ID for file path */
    caseId: string;
    /** Filename to view */
    filename: string;
    /** Trigger button label (optional, defaults to filename) */
    label?: string;
    /** Optional className override for the trigger button */
    triggerClassName?: string;
    /** Optional icon override for the trigger button (replaces file-type icon) */
    triggerIcon?: React.ComponentType<{ className?: string }>;
}

interface Annotation {
    id: number;
    x: number; // percentage-based position (0-100)
    y: number; // percentage-based position (0-100)
    text: string;
}

type FileCategory = "pdf" | "image" | "text" | "other";

// ---- Helpers --------------------------------------------------------------

const IMAGE_EXTENSIONS = new Set([".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"]);
const TEXT_EXTENSIONS = new Set([".txt", ".md", ".csv", ".log", ".json", ".xml", ".yaml", ".yml"]);

function getFileCategory(filename: string): FileCategory {
    const ext = filename.toLowerCase().slice(filename.lastIndexOf("."));
    if (ext === ".pdf") return "pdf";
    if (IMAGE_EXTENSIONS.has(ext)) return "image";
    if (TEXT_EXTENSIONS.has(ext)) return "text";
    return "other";
}

function getFileIcon(category: FileCategory) {
    switch (category) {
        case "pdf":
            return FileTextIcon;
        case "image":
            return ImageIcon;
        case "text":
            return FileTextIcon;
        default:
            return FileIcon;
    }
}

const ZOOM_LEVELS = [50, 75, 100, 125, 150, 200, 300];
const DEFAULT_ZOOM_INDEX = 2; // 100%

// ---- Component ------------------------------------------------------------

export function PdfViewer({ caseId, filename, label, triggerClassName, triggerIcon }: PdfViewerProps) {
    const [open, setOpen] = useState(false);
    const { getToken } = useAuth();
    const [fileUrl, setFileUrl] = useState<string | null>(null);
    const [fileBlob, setFileBlob] = useState<Blob | null>(null);
    const [textContent, setTextContent] = useState<string | null>(null);
    const [zoomIndex, setZoomIndex] = useState(DEFAULT_ZOOM_INDEX);
    const [currentPage, setCurrentPage] = useState(1);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [highlightMode, setHighlightMode] = useState(false);
    const [annotations, setAnnotations] = useState<Annotation[]>([]);
    const [activeAnnotation, setActiveAnnotation] = useState<number | null>(null);
    const [newNoteText, setNewNoteText] = useState("");
    const [pendingAnnotation, setPendingAnnotation] = useState<{ x: number; y: number } | null>(null);
    const [showAnnotationPanel, setShowAnnotationPanel] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const viewerRef = useRef<HTMLDivElement>(null);
    const dialogRef = useRef<HTMLDivElement>(null);
    const annotationIdRef = useRef(0);

    const fileCategory = getFileCategory(filename);
    const zoom = ZOOM_LEVELS[zoomIndex];

    // ---- File loading -------------------------------------------------------

    const handleOpen = async () => {
        try {
            setError(null);
            let token = await getToken();
            if (!token && isDevAuthMode()) {
                token = await getDevToken();
            }
            const res = await fetch(
                `${API_BASE}/api/v1/cases/${caseId}/files/${encodeURIComponent(filename)}`,
                { headers: { Authorization: `Bearer ${token}` } },
            );
            if (!res.ok) throw new Error("Failed to load file");
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            setFileBlob(blob);
            setFileUrl(url);
            setOpen(true);

            // For text files, also extract text content
            if (fileCategory === "text") {
                const text = await blob.text();
                setTextContent(text);
            }
        } catch {
            setError("Failed to load file. Please try again.");
            setFileUrl(null);
            setFileBlob(null);
        }
    };

    const handleClose = () => {
        setOpen(false);
        if (fileUrl) {
            URL.revokeObjectURL(fileUrl);
            setFileUrl(null);
        }
        setFileBlob(null);
        setTextContent(null);
        setZoomIndex(DEFAULT_ZOOM_INDEX);
        setCurrentPage(1);
        setIsFullscreen(false);
        setHighlightMode(false);
        setAnnotations([]);
        setActiveAnnotation(null);
        setPendingAnnotation(null);
        setShowAnnotationPanel(false);
        setError(null);
    };

    // ---- Zoom controls ------------------------------------------------------

    const handleZoomIn = useCallback(() => {
        setZoomIndex((prev) => Math.min(prev + 1, ZOOM_LEVELS.length - 1));
    }, []);

    const handleZoomOut = useCallback(() => {
        setZoomIndex((prev) => Math.max(prev - 1, 0));
    }, []);

    // ---- Page navigation ----------------------------------------------------

    const handlePrevPage = useCallback(() => {
        setCurrentPage((prev) => Math.max(prev - 1, 1));
    }, []);

    const handleNextPage = useCallback(() => {
        setCurrentPage((prev) => prev + 1);
    }, []);

    // ---- Download & Print ---------------------------------------------------

    const handleDownload = useCallback(() => {
        if (!fileUrl) return;
        const a = document.createElement("a");
        a.href = fileUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }, [fileUrl, filename]);

    const handlePrint = useCallback(() => {
        if (!fileUrl) return;
        const printWindow = window.open(fileUrl, "_blank");
        if (printWindow) {
            printWindow.addEventListener("load", () => {
                printWindow.print();
            });
        }
    }, [fileUrl]);

    // ---- Fullscreen ---------------------------------------------------------

    const handleFullscreen = useCallback(() => {
        if (!dialogRef.current) return;
        if (!isFullscreen) {
            dialogRef.current.requestFullscreen?.().catch(() => {});
            setIsFullscreen(true);
        } else {
            document.exitFullscreen?.().catch(() => {});
            setIsFullscreen(false);
        }
    }, [isFullscreen]);

    // ---- Annotations --------------------------------------------------------

    const handleViewerClick = useCallback(
        (e: React.MouseEvent<HTMLDivElement>) => {
            if (!highlightMode) return;
            const rect = e.currentTarget.getBoundingClientRect();
            const x = ((e.clientX - rect.left) / rect.width) * 100;
            const y = ((e.clientY - rect.top) / rect.height) * 100;
            setPendingAnnotation({ x, y });
            setNewNoteText("");
        },
        [highlightMode],
    );

    const handleSaveAnnotation = useCallback(() => {
        if (!pendingAnnotation || !newNoteText.trim()) return;
        annotationIdRef.current += 1;
        const newAnnotation: Annotation = {
            id: annotationIdRef.current,
            x: pendingAnnotation.x,
            y: pendingAnnotation.y,
            text: newNoteText.trim(),
        };
        setAnnotations((prev) => [...prev, newAnnotation]);
        setPendingAnnotation(null);
        setNewNoteText("");
        setShowAnnotationPanel(true);
    }, [pendingAnnotation, newNoteText]);

    const handleCancelAnnotation = useCallback(() => {
        setPendingAnnotation(null);
        setNewNoteText("");
    }, []);

    const handleDeleteAnnotation = useCallback((id: number) => {
        setAnnotations((prev) => prev.filter((a) => a.id !== id));
        setActiveAnnotation(null);
    }, []);

    const handleAnnotationMarkerClick = useCallback(
        (id: number, e: React.MouseEvent) => {
            e.stopPropagation();
            setActiveAnnotation((prev) => (prev === id ? null : id));
        },
        [],
    );

    // ---- Build the PDF/iframe URL with zoom + page params -------------------

    const getViewerUrl = useCallback(() => {
        if (!fileUrl || fileCategory !== "pdf") return fileUrl;
        return `${fileUrl}#zoom=${zoom}&page=${currentPage}`;
    }, [fileUrl, fileCategory, zoom, currentPage]);

    // ---- Render file content based on type ----------------------------------

    const renderContent = () => {
        if (error) {
            return (
                <div className="flex items-center justify-center h-full text-destructive text-sm">
                    {error}
                </div>
            );
        }

        if (!fileUrl) {
            return (
                <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                    Loading...
                </div>
            );
        }

        switch (fileCategory) {
            case "pdf":
                return (
                    <iframe
                        src={getViewerUrl() || ""}
                        className="w-full h-full border-0"
                        title={filename}
                    />
                );

            case "image":
                return (
                    <div className="flex items-center justify-center h-full overflow-auto p-4 bg-muted/30">
                        <img
                            src={fileUrl}
                            alt={filename}
                            className="max-w-none"
                            style={{
                                width: `${zoom}%`,
                                height: "auto",
                                imageRendering: zoom > 200 ? "pixelated" : "auto",
                            }}
                        />
                    </div>
                );

            case "text":
                return (
                    <div className="h-full overflow-auto p-4 bg-muted/20">
                        <pre
                            className="whitespace-pre-wrap font-mono text-sm leading-relaxed"
                            style={{ fontSize: `${zoom / 100}em` }}
                        >
                            {textContent ?? "Loading..."}
                        </pre>
                    </div>
                );

            case "other":
                return (
                    <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground">
                        <FileIcon className="size-16 opacity-40" />
                        <p className="text-sm">
                            Preview is not available for this file type.
                        </p>
                        <Button variant="outline" size="sm" onClick={handleDownload}>
                            <DownloadIcon className="size-4 mr-2" />
                            Download {filename}
                        </Button>
                    </div>
                );
        }
    };

    // ---- Toolbar ------------------------------------------------------------

    const renderToolbar = () => {
        const supportsZoom = fileCategory === "pdf" || fileCategory === "image" || fileCategory === "text";
        const supportsPages = fileCategory === "pdf";
        const supportsPrint = fileCategory === "pdf" || fileCategory === "image";
        const supportsAnnotations = fileCategory === "pdf" || fileCategory === "image";

        return (
            <div className="flex items-center gap-1 px-3 py-1.5 border-b bg-muted/30 shrink-0 flex-wrap">
                {/* Zoom controls */}
                {supportsZoom && (
                    <div className="flex items-center gap-0.5 mr-2">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="size-7"
                            onClick={handleZoomOut}
                            disabled={zoomIndex === 0}
                            title="Zoom out"
                        >
                            <ZoomOutIcon className="size-3.5" />
                        </Button>
                        <span className="text-xs w-10 text-center tabular-nums text-muted-foreground">
                            {zoom}%
                        </span>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="size-7"
                            onClick={handleZoomIn}
                            disabled={zoomIndex === ZOOM_LEVELS.length - 1}
                            title="Zoom in"
                        >
                            <ZoomInIcon className="size-3.5" />
                        </Button>
                    </div>
                )}

                {/* Page navigation (PDF only) */}
                {supportsPages && (
                    <div className="flex items-center gap-0.5 mr-2 border-l pl-2">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="size-7"
                            onClick={handlePrevPage}
                            disabled={currentPage <= 1}
                            title="Previous page"
                        >
                            <ChevronLeftIcon className="size-3.5" />
                        </Button>
                        <span className="text-xs tabular-nums text-muted-foreground min-w-[3rem] text-center">
                            Page {currentPage}
                        </span>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="size-7"
                            onClick={handleNextPage}
                            title="Next page"
                        >
                            <ChevronRightIcon className="size-3.5" />
                        </Button>
                    </div>
                )}

                {/* Spacer */}
                <div className="flex-1" />

                {/* Annotation controls */}
                {supportsAnnotations && (
                    <div className="flex items-center gap-0.5 mr-2">
                        <Button
                            variant={highlightMode ? "default" : "ghost"}
                            size="sm"
                            className={cn(
                                "h-7 text-xs gap-1",
                                highlightMode && "bg-amber-500 hover:bg-amber-600 text-white",
                            )}
                            onClick={() => setHighlightMode(!highlightMode)}
                            title={highlightMode ? "Disable highlight mode" : "Enable highlight mode"}
                        >
                            <HighlighterIcon className="size-3.5" />
                            {highlightMode ? "Done" : "Highlight"}
                        </Button>
                        <Button
                            variant={showAnnotationPanel ? "default" : "ghost"}
                            size="icon"
                            className="size-7"
                            onClick={() => setShowAnnotationPanel(!showAnnotationPanel)}
                            title={showAnnotationPanel ? "Hide annotations" : "Show annotations"}
                        >
                            {showAnnotationPanel ? (
                                <PanelRightCloseIcon className="size-3.5" />
                            ) : (
                                <PanelRightOpenIcon className="size-3.5" />
                            )}
                        </Button>
                        {annotations.length > 0 && (
                            <span className="text-xs text-muted-foreground ml-1">
                                {annotations.length} note{annotations.length !== 1 ? "s" : ""}
                            </span>
                        )}
                    </div>
                )}

                {/* Download */}
                <Button
                    variant="ghost"
                    size="icon"
                    className="size-7"
                    onClick={handleDownload}
                    title="Download file"
                >
                    <DownloadIcon className="size-3.5" />
                </Button>

                {/* Print */}
                {supportsPrint && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="size-7"
                        onClick={handlePrint}
                        title="Print"
                    >
                        <PrinterIcon className="size-3.5" />
                    </Button>
                )}

                {/* Fullscreen */}
                <Button
                    variant="ghost"
                    size="icon"
                    className="size-7"
                    onClick={handleFullscreen}
                    title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
                >
                    {isFullscreen ? (
                        <MinimizeIcon className="size-3.5" />
                    ) : (
                        <MaximizeIcon className="size-3.5" />
                    )}
                </Button>
            </div>
        );
    };

    // ---- Annotation overlay -------------------------------------------------

    const renderAnnotationOverlay = () => {
        if (fileCategory !== "pdf" && fileCategory !== "image") return null;

        return (
            <div
                className={cn(
                    "absolute inset-0 pointer-events-none",
                    highlightMode && "pointer-events-auto cursor-crosshair",
                )}
                onClick={handleViewerClick}
            >
                {/* Existing annotation markers */}
                {annotations.map((ann, idx) => (
                    <div
                        key={ann.id}
                        className="absolute pointer-events-auto"
                        style={{
                            left: `${ann.x}%`,
                            top: `${ann.y}%`,
                            transform: "translate(-50%, -50%)",
                        }}
                    >
                        {/* Numbered marker */}
                        <button
                            className={cn(
                                "size-6 rounded-full flex items-center justify-center text-xs font-bold",
                                "bg-amber-500 text-white shadow-md hover:bg-amber-600",
                                "transition-transform hover:scale-110",
                                activeAnnotation === ann.id && "ring-2 ring-amber-300 scale-110",
                            )}
                            onClick={(e) => handleAnnotationMarkerClick(ann.id, e)}
                            title={ann.text}
                        >
                            {idx + 1}
                        </button>
                        {/* Popover for active annotation */}
                        {activeAnnotation === ann.id && (
                            <div className="absolute top-8 left-1/2 -translate-x-1/2 bg-popover border rounded-md shadow-lg p-2 min-w-[160px] max-w-[250px] z-50">
                                <p className="text-xs text-foreground whitespace-pre-wrap break-words">
                                    {ann.text}
                                </p>
                                <div className="flex justify-end mt-1.5">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-5 text-[10px] text-destructive hover:text-destructive"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleDeleteAnnotation(ann.id);
                                        }}
                                    >
                                        Delete
                                    </Button>
                                </div>
                            </div>
                        )}
                    </div>
                ))}

                {/* Pending annotation input */}
                {pendingAnnotation && (
                    <div
                        className="absolute pointer-events-auto z-50"
                        style={{
                            left: `${pendingAnnotation.x}%`,
                            top: `${pendingAnnotation.y}%`,
                            transform: "translate(-50%, 8px)",
                        }}
                    >
                        <div className="bg-popover border rounded-md shadow-lg p-2 min-w-[200px]">
                            <textarea
                                className="w-full text-xs border rounded p-1.5 resize-none bg-background text-foreground"
                                rows={3}
                                placeholder="Add a note..."
                                value={newNoteText}
                                onChange={(e) => setNewNoteText(e.target.value)}
                                autoFocus
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                                        handleSaveAnnotation();
                                    }
                                    if (e.key === "Escape") {
                                        handleCancelAnnotation();
                                    }
                                }}
                            />
                            <div className="flex justify-end gap-1 mt-1">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 text-xs"
                                    onClick={handleCancelAnnotation}
                                >
                                    Cancel
                                </Button>
                                <Button
                                    variant="default"
                                    size="sm"
                                    className="h-6 text-xs"
                                    onClick={handleSaveAnnotation}
                                    disabled={!newNoteText.trim()}
                                >
                                    Save
                                </Button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        );
    };

    // ---- Annotations sidebar panel ------------------------------------------

    const renderAnnotationPanel = () => {
        if (!showAnnotationPanel) return null;

        return (
            <div className="w-64 border-l shrink-0 flex flex-col bg-muted/10 overflow-hidden">
                <div className="flex items-center justify-between px-3 py-2 border-b">
                    <div className="flex items-center gap-1.5">
                        <StickyNoteIcon className="size-3.5 text-muted-foreground" />
                        <span className="text-xs font-medium">Annotations</span>
                    </div>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="size-6"
                        onClick={() => setShowAnnotationPanel(false)}
                    >
                        <XIcon className="size-3" />
                    </Button>
                </div>
                <div className="flex-1 overflow-y-auto">
                    {annotations.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-4 gap-2">
                            <MessageSquareIcon className="size-8 opacity-30" />
                            <p className="text-xs text-center">
                                No annotations yet.
                                {fileCategory === "pdf" || fileCategory === "image"
                                    ? " Click the Highlight button and click on the document to add notes."
                                    : ""}
                            </p>
                        </div>
                    ) : (
                        <div className="divide-y">
                            {annotations.map((ann, idx) => (
                                <div
                                    key={ann.id}
                                    className={cn(
                                        "px-3 py-2 cursor-pointer hover:bg-muted/50 transition-colors",
                                        activeAnnotation === ann.id && "bg-amber-50 dark:bg-amber-950/20",
                                    )}
                                    onClick={() =>
                                        setActiveAnnotation((prev) =>
                                            prev === ann.id ? null : ann.id,
                                        )
                                    }
                                >
                                    <div className="flex items-start gap-2">
                                        <span className="size-5 rounded-full bg-amber-500 text-white flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">
                                            {idx + 1}
                                        </span>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs text-foreground line-clamp-3 break-words">
                                                {ann.text}
                                            </p>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="size-5 shrink-0 opacity-0 group-hover:opacity-100 hover:opacity-100"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleDeleteAnnotation(ann.id);
                                            }}
                                        >
                                            <XIcon className="size-3 text-destructive" />
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        );
    };

    // ---- Main render --------------------------------------------------------

    const FileIconComponent = getFileIcon(fileCategory);
    const TriggerIconComponent = triggerIcon || FileIconComponent;

    return (
        <>
            <Button
                variant="ghost"
                size="sm"
                className={triggerClassName || "text-xs truncate max-w-[200px]"}
                onClick={handleOpen}
                title={`Preview ${filename}`}
            >
                <TriggerIconComponent className="size-3.5 mr-1 shrink-0" />
                {label || filename}
            </Button>

            <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
                <DialogContent
                    ref={dialogRef}
                    className={cn(
                        "max-w-5xl h-[85vh] p-0 gap-0 flex flex-col",
                        isFullscreen && "max-w-none h-screen rounded-none",
                    )}
                >
                    <DialogHeader className="p-3 pb-0 shrink-0">
                        <DialogTitle className="text-sm truncate flex items-center gap-2">
                            <FileIconComponent className="size-4 shrink-0 text-muted-foreground" />
                            {filename}
                        </DialogTitle>
                    </DialogHeader>

                    {/* Toolbar */}
                    {renderToolbar()}

                    {/* Content area with optional annotation panel */}
                    <div className="flex-1 min-h-0 flex">
                        {/* Main viewer area */}
                        <div className="flex-1 min-w-0 relative" ref={viewerRef}>
                            {renderContent()}
                            {renderAnnotationOverlay()}
                        </div>

                        {/* Annotations sidebar */}
                        {renderAnnotationPanel()}
                    </div>
                </DialogContent>
            </Dialog>
        </>
    );
}
