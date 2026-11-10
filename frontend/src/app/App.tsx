import { Box, Container, Typography } from "@mui/material";
import { Route, Routes } from "react-router-dom";

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
        <Typography variant="h6" color="text.secondary" sx={{ fontWeight: 400 }}>
          سامانه مدیریت سفارش و موجودی برای شرکت‌های پخش
        </Typography>
      </Container>
    </Box>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
    </Routes>
  );
}
