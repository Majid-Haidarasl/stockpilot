import { Paper } from "@mui/material";
import type { ReactNode } from "react";

type SectionCardProps = {
  children: ReactNode;
  component?: React.ElementType;
};

export function SectionCard({ children, component = "section" }: SectionCardProps) {
  return (
    <Paper
      component={component}
      variant="outlined"
      sx={{ p: { xs: 1.5, sm: 2 }, bgcolor: "background.paper" }}
    >
      {children}
    </Paper>
  );
}
