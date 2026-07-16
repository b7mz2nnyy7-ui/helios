import type { ReactNode } from "react";

interface AppShellProps {
  children: ReactNode;
  searchValue: string;
  onSearchChange: (value: string) => void;
}

const navigation = ["Videos", "Missions", "Agents", "Settings"];

export function AppShell({
  children,
  searchValue,
  onSearchChange,
}: AppShellProps) {
  return (
    <div className="min-h-screen bg-[#f7f8f6] text-[#171916]">
      <header className="fixed inset-x-0 top-0 z-30 flex h-[72px] items-center border-b border-[#dedfd9] bg-white px-5 md:px-7">
        <a
          className="flex shrink-0 items-center gap-3 md:w-[220px]"
          href="/videos"
        >
          <span className="grid size-8 place-items-center rounded-md bg-[#171916] text-sm font-semibold text-white">
            H
          </span>
          <span className="hidden text-sm font-semibold uppercase sm:inline">
            Helios
          </span>
        </a>
        <div className="mx-3 w-full max-w-[540px] sm:mx-5 md:mx-auto">
          <label className="sr-only" htmlFor="video-search">
            Search videos
          </label>
          <input
            id="video-search"
            className="h-10 w-full rounded-md border border-[#d9dbd5] bg-[#f7f8f6] px-4 text-sm outline-none transition focus:border-[#216e4e] focus:bg-white focus:ring-2 focus:ring-[#216e4e]/10"
            type="search"
            placeholder="Search productions"
            value={searchValue}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </div>
        <button
          className="grid size-9 shrink-0 place-items-center rounded-full bg-[#e9efe9] text-sm font-semibold text-[#24543e] md:ml-5"
          type="button"
          title="User account"
          aria-label="User account"
        >
          DB
        </button>
      </header>

      <aside className="fixed bottom-0 left-0 top-[72px] hidden w-[240px] border-r border-[#dedfd9] bg-white px-4 py-7 md:block">
        <nav aria-label="Primary navigation">
          <ul className="space-y-1">
            {navigation.map((item) => {
              const active = item === "Videos";
              return (
                <li key={item}>
                  <a
                    className={`flex h-10 items-center rounded-md px-3 text-sm font-medium transition ${
                      active
                        ? "bg-[#edf2ed] text-[#1d5138]"
                        : "text-[#666b64] hover:bg-[#f5f6f3] hover:text-[#20231f]"
                    }`}
                    href={`/${item.toLowerCase()}`}
                    aria-current={active ? "page" : undefined}
                  >
                    {item}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>

      <main className="min-h-screen pt-[72px] md:pl-[240px]">
        <div className="mx-auto max-w-[1560px] px-5 py-8 md:px-10 md:py-11 xl:px-14">
          {children}
        </div>
      </main>
    </div>
  );
}
