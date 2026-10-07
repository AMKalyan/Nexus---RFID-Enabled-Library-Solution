import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { catalog, type Bib } from "../api/endpoints";
import { RefusalBanner } from "../components/RefusalBanner";
import { Button, Card, DataTable, Input, PageHeader } from "../components/ui";

const EMPTY_BIB = { title: "", author: "", isbn: "", publisher: "", pub_year: "" };
const EMPTY_ITEM = { accession_no: "", barcode: "", call_no: "", shelf_code: "", item_type: "lending" };

export function CataloguePage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [bibForm, setBibForm] = useState(EMPTY_BIB);
  const [selected, setSelected] = useState<Bib | null>(null);
  const [itemForm, setItemForm] = useState(EMPTY_ITEM);
  const [error, setError] = useState<ApiError | null>(null);
  const [lastItemId, setLastItemId] = useState<string | null>(null);

  const bibs = useQuery({ queryKey: ["bibs", search], queryFn: () => catalog.bibs(search) });
  const createBib = useMutation({
    mutationFn: () =>
      catalog.createBib({
        ...bibForm,
        isbn: bibForm.isbn || null,
        pub_year: bibForm.pub_year ? Number(bibForm.pub_year) : null,
      } as Partial<Bib>),
    onSuccess: (bib) => {
      setError(null);
      setSelected(bib);
      setBibForm(EMPTY_BIB);
      void qc.invalidateQueries({ queryKey: ["bibs"] });
    },
    onError: (e) => setError(e as ApiError),
  });
  const addItem = useMutation({
    mutationFn: () =>
      catalog.addItem(selected!.id, {
        ...itemForm,
        call_no: itemForm.call_no || null,
        shelf_code: itemForm.shelf_code || null,
      }),
    onSuccess: (item) => {
      setError(null);
      setItemForm(EMPTY_ITEM);
      setLastItemId(item.id);
    },
    onError: (e) => setError(e as ApiError),
  });

  return (
    <div>
      <PageHeader title="Catalogue" />
      {error && <div className="mb-3"><RefusalBanner code={error.code} message={error.message} /></div>}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Find a record">
          <form
            className="mb-3 flex gap-2"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              setSearch(q);
            }}
          >
            <input className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="Title, author or ISBN" value={q} onChange={(e) => setQ(e.target.value)} />
            <Button type="submit">Search</Button>
          </form>
          <DataTable
            columns={["title", "author", "year", ""]}
            rows={(bibs.data ?? []).map((b) => [
              b.title,
              b.author ?? "—",
              b.pub_year ?? "—",
              <Button variant="secondary" onClick={() => setSelected(b)}>
                Select
              </Button>,
            ])}
          />
        </Card>
        <Card title="New bibliographic record">
          <form
            className="grid gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              createBib.mutate();
            }}
          >
            <Input label="Title" required value={bibForm.title} onChange={(e) => setBibForm({ ...bibForm, title: e.target.value })} />
            <Input label="Author" value={bibForm.author} onChange={(e) => setBibForm({ ...bibForm, author: e.target.value })} />
            <div className="grid grid-cols-2 gap-3">
              <Input label="ISBN" value={bibForm.isbn} onChange={(e) => setBibForm({ ...bibForm, isbn: e.target.value })} />
              <Input label="Year" inputMode="numeric" value={bibForm.pub_year} onChange={(e) => setBibForm({ ...bibForm, pub_year: e.target.value })} />
            </div>
            <Input label="Publisher" value={bibForm.publisher} onChange={(e) => setBibForm({ ...bibForm, publisher: e.target.value })} />
            <Button type="submit" disabled={createBib.isPending}>
              <Plus size={14} aria-hidden /> Create record
            </Button>
          </form>
        </Card>
      </div>
      {selected && (
        <Card title={`Add a copy of “${selected.title}”`} className="mt-4">
          <form
            className="grid gap-3 md:grid-cols-6 md:items-end"
            onSubmit={(e) => {
              e.preventDefault();
              addItem.mutate();
            }}
          >
            <Input label="Accession no." required placeholder="ACC-000123" value={itemForm.accession_no} onChange={(e) => setItemForm({ ...itemForm, accession_no: e.target.value })} />
            <Input label="Barcode" required value={itemForm.barcode} onChange={(e) => setItemForm({ ...itemForm, barcode: e.target.value })} />
            <Input label="Call no." value={itemForm.call_no} onChange={(e) => setItemForm({ ...itemForm, call_no: e.target.value })} />
            <Input label="Shelf" placeholder="A-01" value={itemForm.shelf_code} onChange={(e) => setItemForm({ ...itemForm, shelf_code: e.target.value })} />
            <label className="text-sm text-slate-700">
              Type
              <select className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" value={itemForm.item_type} onChange={(e) => setItemForm({ ...itemForm, item_type: e.target.value })}>
                <option value="lending">Lending</option>
                <option value="reference">Reference only</option>
              </select>
            </label>
            <Button type="submit" disabled={addItem.isPending}>
              Add item
            </Button>
          </form>
          {lastItemId && (
            <p className="mt-3 text-sm text-green-700">
              Item added. <Link className="underline" to={`/items/${lastItemId}`}>Open item</Link> to tag it.
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
