import { Breadcrumbs, Link, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";
import { Link as RouterLink } from "react-router-dom";

export type PageBreadcrumb = {
  label: string;
  to?: string;
};

type PageHeaderProps = {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  breadcrumbs?: PageBreadcrumb[];
};

export function PageHeader({ title, subtitle, actions, breadcrumbs }: PageHeaderProps) {
  return (
    <Stack spacing={1} sx={{ mb: 2 }}>
      {breadcrumbs && breadcrumbs.length > 0 ? (
        <Breadcrumbs aria-label="مسیر صفحه">
          {breadcrumbs.map((crumb, index) => {
            const last = index === breadcrumbs.length - 1;
            if (crumb.to && !last) {
              return (
                <Link
                  key={`${crumb.label}-${index}`}
                  component={RouterLink}
                  to={crumb.to}
                  underline="hover"
                  color="inherit"
                >
                  {crumb.label}
                </Link>
              );
            }
            return (
              <Typography key={`${crumb.label}-${index}`} color="text.primary">
                {crumb.label}
              </Typography>
            );
          })}
        </Breadcrumbs>
      ) : null}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        alignItems={{ xs: "stretch", sm: "center" }}
        spacing={1.5}
      >
        <Stack spacing={0.5}>
          <Typography variant="h5" component="h1" sx={{ fontWeight: 700, m: 0 }}>
            {title}
          </Typography>
          {subtitle ? (
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          ) : null}
        </Stack>
        {actions ? (
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {actions}
          </Stack>
        ) : null}
      </Stack>
    </Stack>
  );
}
