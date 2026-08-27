"""Tenant-scoped dashboard reads under an established RLS transaction."""

from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


class DashboardRepository:
    def __init__(self, db: Session):
        self.db = db

    def overview(self, tenant: UUID, from_date: date, to_date: date, search: str, status: str, sort: str, page: int, per_page: int) -> dict:
        values: dict[str, object] = {
            "tenant": tenant,
            "from": from_date,
            "to": to_date,
            "search": f"%{search}%",
            "status": status,
            "sort": sort,
            "limit": per_page,
            "offset": (page - 1) * per_page,
        }
        # pi-lens-ignore: python-sql-injection
        kpis = dict(self.db.execute(text("""SELECT count(DISTINCT e.id) AS total, count(DISTINCT e.id) FILTER (WHERE e.status='running') AS running, count(DISTINCT e.id) FILTER (WHERE e.status='completed') AS completed, count(DISTINCT r.id) AS results FROM experiments e LEFT JOIN results r ON r.tenant_id=e.tenant_id AND r.experiment_id=e.id WHERE e.tenant_id=:tenant AND e.created_at >= :from AND e.created_at < (CAST(:to AS date) + interval '1 day')"""), values).mappings().one())
        # pi-lens-ignore: python-sql-injection
        daily = [dict(row) for row in self.db.execute(text("""WITH days AS (SELECT generate_series(CAST(:from AS date), CAST(:to AS date), interval '1 day')::date AS day) SELECT days.day::text AS date, count(DISTINCT e.id) AS experiments, count(DISTINCT r.id) AS results, avg(m.number_value)::float AS metric_average FROM days LEFT JOIN experiments e ON e.tenant_id=:tenant AND e.created_at::date=days.day LEFT JOIN results r ON r.tenant_id=:tenant AND r.experiment_id=e.id LEFT JOIN metrics m ON m.tenant_id=:tenant AND m.result_id=r.id AND m.value_type='number' GROUP BY days.day ORDER BY days.day"""), values).mappings().all()]
        # pi-lens-ignore: python-sql-injection
        statuses = [dict(row) for row in self.db.execute(text("""SELECT e.status, count(*) AS count FROM experiments e WHERE e.tenant_id=:tenant AND e.created_at >= :from AND e.created_at < (CAST(:to AS date) + interval '1 day') GROUP BY e.status ORDER BY e.status"""), values).mappings().all()]
        # pi-lens-ignore: python-sql-injection
        total = self.db.execute(text("""SELECT count(*) FROM experiments e WHERE e.tenant_id=:tenant AND e.created_at >= :from AND e.created_at < (CAST(:to AS date) + interval '1 day') AND (:status='' OR e.status=:status) AND (:search='' OR e.name ILIKE :search)"""), values).scalar_one()
        # pi-lens-ignore: python-sql-injection
        items = [dict(row) for row in self.db.execute(text("""SELECT e.id, e.name, e.status, e.created_at, count(r.id) AS result_count, latest_metric.number_value::float AS latest_metric FROM experiments e LEFT JOIN results r ON r.tenant_id=e.tenant_id AND r.experiment_id=e.id LEFT JOIN LATERAL (SELECT m.number_value FROM results latest_result JOIN metrics m ON m.tenant_id=latest_result.tenant_id AND m.result_id=latest_result.id AND m.value_type='number' WHERE latest_result.tenant_id=e.tenant_id AND latest_result.experiment_id=e.id ORDER BY m.recorded_at DESC, m.id DESC LIMIT 1) latest_metric ON true WHERE e.tenant_id=:tenant AND e.created_at >= :from AND e.created_at < (CAST(:to AS date) + interval '1 day') AND (:status='' OR e.status=:status) AND (:search='' OR e.name ILIKE :search) GROUP BY e.id, latest_metric.number_value ORDER BY CASE WHEN :sort='created_at:asc' THEN e.created_at END ASC, CASE WHEN :sort='created_at:desc' THEN e.created_at END DESC, CASE WHEN :sort='name:asc' THEN e.name END ASC, CASE WHEN :sort='name:desc' THEN e.name END DESC, CASE WHEN :sort='result_count:desc' THEN count(r.id) END DESC, e.id LIMIT :limit OFFSET :offset"""), values).mappings().all()]
        pages = max(1, (total + per_page - 1) // per_page)
        return {"range": {"from": from_date.isoformat(), "to": to_date.isoformat()}, "kpis": kpis, "daily": daily, "statuses": statuses, "items": items, "total": total, "page": page, "per_page": per_page, "pages": pages}
