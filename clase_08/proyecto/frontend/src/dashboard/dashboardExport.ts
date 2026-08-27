import type {
  DashboardQuery,
  DashboardResponse,
  DashboardStatus,
} from "../api";

const statusLabel: Record<DashboardStatus, string> = {
  draft: "Borrador",
  running: "En ejecución",
  completed: "Completado",
  failed: "Fallido",
};

type DashboardExportRow = [string, string, string, number, number | string];
type DashboardFetcher = (query: DashboardQuery) => Promise<DashboardResponse>;

export const dashboardExportRows = (
  result: DashboardResponse,
): DashboardExportRow[] =>
  result.items.map((item) => [
    item.name,
    statusLabel[item.status],
    item.created_at,
    item.result_count,
    item.latest_metric ?? "—",
  ]);

export async function collectDashboardExportRows(
  firstPage: DashboardResponse,
  query: DashboardQuery,
  getDashboard: DashboardFetcher,
): Promise<DashboardExportRow[]> {
  let currentPage = firstPage;
  if (currentPage.page !== 1)
    currentPage = await getDashboard({ ...query, page: 1, per_page: 50 });
  const rows = dashboardExportRows(currentPage);
  for (let page = currentPage.page + 1; page <= currentPage.pages; page += 1) {
    const nextPage = await getDashboard({ ...query, page, per_page: 50 });
    rows.push(...dashboardExportRows(nextPage));
  }
  return rows;
}
