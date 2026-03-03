import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
    return (
        <div className="flex min-h-screen">
            {/* Left panel: branding (hidden on mobile) */}
            <div className="hidden lg:flex lg:w-1/2 flex-col justify-center items-center relative overflow-hidden bg-[oklch(0.14_0.01_264)]">
                {/* Decorative blur orbs */}
                <div className="absolute top-1/4 left-1/4 w-72 h-72 rounded-full bg-[oklch(0.55_0.23_264_/_12%)] blur-3xl" />
                <div className="absolute bottom-1/3 right-1/4 w-56 h-56 rounded-full bg-[oklch(0.62_0.21_293_/_8%)] blur-3xl" />
                <div className="absolute top-2/3 left-1/2 w-40 h-40 rounded-full bg-[oklch(0.74_0.14_293_/_6%)] blur-3xl" />

                <div className="relative z-10 text-center px-8">
                    <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-[oklch(0.55_0.23_264)] text-white font-extrabold text-3xl mx-auto mb-8 shadow-lg shadow-[oklch(0.55_0.23_264_/_30%)]">
                        MC
                    </div>
                    <h1 className="text-4xl font-extrabold text-white tracking-tight">
                        Project Mushroom Cloud
                    </h1>
                    <p className="text-lg text-white/50 mt-4 max-w-md leading-relaxed">
                        AI-powered legal intelligence — case analysis, strategy, and document management.
                    </p>
                    <div className="h-1 w-28 mx-auto mt-10 rounded-full bg-gradient-to-r from-[oklch(0.55_0.23_264)] to-[oklch(0.74_0.14_293)]" />
                </div>
            </div>

            {/* Right panel: sign-in form */}
            <div className="flex flex-1 items-center justify-center bg-background px-4">
                <div className="w-full max-w-md">
                    {/* Mobile-only branding */}
                    <div className="lg:hidden text-center mb-8">
                        <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary text-primary-foreground font-bold text-xl mx-auto mb-4">
                            MC
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight">
                            Project Mushroom Cloud
                        </h1>
                        <p className="text-sm text-muted-foreground mt-1">
                            Legal Intelligence Suite
                        </p>
                    </div>
                    <SignIn
                        fallbackRedirectUrl="/"
                        appearance={{
                            elements: {
                                rootBox: "mx-auto w-full",
                                card: "shadow-xl border border-border rounded-2xl",
                            },
                        }}
                    />
                </div>
            </div>
        </div>
    );
}
