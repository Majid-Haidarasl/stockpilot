import { QueryClient } from "@tanstack/react-query";
import { setupMediaUrlRevocation } from "../shared/query/mediaCache";

export function createQueryClient(): QueryClient {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
  setupMediaUrlRevocation(client);
  return client;
}
