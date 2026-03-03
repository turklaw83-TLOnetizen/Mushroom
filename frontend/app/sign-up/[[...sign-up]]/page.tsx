import { redirect } from "next/navigation";

// Sign-up is disabled — users are invited through the Clerk Dashboard.
// Redirect anyone hitting /sign-up to /sign-in.
export default function SignUpPage() {
    redirect("/sign-in");
}
