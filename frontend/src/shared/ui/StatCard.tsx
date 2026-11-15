import { Box, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";
import { SectionCard } from "./SectionCard";

type StatCardProps = {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
};

/** KPI tile for Run 2+ dashboards — shipped now, unused until Run 2. */
export function StatCard({ label, value, hint, icon }: StatCardProps) {
  return (
    <SectionCard>
      <Stack direction="row" spacing={1.5} alignItems="flex-start">
        {icon ? (
          <Box sx={{ color: "primary.main", display: "inline-flex", mt: 0.25 }} aria-hidden>
            {icon}
          </Box>
        ) : null}
        <Stack spacing={0.5} sx={{ minWidth: 0 }}>
          <Typography variant="body2" color="text.secondary">
            {label}
          </Typography>
          <Typography variant="h5" component="p" sx={{ fontWeight: 700, m: 0 }}>
            {value}
          </Typography>
          {hint ? (
            <Typography variant="caption" color="text.secondary">
              {hint}
            </Typography>
          ) : null}
        </Stack>
      </Stack>
    </SectionCard>
  );
}
