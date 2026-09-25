import type { PropsWithChildren } from "react";
import { useSession } from "../../app/session";
import { ErrorState } from "../../components/States";
import { ApiError } from "../../api/client";
export function AdminOnly({ children }: PropsWithChildren) {
  return useSession()?.role === "admin" ? (
    children
  ) : (
    <ErrorState error={new ApiError("FORBIDDEN")} />
  );
}
