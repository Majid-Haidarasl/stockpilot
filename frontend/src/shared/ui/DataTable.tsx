import {
  Box,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import type { ReactNode } from "react";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { ForbiddenState } from "./ForbiddenState";
import { LoadingState } from "./LoadingState";
import { SectionCard } from "./SectionCard";

export type DataTableColumn<T> = {
  id: string;
  header: string;
  render: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
};

type DataTableProps<T> = {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  emptyMessage?: string;
  errorMessage?: string | null;
  forbiddenMessage?: string | null;
  onRetry?: () => void;
  skeletonRows?: number;
  /**
   * When provided, only this branch renders below `sm` (never both variants).
   * Avoids duplicate accessible names from CSS-hidden tables.
   */
  renderMobileRow?: (row: T) => ReactNode;
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading = false,
  emptyMessage = "موردی برای نمایش نیست.",
  errorMessage = null,
  forbiddenMessage = null,
  onRetry,
  skeletonRows = 5,
  renderMobileRow,
}: DataTableProps<T>) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));

  if (forbiddenMessage) {
    return <ForbiddenState message={forbiddenMessage} />;
  }
  if (errorMessage) {
    return <ErrorState message={errorMessage} onRetry={onRetry} />;
  }
  if (loading) {
    if (isMobile && renderMobileRow) {
      return (
        <SectionCard>
          <Stack spacing={1}>
            {Array.from({ length: skeletonRows }).map((_, i) => (
              <Skeleton key={`sk-m-${i}`} variant="rounded" height={72} />
            ))}
          </Stack>
          <LoadingState message="در حال بارگذاری…" />
        </SectionCard>
      );
    }
    return (
      <SectionCard>
        <TableContainer>
          <Table size="small" aria-busy="true">
            <TableHead>
              <TableRow>
                {columns.map((col) => (
                  <TableCell key={col.id} align={col.align}>
                    {col.header}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {Array.from({ length: skeletonRows }).map((_, i) => (
                <TableRow key={`sk-${i}`}>
                  {columns.map((col) => (
                    <TableCell key={col.id}>
                      <Skeleton variant="text" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        <LoadingState message="در حال بارگذاری…" />
      </SectionCard>
    );
  }
  if (rows.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  if (isMobile && renderMobileRow) {
    return (
      <SectionCard>
        <Stack component="ul" spacing={1} sx={{ listStyle: "none", m: 0, p: 0 }}>
          {rows.map((row) => (
            <Box component="li" key={rowKey(row)}>
              {renderMobileRow(row)}
            </Box>
          ))}
        </Stack>
      </SectionCard>
    );
  }

  return (
    <SectionCard>
      <TableContainer sx={{ overflowX: "auto" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              {columns.map((col) => (
                <TableCell key={col.id} align={col.align}>
                  {col.header}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={rowKey(row)} hover>
                {columns.map((col) => (
                  <TableCell key={col.id} align={col.align}>
                    {col.render(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </SectionCard>
  );
}
