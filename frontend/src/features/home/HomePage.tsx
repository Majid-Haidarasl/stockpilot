import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import BusinessOutlinedIcon from "@mui/icons-material/BusinessOutlined";
import ReceiptLongOutlinedIcon from "@mui/icons-material/ReceiptLongOutlined";
import SecurityOutlinedIcon from "@mui/icons-material/SecurityOutlined";
import {
  Box,
  Button,
  Container,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import { loginUrl } from "../../shared/api";
import { transition } from "../../theme/shape";

const FEATURES = [
  {
    title: "سفارش‌ها",
    body: "از پیش‌نویس تا ارسال، با رزرو موجودی و پیگیری وضعیت.",
    icon: <ReceiptLongOutlinedIcon aria-hidden />,
  },
  {
    title: "موجودی",
    body: "رسید، تعدیل و هشدار کمبود در یک نگاه عملیاتی.",
    icon: <Inventory2OutlinedIcon aria-hidden />,
  },
  {
    title: "چندسازمانی",
    body: "هر سازمان داده و نقش جدا دارد؛ جابه‌جایی امن بین سازمان‌ها.",
    icon: <BusinessOutlinedIcon aria-hidden />,
  },
  {
    title: "نقش و امنیت",
    body: "دسترسی مبتنی بر نقش با احراز هویت Keycloak.",
    icon: <SecurityOutlinedIcon aria-hidden />,
  },
] as const;

function DashboardPreview() {
  const theme = useTheme();
  const bar = theme.palette.mode === "light" ? theme.palette.primary.main : theme.palette.primary.main;
  const muted = theme.palette.divider;
  return (
    <Box
      aria-hidden
      sx={{
        width: "100%",
        maxWidth: 420,
        mx: "auto",
        p: 2,
        borderRadius: 3,
        border: 1,
        borderColor: "divider",
        bgcolor: "background.paper",
        boxShadow: (t) => (t.palette.mode === "light" ? 2 : 3),
        transform: { md: "rotate(-1.5deg)" },
      }}
    >
      <Stack direction="row" spacing={1} sx={{ mb: 1.5 }}>
        {[0.9, 0.65, 0.45, 0.7].map((h, i) => (
          <Box
            key={i}
            sx={{
              flex: 1,
              height: 56,
              borderRadius: 1.5,
              bgcolor: i === 0 ? `${bar}18` : "action.hover",
              border: 1,
              borderColor: muted,
              position: "relative",
              overflow: "hidden",
              "&::after": {
                content: '""',
                position: "absolute",
                bottom: 8,
                insetInline: 8,
                height: 6,
                borderRadius: 1,
                bgcolor: i === 0 ? bar : muted,
                opacity: h,
              },
            }}
          />
        ))}
      </Stack>
      <Box sx={{ display: "grid", gap: 0.75 }}>
        {[0.95, 0.7, 0.55, 0.8].map((w, i) => (
          <Box
            key={i}
            sx={{
              height: 10,
              width: `${w * 100}%`,
              borderRadius: 1,
              bgcolor: muted,
            }}
          />
        ))}
      </Box>
    </Box>
  );
}

export function HomePage() {
  return (
    <Box
      component="main"
      sx={{
        minHeight: "100vh",
        bgcolor: "background.default",
        position: "relative",
        overflow: "hidden",
        backgroundImage: (theme) =>
          theme.palette.mode === "light"
            ? `radial-gradient(ellipse 80% 50% at 100% 0%, ${theme.palette.secondary.main}28, transparent 55%),
               radial-gradient(ellipse 60% 40% at 0% 100%, ${theme.palette.primary.main}10, transparent 50%),
               linear-gradient(165deg, ${theme.palette.background.default} 0%, ${theme.palette.divider}55 100%)`
            : `radial-gradient(ellipse 80% 50% at 100% 0%, ${theme.palette.primary.main}22, transparent 55%),
               radial-gradient(ellipse 60% 40% at 0% 100%, ${theme.palette.secondary.main}18, transparent 50%),
               linear-gradient(165deg, ${theme.palette.background.default} 0%, ${theme.palette.background.paper} 100%)`,
      }}
    >
      <Box
        aria-hidden
        sx={{
          position: "absolute",
          width: 280,
          height: 280,
          borderRadius: "50%",
          border: 1,
          borderColor: "divider",
          top: -80,
          insetInlineEnd: -60,
          opacity: 0.5,
        }}
      />
      <Box
        aria-hidden
        sx={{
          position: "absolute",
          width: 160,
          height: 160,
          borderRadius: 4,
          border: 1,
          borderColor: "divider",
          bottom: 120,
          insetInlineStart: -40,
          opacity: 0.35,
          transform: "rotate(18deg)",
        }}
      />

      <Container maxWidth="lg" sx={{ position: "relative", py: { xs: 6, md: 10 } }}>
        <Box
          sx={{
            display: "grid",
            gap: { xs: 4, md: 6 },
            gridTemplateColumns: { xs: "1fr", md: "1.1fr 0.9fr" },
            alignItems: "center",
            mb: { xs: 6, md: 8 },
          }}
        >
          <Box>
            <Typography
              component="h1"
              variant="h2"
              sx={{ fontWeight: 800, letterSpacing: "-0.03em", mb: 1.5 }}
            >
              StockPilot
            </Typography>
            <Typography variant="h6" color="text.secondary" sx={{ fontWeight: 400, mb: 1 }}>
              سامانه مدیریت سفارش و موجودی برای شرکت‌های پخش
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 3, maxWidth: 480 }}>
              سفارش، موجودی و سازمان‌ها را در یک محیط فارسی، امن و چندسازمانی مدیریت کنید.
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} useFlexGap>
              <Button
                variant="contained"
                size="large"
                sx={{ fontWeight: 700, px: 3 }}
                onClick={() => {
                  window.location.href = loginUrl();
                }}
              >
                ورود
              </Button>
              <Button
                href="#features"
                variant="outlined"
                size="large"
                sx={{ fontWeight: 600 }}
              >
                امکانات
              </Button>
            </Stack>
          </Box>
          <DashboardPreview />
        </Box>

        <Box id="features" component="section" aria-labelledby="features-heading">
          <Typography
            id="features-heading"
            component="h2"
            variant="h5"
            sx={{ fontWeight: 700, mb: 2.5 }}
          >
            آنچه در عمل می‌بینید
          </Typography>
          <Box
            sx={{
              display: "grid",
              gap: 2,
              gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "repeat(4, 1fr)" },
            }}
          >
            {FEATURES.map((feature) => (
              <Box
                key={feature.title}
                sx={{
                  p: 2.5,
                  borderRadius: 2,
                  border: 1,
                  borderColor: "divider",
                  bgcolor: "background.paper",
                  transition: transition(["transform", "box-shadow", "border-color"]),
                  "&:hover": {
                    transform: "translateY(-2px)",
                    borderColor: "primary.main",
                  },
                }}
              >
                <Box sx={{ color: "primary.main", mb: 1.25, display: "inline-flex" }}>
                  {feature.icon}
                </Box>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
                  {feature.title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {feature.body}
                </Typography>
              </Box>
            ))}
          </Box>
        </Box>
      </Container>

      <Box
        component="footer"
        sx={{
          borderTop: 1,
          borderColor: "divider",
          py: 2.5,
          mt: 2,
          bgcolor: "background.paper",
        }}
      >
        <Container maxWidth="lg">
          <Typography variant="body2" color="text.secondary">
            StockPilot — سامانه سفارش و موجودی برای شرکت‌های پخش
          </Typography>
        </Container>
      </Box>
    </Box>
  );
}
