"""Expose tenant-safe security-barrier views to the read-only assistant role."""

# pyright: reportMissingImports=false

from alembic import op

revision = "20260330_09"
down_revision = "20260330_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        CREATE VIEW public.assistant_experiments WITH (security_barrier=true) AS
          SELECT id,name,status,created_at,updated_at FROM public.experiments
          WHERE tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
            AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL;
        CREATE VIEW public.assistant_results WITH (security_barrier=true) AS
          SELECT id,experiment_id,status,input_summary,output_summary,created_at FROM public.results
          WHERE tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
            AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL;
        CREATE VIEW public.assistant_metrics WITH (security_barrier=true) AS
          SELECT result_id,name,value_type,number_value,text_value,boolean_value,unit,step,recorded_at FROM public.metrics
          WHERE tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
            AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL;

        REVOKE ALL ON SCHEMA public FROM assistant_reader;
        REVOKE ALL ON public.experiments,public.results,public.metrics,public.documents,public.chunks,public.embeddings FROM assistant_reader;
        REVOKE ALL ON public.assistant_experiments,public.assistant_results,public.assistant_metrics FROM PUBLIC;
        GRANT USAGE ON SCHEMA public TO assistant_reader;
        GRANT SELECT ON public.assistant_experiments,public.assistant_results,public.assistant_metrics TO assistant_reader;
    """)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        REVOKE ALL ON public.assistant_experiments,public.assistant_results,public.assistant_metrics FROM assistant_reader;
        DROP VIEW public.assistant_metrics,public.assistant_results,public.assistant_experiments;
    """)
    op.execute("RESET ROLE")
