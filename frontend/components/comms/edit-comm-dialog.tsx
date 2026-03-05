// ---- Edit Communication Dialog -------------------------------------------
// Allows attorney to edit email body + SMS text before approving.
"use client";

import { useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import type { CommQueueItem } from "@/types/api";

interface EditCommDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    item: CommQueueItem | null;
    onApprove: (commId: string, editedBody: string, editedSms: string) => void;
    isLoading?: boolean;
}

export function EditCommDialog({
    open,
    onOpenChange,
    item,
    onApprove,
    isLoading,
}: EditCommDialogProps) {
    const [subject, setSubject] = useState("");
    const [body, setBody] = useState("");
    const [sms, setSms] = useState("");

    // Sync state when item changes
    const handleOpenChange = (isOpen: boolean) => {
        if (isOpen && item) {
            setSubject(item.subject);
            setBody(item.body_html);
            setSms(item.body_sms);
        }
        onOpenChange(isOpen);
    };

    if (!item) return null;

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        Edit Communication
                        <Badge variant="outline" className="text-[10px]">
                            {item.trigger_type.replace(/_/g, " ")}
                        </Badge>
                    </DialogTitle>
                    <DialogDescription>
                        Edit the message before approving. To: {item.metadata?.client_name || "Client"}
                        {item.metadata?.client_email ? ` (${item.metadata.client_email})` : ""}
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-2">
                    {/* Subject */}
                    <div className="space-y-1.5">
                        <label htmlFor="comm-subject" className="text-xs font-medium">
                            Subject
                        </label>
                        <Input
                            id="comm-subject"
                            value={subject}
                            onChange={(e) => setSubject(e.target.value)}
                            placeholder="Email subject line"
                        />
                    </div>

                    {/* Email Body */}
                    <div className="space-y-1.5">
                        <label htmlFor="comm-body" className="text-xs font-medium">
                            Email Body
                        </label>
                        <textarea
                            id="comm-body"
                            value={body}
                            onChange={(e) => setBody(e.target.value)}
                            placeholder="Email body content..."
                            rows={10}
                            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        />
                    </div>

                    {/* SMS Text */}
                    <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                            <label htmlFor="comm-sms" className="text-xs font-medium">
                                SMS Text
                            </label>
                            <span className={`text-[10px] ${sms.length > 160 ? "text-destructive" : "text-muted-foreground"}`}>
                                {sms.length}/160
                            </span>
                        </div>
                        <textarea
                            id="comm-sms"
                            value={sms}
                            onChange={(e) => setSms(e.target.value)}
                            placeholder="SMS message text..."
                            rows={3}
                            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        />
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="ghost" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={() => onApprove(item.id, body, sms)}
                        disabled={isLoading || !body.trim()}
                    >
                        {isLoading ? "Saving..." : "Save & Approve"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
