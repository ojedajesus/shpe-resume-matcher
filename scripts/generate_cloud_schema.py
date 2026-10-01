"""Emit reviewed Postgres DDL into a Supabase CLI-created migration file.

Run from apps/backend with its environment and PYTHONPATH=.; provide the
migration filename created by `supabase migration new shpe_cloud_schema`.
"""
from pathlib import Path
import sys
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from app.models import Base

path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit('Create the migration with Supabase CLI first')
dialect = postgresql.dialect()
statements = ['-- SHPE backend-only persistence. Existing invite/session authentication remains in the app.',
    '-- No browser/Data API grants: all operations pass through owner-scoped backend methods.', 'BEGIN;']
for table in Base.metadata.sorted_tables:
    statements.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ';')
    for index in sorted(table.indexes, key=lambda item: item.name):
        statements.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ';')
    statements.append(f'ALTER TABLE public.{table.name} ENABLE ROW LEVEL SECURITY;')
    statements.append(f'REVOKE ALL ON public.{table.name} FROM anon, authenticated;')
statements += ['REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;', 'COMMIT;']
path.write_text('\n\n'.join(statements) + '\n')
print(f'Generated {len(Base.metadata.tables)} tables with RLS and no client grants')
