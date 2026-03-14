"use client";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";

interface NavCounts {
  tasks: number;
  comms: number;
  notifications: number;
}

export function useNavCounts() {
  const { getToken } = useAuth();

  return useQuery<NavCounts>({
    queryKey: ["nav-counts"],
    queryFn: async () => {
      // Fetch counts in parallel, with fallbacks
      const results = await Promise.allSettled([
        api.get("/tasks?status=pending&per_page=1", { getToken }),
        api.get("/comms?status=unread&per_page=1", { getToken }),
      ]);

      return {
        tasks: results[0].status === "fulfilled" ? (results[0].value as any)?.total ?? 0 : 0,
        comms: results[1].status === "fulfilled" ? (results[1].value as any)?.total ?? 0 : 0,
        notifications: 0,
      };
    },
    staleTime: 60_000, // 1 minute
    refetchInterval: 60_000, // Refetch every minute
    retry: false,
  });
}
