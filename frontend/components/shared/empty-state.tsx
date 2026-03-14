// ---- Empty State Component ------------------------------------------------
// Reusable empty state card used across all pages when a list has no items.
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface EmptyStateProps {
    icon: string;
    title: string;
    description: string;
    action?: { label: string; onClick: () => void };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
    return (
        <Card className="border-dashed">
            <CardContent className="py-12 text-center">
                <div className="mx-auto w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
                    <span className="text-xl" aria-hidden="true">{icon}</span>
                </div>
                <p className="text-sm font-medium">{title}</p>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">{description}</p>
                {action && (
                    <Button variant="outline" size="sm" className="mt-3" onClick={action.onClick}>
                        {action.label}
                    </Button>
                )}
            </CardContent>
        </Card>
    );
}
