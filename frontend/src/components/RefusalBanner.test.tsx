import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { REFUSAL_TEXT, RefusalBanner } from "./RefusalBanner";

const CODES = [
  "ITEM_REFERENCE_ONLY",
  "MEMBER_BLOCKED",
  "MEMBER_EXPIRED",
  "FINE_LIMIT_EXCEEDED",
  "MAX_ITEMS_REACHED",
  "MAX_RENEWALS_REACHED",
  "ITEM_NOT_AVAILABLE",
  "ITEM_NOT_ON_LOAN",
  "ROLE_NOT_PERMITTED",
];

it("has text for every circulation refusal code", () => {
  for (const code of CODES) expect(REFUSAL_TEXT[code]).toBeTruthy();
});

it("renders the message for a code as an alert", () => {
  render(<RefusalBanner code="MEMBER_BLOCKED" />);
  expect(screen.getByRole("alert").textContent).toContain("blocked");
});

it("falls back to the server message for unknown codes", () => {
  render(<RefusalBanner code="SOMETHING_NEW" message="Server said no" />);
  expect(screen.getByRole("alert").textContent).toContain("Server said no");
});
