import type { ReactNode } from "react";

export function Page({ children }: { children: ReactNode }) {
  return <div className="h-full overflow-y-auto"><div className="mx-auto max-w-[1500px] p-5">{children}</div></div>;
}
