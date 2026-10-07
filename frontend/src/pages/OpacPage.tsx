import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { opac } from "../api/endpoints";
import { Button, Card, DataTable, ErrorText, Input, PageHeader } from "../components/ui";

export function OpacPage() {
  const [form, setForm] = useState({ q: "", author: "", year_from: "", available: false });
  const [query, setQuery] = useState(form);
  const [page, setPage] = useState(1);
  const { data, isFetching, error } = useQuery({
    queryKey: ["opac", query, page],
    queryFn: () =>
      opac.search({
        q: query.q,
        author: query.author,
        year_from: query.year_from ? Number(query.year_from) : undefined,
        available: query.available || undefined,
        page,
      }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setPage(1);
    setQuery(form);
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <PageHeader title="Library catalogue">
        <Link to="/login" className="text-sm text-indigo-700 hover:underline">
          Staff / patron sign in
        </Link>
      </PageHeader>
      <Card className="mb-4">
        <form onSubmit={submit} className="grid gap-3 md:grid-cols-[2fr_1fr_120px_auto_auto] md:items-end">
          <Input label="Search title, author, subject or ISBN" value={form.q} onChange={(e) => setForm({ ...form, q: e.target.value })} />
          <Input label="Author" value={form.author} onChange={(e) => setForm({ ...form, author: e.target.value })} />
          <Input label="From year" inputMode="numeric" value={form.year_from} onChange={(e) => setForm({ ...form, year_from: e.target.value })} />
          <label className="flex items-center gap-2 pb-2 text-sm">
            <input type="checkbox" checked={form.available} onChange={(e) => setForm({ ...form, available: e.target.checked })} />
            Available now
          </label>
          <Button type="submit">
            <Search size={14} aria-hidden /> Search
          </Button>
        </form>
      </Card>
      <ErrorText error={error} />
      <p className="mb-2 text-sm text-slate-500">{isFetching ? "Searching…" : `${data?.total ?? 0} records`}</p>
      <DataTable
        columns={["title", "author", "year", "publisher", "copies"]}
        rows={(data?.items ?? []).map((h) => [
          <span className="font-medium">{h.title}</span>,
          h.author ?? "—",
          h.pub_year ?? "—",
          h.publisher ?? "—",
          <span className={h.available_copies ? "text-green-700" : "text-slate-400"}>
            {h.available_copies} of {h.total_copies} available
          </span>,
        ])}
      />
      <div className="mt-3 flex items-center gap-2">
        <Button variant="secondary" disabled={page === 1} onClick={() => setPage(page - 1)}>
          Previous
        </Button>
        <Button variant="secondary" disabled={!data || page * data.size >= data.total} onClick={() => setPage(page + 1)}>
          Next
        </Button>
        <span className="ml-auto text-sm text-slate-500">
          Browse shelves:{" "}
          {["A-01", "A-02", "B-01", "B-02", "C-01", "C-02", "D-01", "D-02"].map((s) => (
            <Link key={s} to={`/opac/shelves/${s}`} className="mx-1 text-indigo-700 hover:underline">
              {s}
            </Link>
          ))}
        </span>
      </div>
    </div>
  );
}
