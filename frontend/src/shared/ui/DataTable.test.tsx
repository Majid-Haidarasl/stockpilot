import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppThemeProvider } from "../../theme";
import { DataTable } from "./DataTable";

type Row = { id: string; name: string };

const rows: Row[] = [
  { id: "1", name: "آلفا" },
  { id: "2", name: "بتا" },
];

const columns = [
  { id: "name", header: "نام", render: (r: Row) => r.name },
];

describe("DataTable mobile vs desktop", () => {
  it("renders the desktop table when matchMedia reports desktop", () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    render(
      <AppThemeProvider>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          renderMobileRow={(r) => <span>موبایل-{r.name}</span>}
        />
      </AppThemeProvider>,
    );

    expect(screen.getByRole("columnheader", { name: "نام" })).toBeInTheDocument();
    expect(screen.getByText("آلفا")).toBeInTheDocument();
    expect(screen.queryByText("موبایل-آلفا")).not.toBeInTheDocument();
  });

  it("renders only the mobile variant when matchMedia reports mobile", () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: true,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    render(
      <AppThemeProvider>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          renderMobileRow={(r) => <span>موبایل-{r.name}</span>}
        />
      </AppThemeProvider>,
    );

    expect(screen.getByText("موبایل-آلفا")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "نام" })).not.toBeInTheDocument();
  });
});
