import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import MenuIcon from "@mui/icons-material/Menu";
import NotificationsOutlinedIcon from "@mui/icons-material/NotificationsOutlined";
import DashboardOutlinedIcon from "@mui/icons-material/DashboardOutlined";
import MenuOpenIcon from "@mui/icons-material/MenuOpen";
import ReceiptLongOutlinedIcon from "@mui/icons-material/ReceiptLongOutlined";
import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import PeopleOutlinedIcon from "@mui/icons-material/PeopleOutlined";
import WarehouseOutlinedIcon from "@mui/icons-material/WarehouseOutlined";
import GroupOutlinedIcon from "@mui/icons-material/GroupOutlined";
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListSubheader,
  Menu,
  MenuItem,
  Toolbar,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link as RouterLink, useLocation, useParams } from "react-router-dom";
import { apiFetch, type MeResponse } from "../api";
import { useLogout } from "../auth/useLogout";
import { queryKeys } from "../query/keys";
import { getTenant } from "../tenant";
import { prefersReducedMotion } from "../../theme/shape";
import { useColorMode } from "../../theme";
import { PageHeader } from "./PageHeader";

const DRAWER_WIDTH = 248;
const DRAWER_WIDTH_COLLAPSED = 72;
const COLLAPSE_KEY = "stockpilot.navCollapsed";

type NavItem = {
  to: string;
  label: string;
  icon: ReactNode;
};

type TenantShellProps = {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
  subtitle?: string;
};

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

export function TenantShell({ title, children, actions, subtitle }: TenantShellProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const { tenantId = "" } = useParams();
  const location = useLocation();
  const role = getTenant()?.role ?? "";
  const orgName = getTenant()?.name ?? "سازمان";
  const isAdmin = role === "admin";
  const { mode, toggleColorMode } = useColorMode();
  const { logout, pending: logoutPending } = useLogout();

  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => readCollapsed());
  const [userAnchor, setUserAnchor] = useState<null | HTMLElement>(null);

  const meQuery = useQuery({
    queryKey: queryKeys.me(),
    queryFn: () => apiFetch<MeResponse>("/api/v1/me"),
  });

  const userLabel =
    meQuery.data?.user?.display_name ??
    meQuery.data?.user?.email ??
    meQuery.data?.user?.id ??
    "کاربر";

  const primaryNav: NavItem[] = [
    {
      to: `/t/${tenantId}/dashboard`,
      label: "داشبورد",
      icon: <DashboardOutlinedIcon fontSize="small" />,
    },
    {
      to: `/t/${tenantId}/orders`,
      label: "سفارش‌ها",
      icon: <ReceiptLongOutlinedIcon fontSize="small" />,
    },
  ];

  const opsNav: NavItem[] = [
    {
      to: `/t/${tenantId}/products`,
      label: "کالاها",
      icon: <Inventory2OutlinedIcon fontSize="small" />,
    },
    {
      to: `/t/${tenantId}/customers`,
      label: "مشتریان",
      icon: <PeopleOutlinedIcon fontSize="small" />,
    },
    {
      to: `/t/${tenantId}/inventory`,
      label: "موجودی",
      icon: <WarehouseOutlinedIcon fontSize="small" />,
    },
  ];

  const orgNav: NavItem[] = [
    {
      to: `/t/${tenantId}/notifications`,
      label: "اعلان‌ها",
      icon: <NotificationsOutlinedIcon fontSize="small" />,
    },
  ];
  if (isAdmin) {
    orgNav.push({
      to: `/t/${tenantId}/members`,
      label: "اعضا",
      icon: <GroupOutlinedIcon fontSize="small" />,
    });
  }

  const drawerExpanded = isMobile || !collapsed;
  const drawerWidth = drawerExpanded ? DRAWER_WIDTH : DRAWER_WIDTH_COLLAPSED;

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  function isActive(to: string): boolean {
    if (to.endsWith("/orders")) {
      return (
        location.pathname === to ||
        location.pathname.startsWith(`${to}/`)
      );
    }
    return location.pathname === to || location.pathname.startsWith(`${to}/`);
  }

  function renderNavGroup(heading: string, items: NavItem[]) {
    return (
      <List
        key={heading}
        dense
        subheader={
          drawerExpanded ? (
            <ListSubheader
              component="div"
              sx={{ bgcolor: "transparent", lineHeight: 2, fontWeight: 700 }}
            >
              {heading}
            </ListSubheader>
          ) : undefined
        }
        sx={{ px: 0.5 }}
      >
        {items.map((item) => {
          const active = isActive(item.to);
          const button = (
            <ListItemButton
              key={item.to}
              component={RouterLink}
              to={item.to}
              selected={active}
              aria-current={active ? "page" : undefined}
              aria-label={drawerExpanded ? undefined : item.label}
              onClick={() => {
                if (isMobile) setMobileOpen(false);
              }}
              sx={{
                justifyContent: drawerExpanded ? "flex-start" : "center",
                px: drawerExpanded ? 1.5 : 1,
                minHeight: 44,
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: drawerExpanded ? 36 : 0,
                  color: active ? "primary.main" : "text.secondary",
                  justifyContent: "center",
                }}
                aria-hidden
              >
                {item.icon}
              </ListItemIcon>
              {drawerExpanded ? <ListItemText primary={item.label} /> : null}
            </ListItemButton>
          );
          return drawerExpanded ? (
            button
          ) : (
            <Tooltip key={item.to} title={item.label} placement="left">
              <Box component="span" sx={{ display: "block" }}>
                {button}
              </Box>
            </Tooltip>
          );
        })}
      </List>
    );
  }

  const collapseLabel = collapsed ? "باز کردن منو" : "جمع کردن منو";
  const collapseControl =
    !isMobile ? (
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: drawerExpanded ? "flex-end" : "center",
          px: 1,
          py: 0.5,
        }}
      >
        <Tooltip title={collapseLabel} placement="left">
          <IconButton
            onClick={toggleCollapsed}
            aria-label={collapseLabel}
            aria-expanded={!collapsed}
            size="small"
          >
            {collapsed ? <MenuOpenIcon /> : <MenuIcon />}
          </IconButton>
        </Tooltip>
      </Box>
    ) : null;

  const navContent = (
    <Box
      component="nav"
      aria-label="منوی سازمان"
      sx={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        pt: 1,
        pb: 2,
      }}
    >
      {collapseControl}
      {renderNavGroup("اصلی", primaryNav)}
      {renderNavGroup("عملیات", opsNav)}
      {renderNavGroup("سازمان", orgNav)}
      <Box sx={{ flexGrow: 1 }} />
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <Box
        component="a"
        href="#main-content"
        sx={{
          position: "absolute",
          insetInlineStart: -9999,
          top: 8,
          zIndex: theme.zIndex.tooltip + 1,
          bgcolor: "background.paper",
          color: "text.primary",
          px: 2,
          py: 1,
          borderRadius: 1,
          "&:focus": { insetInlineStart: 8 },
        }}
      >
        پرش به محتوا
      </Box>

      <AppBar
        component="header"
        position="fixed"
        color="inherit"
        elevation={0}
        sx={{
          borderBottom: 1,
          borderColor: "divider",
          bgcolor: "var(--sp-chrome)",
          zIndex: theme.zIndex.drawer + 1,
        }}
      >
        <Toolbar sx={{ gap: 1, minHeight: { xs: 56, sm: 64 } }}>
          {isMobile ? (
            <IconButton
              edge="start"
              aria-label="باز کردن منو"
              onClick={() => setMobileOpen(true)}
            >
              <MenuIcon />
            </IconButton>
          ) : null}

          <Typography variant="h6" component="p" sx={{ fontWeight: 700, m: 0, flexShrink: 0 }}>
            StockPilot
          </Typography>

          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              mx: 1,
              display: { xs: "none", sm: "block" },
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              maxWidth: 200,
            }}
          >
            {orgName}
          </Typography>

          <Box sx={{ flexGrow: 1 }} />

          <IconButton
            component={RouterLink}
            to={`/t/${tenantId}/notifications`}
            aria-label="نمایش اعلان‌ها"
            color="inherit"
          >
            <NotificationsOutlinedIcon />
          </IconButton>

          <IconButton
            onClick={toggleColorMode}
            aria-label={mode === "light" ? "فعال‌سازی حالت تاریک" : "فعال‌سازی حالت روشن"}
            color="inherit"
          >
            {mode === "light" ? <DarkModeOutlinedIcon /> : <LightModeOutlinedIcon />}
          </IconButton>

          <IconButton
            component={RouterLink}
            to="/orgs"
            aria-label="تغییر سازمان"
            color="inherit"
            sx={{
              borderRadius: 2,
              px: 1,
              typography: "body2",
              fontWeight: 600,
            }}
          >
            تغییر سازمان
          </IconButton>

          <IconButton
            onClick={(e) => setUserAnchor(e.currentTarget)}
            aria-label="منوی کاربر"
            aria-haspopup="true"
            aria-expanded={Boolean(userAnchor)}
            color="inherit"
          >
            <Typography variant="body2" sx={{ fontWeight: 600, maxWidth: 120 }} noWrap>
              {userLabel}
            </Typography>
          </IconButton>
          <Menu
            anchorEl={userAnchor}
            open={Boolean(userAnchor)}
            onClose={() => setUserAnchor(null)}
            anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
          >
            <MenuItem disabled>{userLabel}</MenuItem>
            <MenuItem
              disabled={logoutPending}
              onClick={() => {
                setUserAnchor(null);
                void logout();
              }}
            >
              خروج
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      {/* Exactly one navigation instance: temporary on mobile OR permanent on desktop. */}
      {isMobile ? (
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: false }}
          sx={{
            "& .MuiDrawer-paper": {
              width: DRAWER_WIDTH,
              boxSizing: "border-box",
            },
          }}
        >
          <Toolbar />
          {navContent}
        </Drawer>
      ) : (
        <Drawer
          variant="permanent"
          open
          sx={{
            width: drawerWidth,
            flexShrink: 0,
            whiteSpace: "nowrap",
            "& .MuiDrawer-paper": {
              width: drawerWidth,
              boxSizing: "border-box",
              overflowX: "hidden",
              bgcolor: "var(--sp-chrome)",
              transition: prefersReducedMotion()
                ? "none"
                : theme.transitions.create("width", {
                    easing: theme.transitions.easing.sharp,
                    duration: 200,
                  }),
            },
          }}
        >
          <Toolbar />
          {navContent}
        </Drawer>
      )}

      <Box
        component="main"
        id="main-content"
        tabIndex={-1}
        sx={{
          flexGrow: 1,
          width: { md: `calc(100% - ${drawerWidth}px)` },
          minWidth: 0,
          pt: { xs: 8, sm: 9 },
          px: { xs: 2, sm: 3 },
          pb: { xs: 3, sm: 4 },
          outline: "none",
        }}
      >
        <Box sx={{ maxWidth: 1400, mx: "auto", width: "100%" }}>
          <PageHeader title={title} subtitle={subtitle} actions={actions} />
          {children}
        </Box>
      </Box>
    </Box>
  );
}
