import { AlertTriangle } from "lucide-react";

// eslint-disable-next-line react-refresh/only-export-components
export const REFUSAL_TEXT: Record<string, string> = {
  ITEM_REFERENCE_ONLY: "This is a reference item and cannot leave the library",
  MEMBER_BLOCKED: "This member is blocked from borrowing",
  MEMBER_EXPIRED: "This membership has expired",
  FINE_LIMIT_EXCEEDED: "Outstanding fines exceed this member's limit",
  MAX_ITEMS_REACHED: "The member already has the maximum number of items",
  MAX_RENEWALS_REACHED: "This loan has been renewed the maximum number of times",
  ITEM_NOT_AVAILABLE: "This item is not available for loan",
  ITEM_NOT_ON_LOAN: "This item is not on loan",
  ROLE_NOT_PERMITTED: "Your role does not allow this action",
  MEMBER_NOT_FOUND: "No member with that card number",
  ITEM_NOT_FOUND: "No item with that accession number, barcode or tag",
};

export function RefusalBanner({ code, message }: { code: string; message?: string }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      <AlertTriangle size={18} className="mt-0.5 shrink-0" aria-hidden />
      <div>
        <div className="font-medium">{REFUSAL_TEXT[code] ?? message ?? "The request was refused"}</div>
        <div className="text-xs text-red-600">{code}</div>
      </div>
    </div>
  );
}
