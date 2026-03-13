import "@testing-library/jest-dom";

// Set test environment variables before any imports
process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000";
process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = "pk_test_mock";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(process.env as any).NODE_ENV = "test";

// Ensure localStorage is available for Zustand persist middleware
if (typeof globalThis.localStorage === "undefined") {
  const store: Record<string, string> = {};
  globalThis.localStorage = {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      Object.keys(store).forEach((k) => delete store[k]);
    },
    get length() {
      return Object.keys(store).length;
    },
    key: (index: number) => Object.keys(store)[index] ?? null,
  };
}

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    prefetch: vi.fn(),
    refresh: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
  useParams: () => ({}),
}));

// Mock @clerk/nextjs
vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: true,
    userId: "user_test_123",
    getToken: vi.fn().mockResolvedValue("mock-clerk-token"),
  }),
  useUser: () => ({
    isLoaded: true,
    user: {
      id: "user_test_123",
      firstName: "Test",
      lastName: "User",
      fullName: "Test User",
      emailAddresses: [{ emailAddress: "test@example.com" }],
    },
  }),
  ClerkProvider: ({ children }: { children: React.ReactNode }) => children,
  SignIn: () => null,
  SignUp: () => null,
}));
