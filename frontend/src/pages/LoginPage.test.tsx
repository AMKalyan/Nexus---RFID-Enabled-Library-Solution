import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

const state = { accounts: [] as { role: string; username: string; password: string }[] };

vi.mock("../api/client", async (importOriginal) => {
  const real = await importOriginal<typeof import("../api/client")>();
  return { ...real, api: vi.fn(async (path: string) => (path === "/auth/demo-accounts" ? state.accounts : {})) };
});
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ login: vi.fn(), loginWithTokens: vi.fn() }) }));
vi.mock("react-router-dom", () => ({ useNavigate: () => vi.fn() }));

import { LoginPage } from "./LoginPage";

beforeEach(() => {
  state.accounts = [];
});

it("shows no demo accounts on a normal installation", async () => {
  render(<LoginPage />);
  await screen.findByText("Nexus sign in");
  expect(screen.queryByText("Demo accounts")).toBeNull();
});

it("lists demo accounts and fills the form with the chosen one", async () => {
  state.accounts = [
    { role: "Librarian", username: "librarian", password: "demo-visitor-2026" },
    { role: "Patron", username: "B00001", password: "demo-visitor-2026" },
  ];
  render(<LoginPage />);
  await screen.findByText("Demo accounts");
  expect(screen.queryByText("admin")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Use the Patron account" }));
  expect((screen.getByLabelText("Username or card number") as HTMLInputElement).value).toBe("B00001");
  expect((screen.getByLabelText("Password") as HTMLInputElement).value).toBe("demo-visitor-2026");
});
