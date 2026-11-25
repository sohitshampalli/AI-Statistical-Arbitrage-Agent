import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export interface TopBarInfo {
  runId?: string | null;
  data?: "real" | "synthetic" | "mixed" | null;
}

const Ctx = createContext<{ info: TopBarInfo; set: (info: TopBarInfo) => void } | null>(null);

export function TopBarProvider({ children }: { children: ReactNode }) {
  const [info, set] = useState<TopBarInfo>({});
  return <Ctx.Provider value={{ info, set }}>{children}</Ctx.Provider>;
}

export function useTopBarInfo(): TopBarInfo {
  return useContext(Ctx)?.info ?? {};
}

/** A page states which run it shows and whether its data is real or synthetic. */
export function useTopBar(info: TopBarInfo): void {
  const ctx = useContext(Ctx);
  const set = ctx?.set;
  const key = JSON.stringify(info);
  useEffect(() => {
    set?.(JSON.parse(key) as TopBarInfo);
  }, [set, key]);
}
