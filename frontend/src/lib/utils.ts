import { clsx, type ClassValue } from "clsx";
import { type DependencyList, useEffect, useState } from "react";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function useLoader<T>(initialValue: T, load: () => Promise<T>, deps: DependencyList) {
  const [value, setValue] = useState<T>(initialValue);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const reload = async (): Promise<T> => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await load();
      setValue(result);
      return result;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let ignore = false;

    setIsLoading(true);
    setError(null);
    void load()
      .then((result) => {
        if (!ignore) {
          setValue(result);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(err);
        }
      })
      .finally(() => {
        if (!ignore) {
          setIsLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return [value, isLoading, error, reload] as const;
}
