// ---- ErrorBoundary Component ---------------------------------------------
// Catches rendering errors in child components and displays a fallback UI.
// Prevents unhandled errors from crashing the entire application.
"use client";

import React, { Component, type ErrorInfo, type ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface ErrorBoundaryProps {
    children: ReactNode;
    /** Optional custom fallback UI */
    fallback?: ReactNode;
    /** Called when an error is caught */
    onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("[ErrorBoundary]", error, errorInfo);
        this.props.onError?.(error, errorInfo);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <Card className="border-destructive/30 bg-destructive/5 mx-auto max-w-lg mt-12">
                    <CardContent className="py-10 text-center space-y-4">
                        <div className="mx-auto w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center text-xl">
                            ⚠️
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-foreground">
                                Something went wrong
                            </h3>
                            <p className="text-sm text-muted-foreground mt-1">
                                An unexpected error occurred. Try refreshing or click below.
                            </p>
                        </div>
                        {process.env.NODE_ENV === "development" && this.state.error && (
                            <pre className="mt-4 text-xs text-left bg-muted/50 rounded-md p-3 overflow-x-auto max-h-40 text-destructive">
                                {this.state.error.message}
                                {"\n"}
                                {this.state.error.stack?.split("\n").slice(1, 5).join("\n")}
                            </pre>
                        )}
                        <div className="flex gap-2 justify-center pt-2">
                            <Button variant="outline" onClick={this.handleReset}>
                                Try Again
                            </Button>
                            <Button
                                variant="outline"
                                onClick={() => window.location.reload()}
                            >
                                Reload Page
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            );
        }

        return this.props.children;
    }
}
