interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry: () => void;
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: ErrorStateProps) {
  return (
    <section className="mx-auto mt-20 max-w-xl text-center" role="alert">
      <p className="text-xs font-semibold uppercase text-[#8a352d]">Helios</p>
      <h1 className="mt-3 text-2xl font-semibold text-[#171916]">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-[#666b64]">{message}</p>
      <button
        className="mt-6 rounded-md bg-[#171916] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#30332f] focus:outline-none focus:ring-2 focus:ring-[#216e4e]/30"
        type="button"
        onClick={onRetry}
      >
        Retry
      </button>
    </section>
  );
}
