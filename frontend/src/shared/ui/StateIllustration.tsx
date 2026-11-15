import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import InboxOutlinedIcon from "@mui/icons-material/InboxOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import SearchOffOutlinedIcon from "@mui/icons-material/SearchOffOutlined";
import { Box } from "@mui/material";
import type { ReactElement, ReactNode } from "react";

export type StateIllustrationKind = "empty" | "error" | "forbidden" | "notFound" | "inbox";

const ICONS: Record<StateIllustrationKind, ReactElement> = {
  empty: <InboxOutlinedIcon sx={{ fontSize: 48 }} aria-hidden />,
  inbox: <InboxOutlinedIcon sx={{ fontSize: 56 }} aria-hidden />,
  error: <ErrorOutlineIcon sx={{ fontSize: 48 }} aria-hidden />,
  forbidden: <LockOutlinedIcon sx={{ fontSize: 48 }} aria-hidden />,
  notFound: <SearchOffOutlinedIcon sx={{ fontSize: 48 }} aria-hidden />,
};

type StateIllustrationProps = {
  kind: StateIllustrationKind;
  children?: ReactNode;
};

/** Decorative icon block for empty/error/forbidden/404 surfaces (aria-hidden). */
export function StateIllustration({ kind, children }: StateIllustrationProps) {
  return (
    <Box
      aria-hidden
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 1,
        color: "text.secondary",
        opacity: 0.85,
        mb: 1,
      }}
    >
      {children ?? ICONS[kind]}
    </Box>
  );
}
