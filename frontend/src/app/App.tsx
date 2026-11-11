import { Box, Container, Typography } from "@mui/material";
import { Link as RouterLink, Route, Routes } from "react-router-dom";
import { LoginPage } from "../features/auth/LoginPage";
import { CustomersPage } from "../features/customers/CustomersPage";
import { ProductsPage } from "../features/catalog/ProductsPage";
import { OrgPickerPage } from "../features/orgs/OrgPickerPage";

function HomePage() {
  return (
    <Box
      component="main"
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        background:
          "radial-gradient(circle at top right, rgba(15,76,92,0.12), transparent 45%), linear-gradient(160deg, #f4f7f8 0%, #e8eef0 100%)",
      }}
    >
      <Container maxWidth="sm">
        <Typography
          component="h1"
          variant="h2"
          sx={{ fontWeight: 700, letterSpacing: "-0.02em", mb: 1.5 }}
        >
          StockPilot
        </Typography>
        <Typography variant="h6" color="text.secondary" sx={{ fontWeight: 400, mb: 3 }}>
          سامانه مدیریت سفارش و موجودی برای شرکت‌های پخش
        </Typography>
        <Typography
          component={RouterLink}
          to="/login"
          sx={{ color: "primary.main", fontWeight: 600, textDecoration: "none" }}
        >
          ورود به سامانه
        </Typography>
      </Container>
    </Box>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/orgs" element={<OrgPickerPage />} />
      <Route path="/t/:tenantId/products" element={<ProductsPage />} />
      <Route path="/t/:tenantId/customers" element={<CustomersPage />} />
    </Routes>
  );
}
