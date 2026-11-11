import { Box, Button, Container, Paper, Typography } from "@mui/material";
import { loginUrl } from "../../shared/api";

export function LoginPage() {
  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        background:
          "radial-gradient(circle at top right, rgba(15,76,92,0.12), transparent 45%), linear-gradient(160deg, #f4f7f8 0%, #e8eef0 100%)",
      }}
    >
      <Container maxWidth="sm">
        <Paper sx={{ p: 4 }}>
          <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
            StockPilot
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            برای ادامه وارد حساب کاربری شوید. احراز هویت توسط Keycloak انجام می‌شود.
          </Typography>
          <Button
            variant="contained"
            size="large"
            onClick={() => {
              window.location.href = loginUrl();
            }}
          >
            ورود
          </Button>
        </Paper>
      </Container>
    </Box>
  );
}
