export function EmptyState() {
  return (
    <section className="flex min-h-[620px] flex-col items-center justify-center text-center">
      <img
        className="aspect-video w-full max-w-[520px] rounded-lg border border-[#d9dbd5] object-cover shadow-[0_18px_50px_rgba(35,40,34,0.08)]"
        src="/poster-placeholder.png"
        alt=""
      />
      <h2 className="mt-9 text-2xl font-semibold text-[#1d201c]">
        Your AI productions will appear here.
      </h2>
      <a
        className="mt-6 inline-flex h-11 items-center rounded-md bg-[#1d5138] px-5 text-sm font-semibold text-white transition hover:bg-[#173f2c] focus:outline-none focus:ring-2 focus:ring-[#216e4e]/30"
        href="/missions"
      >
        Create Mission
      </a>
    </section>
  );
}
