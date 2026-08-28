import { useState, useEffect } from 'react';

export function usePollingApi<T>(endpoint: string, intervalMs: number = 5000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    
    const fetchData = async () => {
      try {
        const response = await fetch(`/api${endpoint}`);
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }
        const result = await response.json();
        if (isMounted) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (isMounted) {
          setError(err as Error);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchData();
    const interval = setInterval(fetchData, intervalMs);
    
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [endpoint, intervalMs]);

  return { data, error, isLoading };
}
