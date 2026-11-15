import { Route, Routes } from "react-router-dom";
import { LoginPage } from "../features/auth/LoginPage";
import { CustomersPage } from "../features/customers/CustomersPage";
import { ProductsPage } from "../features/catalog/ProductsPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { ErrorFallbackPage } from "../features/errors/ErrorFallbackPage";
import { NotFoundPage, TenantNotFoundPage } from "../features/errors/NotFoundPage";
import { HomePage } from "../features/home/HomePage";
import { InventoryPage } from "../features/inventory/InventoryPage";
import { MembersPage } from "../features/members/MembersPage";
import { NotificationsPage } from "../features/notifications/NotificationsPage";
import { DraftOrderPage } from "../features/orders/DraftOrderPage";
import { OrderDetailPage } from "../features/orders/OrderDetailPage";
import { OrderListPage } from "../features/orders/OrderListPage";
import { OrgPickerPage } from "../features/orgs/OrgPickerPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/orgs" element={<OrgPickerPage />} />
      <Route path="/error" element={<ErrorFallbackPage />} />
      <Route path="/t/:tenantId" element={<DashboardPage />} />
      <Route path="/t/:tenantId/dashboard" element={<DashboardPage />} />
      <Route path="/t/:tenantId/products" element={<ProductsPage />} />
      <Route path="/t/:tenantId/customers" element={<CustomersPage />} />
      <Route path="/t/:tenantId/inventory" element={<InventoryPage />} />
      <Route path="/t/:tenantId/orders" element={<OrderListPage />} />
      <Route path="/t/:tenantId/orders/new" element={<DraftOrderPage />} />
      <Route path="/t/:tenantId/orders/:orderId" element={<OrderDetailPage />} />
      <Route path="/t/:tenantId/members" element={<MembersPage />} />
      <Route path="/t/:tenantId/notifications" element={<NotificationsPage />} />
      <Route path="/t/:tenantId/*" element={<TenantNotFoundPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
