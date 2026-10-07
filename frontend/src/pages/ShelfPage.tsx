import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { opac } from "../api/endpoints";
import { ErrorText, PageHeader } from "../components/ui";

const SPINE_COLOURS = ["bg-indigo-700", "bg-emerald-700", "bg-amber-700", "bg-rose-700", "bg-sky-700", "bg-violet-700"];

/** Virtual bookshelf (FR 02): spines in call-number order, as they stand on the shelf. */
export function ShelfPage() {
  const { code = "" } = useParams();
  const { data, error } = useQuery({ queryKey: ["shelf", code], queryFn: () => opac.shelf(code) });

  return (
    <div className="mx-auto max-w-6xl p-6">
      <PageHeader title={`Shelf ${code}`}>
        <Link to="/opac" className="text-sm text-indigo-700 hover:underline">
          Back to search
        </Link>
      </PageHeader>
      <ErrorText error={error} />
      <div className="flex min-h-72 items-end gap-1 overflow-x-auto rounded-lg border-b-8 border-amber-900 bg-amber-50 p-4">
        {(data ?? []).map((s, i) => (
          <div
            key={s.item_id}
            title={`${s.title} — ${s.author ?? "unknown"} (${s.call_no ?? ""})`}
            className={`flex h-64 w-10 shrink-0 flex-col items-center justify-between rounded-sm py-2 text-white shadow ${
              SPINE_COLOURS[i % SPINE_COLOURS.length]
            } ${s.status === "available" ? "" : "opacity-40"}`}
          >
            <span className="text-[10px] [writing-mode:vertical-rl] line-clamp-1">{s.title}</span>
            <span className="text-[9px] leading-tight">{s.call_no?.split(" ")[0]}</span>
          </div>
        ))}
        {data?.length === 0 && <p className="text-sm text-slate-500">This shelf is empty.</p>}
      </div>
      <p className="mt-2 text-xs text-slate-500">Faded spines are on loan or missing. Hover a spine for details.</p>
    </div>
  );
}
