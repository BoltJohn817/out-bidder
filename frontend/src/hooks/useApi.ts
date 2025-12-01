import { useCallback, useState } from 'react';
import api from '../api/client';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

interface UseApiReturn<T> extends UseApiState<T> {
  execute: (...args: any[]) => Promise<T | null>;
  reset: () => void;
}

/**
 * Hook for making API calls with loading and error state management.
 * 
 * @param apiCall - Function that returns a promise from an API call
 * @returns Object with data, loading, error, execute, and reset
 */
export function useApi<T = any>(
  apiCall: (...args: any[]) => Promise<{ data: T }>
): UseApiReturn<T> {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: false,
    error: null,
  });

  const execute = useCallback(
    async (...args: any[]): Promise<T | null> => {
      setState({ data: null, loading: true, error: null });
      try {
        const response = await apiCall(...args);
        setState({ data: response.data, loading: false, error: null });
        return response.data;
      } catch (err: any) {
        const errorMessage = err?.response?.data?.message ?? 'An error occurred';
        setState({ data: null, loading: false, error: errorMessage });
        return null;
      }
    },
    [apiCall]
  );

  const reset = useCallback(() => {
    setState({ data: null, loading: false, error: null });
  }, []);

  return {
    ...state,
    execute,
    reset,
  };
}

/**
 * Hook for simple API GET requests.
 */
export function useApiGet<T = any>(endpoint: string) {
  return useApi<T>(() => api.get<T>(endpoint));
}

/**
 * Hook for API POST requests.
 */
export function useApiPost<T = any, P = any>(endpoint: string) {
  return useApi<T>((payload: P) => api.post<T>(endpoint, payload));
}

