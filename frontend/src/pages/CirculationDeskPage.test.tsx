import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import type { LoanDetail, MemberSummary } from "../api/endpoints";
import { CirculationDeskPage } from "./CirculationDeskPage";

const member: MemberSummary = {
  id: "m-1",
  card_no: "B00144",
  full_name: "Test Member",
  email: null,
  phone: null,
  category_code: "UG",
  status: "active",
  block_reason: null,
  open_fines: "0",
  fine_limit: "100.00",
  open_loans: 0,
  max_items: 4,
} as MemberSummary;

const kioskLoan: LoanDetail = {
  id: "l-1",
  item_id: "i-1",
  member_id: "m-1",
  issued_at: "2026-10-07T10:00:00Z",
  due_at: "2026-10-21T10:00:00Z",
  returned_at: null,
  renew_count: 0,
  channel: "ncip",
  accession_no: "ACC-000003",
  title: "Borrowed At The Kiosk",
};

const state = { loans: [] as LoanDetail[], openLoans: 0 };

vi.mock("../api/endpoints", async (importOriginal) => {
  const real = await importOriginal<typeof import("../api/endpoints")>();
  return {
    ...real,
    members: {
      ...real.members,
      search: vi.fn(async () => [member]),
      get: vi.fn(async () => ({ ...member, open_loans: state.openLoans })),
      loans: vi.fn(async () => state.loans),
    },
  };
});

beforeEach(() => {
  state.loans = [];
  state.openLoans = 0;
});

function lookUp() {
  fireEvent.change(screen.getByPlaceholderText("Scan or type card number"), { target: { value: "B00144" } });
  fireEvent.click(screen.getByRole("button", { name: "Look up" }));
}

it("looking a member up again shows loans made elsewhere since the last look-up (DEF-013)", async () => {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <CirculationDeskPage />
    </QueryClientProvider>,
  );
  lookUp();
  await screen.findByText("No items on loan");

  // The member borrows at a self-check kiosk (NCIP) while the desk still shows them.
  state.loans = [kioskLoan];
  state.openLoans = 1;
  lookUp();

  await waitFor(() => expect(screen.getByText("ACC-000003")).toBeTruthy());
});
