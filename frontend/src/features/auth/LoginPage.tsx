import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import { Box, Button, Paper, Stack, Typography } from "@mui/material";
import { loginUrl } from "../../shared/api";

const BULLETS = [
  "احراز هویت امن با Keycloak",
  "جداسازی کامل داده بین سازمان‌ها",
  "دسترسی مبتنی بر نقش (مدیر، فروش، انبار، مشاهده)",
] as const;

export function LoginPage() {
  return (
    <Box
      component="main"
      sx={{
        minHeight: "100vh",
        display: "grid",
        gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
        bgcolor: "background.default",
      }}
    >
      <Box
        sx={{
          display: { xs: "flex", md: "flex" },
          flexDirection: "column",
          justifyContent: "center",
          gap: 2,
          p: { xs: 3, md: 6 },
          color: "primary.contrastText",
          background: (theme) =>
            theme.palette.mode === "light"
              ? `linear-gradient(145deg, ${theme.palette.primary.main} 0%, ${theme.palette.secondary.main} 100%)`
              : `linear-gradient(145deg, #0F172A 0%, #0369A1 100%)`,
          minHeight: { xs: 200, md: "100vh" },
        }}
      >
        <Typography component="p" variant="h3" sx={{ fontWeight: 800, m: 0, letterSpacing: "-0.02em" }}>
          StockPilot
        </Typography>
        <Typography variant="h6" sx={{ opacity: 0.92, fontWeight: 500, maxWidth: 360 }}>
          سامانه مدیریت سفارش و موجودی برای شرکت‌های پخش
        </Typography>
        <Stack spacing={1.25} sx={{ mt: 1, display: { xs: "none", sm: "flex" } }}>
          {BULLETS.map((text) => (
            <Stack key={text} direction="row" spacing={1} alignItems="flex-start">
              <CheckCircleOutlineIcon fontSize="small" aria-hidden sx={{ mt: 0.25 }} />
              <Typography variant="body2" sx={{ opacity: 0.95 }}>
                {text}
              </Typography>
            </Stack>
          ))}
        </Stack>
        <Box
          aria-hidden
          sx={{
            mt: { xs: 0, md: 4 },
            display: { xs: "none", md: "block" },
            width: 180,
            height: 100,
            borderRadius: 2,
            border: "1px solid rgba(255,255,255,0.25)",
            background:
              "linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.04))",
          }}
        />
      </Box>

      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          p: { xs: 3, sm: 4 },
          backgroundImage: (theme) =>
            theme.palette.mode === "light"
              ? `radial-gradient(circle at top left, ${theme.palette.secondary.main}14, transparent 45%)`
              : `radial-gradient(circle at top left, ${theme.palette.primary.main}18, transparent 45%)`,
        }}
      >
        <Paper
          variant="outlined"
          sx={{
            p: { xs: 3, sm: 4 },
            width: "100%",
            maxWidth: 420,
            bgcolor: "background.paper",
          }}
        >
          <Typography component="h1" variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
            ورود
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            برای ادامه وارد حساب کاربری شوید. احراز هویت توسط Keycloak انجام می‌شود.
          </Typography>
          <Button
            variant="contained"
            size="large"
            fullWidth
            onClick={() => {
              window.location.href = loginUrl();
            }}
          >
            ورود
          </Button>
        </Paper>
      </Box>
    </Box>
  );
}
