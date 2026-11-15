import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./app/App";
import { AppProviders } from "./app/providers";
import { AppThemeProvider } from "./app/theme";
import { RouteErrorBoundary } from "./features/errors/AppErrorBoundary";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppThemeProvider>
      <AppProviders>
        <BrowserRouter>
          <RouteErrorBoundary>
            <App />
          </RouteErrorBoundary>
        </BrowserRouter>
      </AppProviders>
    </AppThemeProvider>
  </StrictMode>,
);
