/** Dark-mode toggle: follows the OS by default, remembers an explicit choice. */

import { useEffect, useState } from "react";

const STORAGE_KEY = "jars-theme";

function initialDark(): boolean {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "dark") return true;
  if (saved === "light") return false;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

export function useDarkMode(): [boolean, () => void] {
  const [dark, setDark] = useState<boolean>(initialDark);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem(STORAGE_KEY, dark ? "dark" : "light");
  }, [dark]);

  return [dark, () => setDark((d) => !d)];
}
