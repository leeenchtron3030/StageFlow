const releaseDetails = [
  ["Architecture Release", "AR-1.2"],
  ["Engineering Directive", "ED-0003"],
  ["Backend Status", "Not Connected"],
] as const;

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <section className="mx-auto flex min-h-screen w-full max-w-5xl flex-col justify-center px-6 py-16">
        <p className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
          Frontend Foundation
        </p>
        <h1 className="mt-4 text-5xl font-semibold tracking-normal">StageFlow</h1>
        <dl className="mt-10 grid gap-4 sm:grid-cols-3">
          {releaseDetails.map(([label, value]) => (
            <div className="border border-border bg-surface p-4" key={label}>
              <dt className="text-sm text-muted-foreground">{label}</dt>
              <dd className="mt-2 text-lg font-medium">{value}</dd>
            </div>
          ))}
        </dl>
      </section>
    </main>
  );
}
