"""Verify already-applied 0065..0069 before aligning the legacy Alembic ledger.

Read-only by default. --apply changes only alembic_version after every check passes.
Run from /app in the production backend, using the committed version of this file.
"""
import argparse
import importlib.util
from pathlib import Path
import re

import sqlalchemy as sa
from app.db import engine


class Capture:
    def __init__(self):
        self.metadata = sa.MetaData()
        self.tables = []
        self.indexes = []
        self.columns = []
        self.sql = []

    def create_table(self, name, *args):
        self.tables.append(sa.Table(name, self.metadata, *args))

    def create_index(self, name, table, columns):
        self.indexes.append((name, table, columns))

    def add_column(self, table, column):
        self.columns.append((table, column))

    def execute(self, sql):
        self.sql.append(sql)


def normalized(value):
    return re.sub(r'\s+', ' ', value.strip()).rstrip(';').lower()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def check_column(actual, expected, dialect, table):
    require(actual is not None, f'{table}.{expected.name}: missing column')
    require(actual['type'].compile(dialect=dialect) == expected.type.compile(dialect=dialect),
            f'{table}.{expected.name}: type differs')
    require(actual['nullable'] == expected.nullable, f'{table}.{expected.name}: nullability differs')
    if expected.server_default is not None:
        require(normalized(actual.get('default') or '') == normalized(str(expected.server_default.arg)),
                f'{table}.{expected.name}: server default differs')


def verify(connection, migrations):
    capture = Capture()
    for prefix in ('0065_', '0066_', '0067_', '0068_', '0069_'):
        paths = list(migrations.glob(prefix + '*.py'))
        require(len(paths) == 1, f'Expected one migration for {prefix}')
        spec = importlib.util.spec_from_file_location(prefix, paths[0])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.op = capture
        module.upgrade()
    inspector = sa.inspect(connection)
    for table in capture.tables:
        require(inspector.has_table(table.name), f'{table.name}: missing table')
        actual = {c['name']: c for c in inspector.get_columns(table.name)}
        for column in table.columns:
            check_column(actual.get(column.name), column, connection.dialect, table.name)
        require(inspector.get_pk_constraint(table.name)['constrained_columns'] == [c.name for c in table.primary_key],
                f'{table.name}: primary key differs')
        uniques = {tuple(x['column_names']) for x in inspector.get_unique_constraints(table.name)}
        for constraint in table.constraints:
            if isinstance(constraint, sa.UniqueConstraint):
                require(tuple(c.name for c in constraint.columns) in uniques, f'{table.name}: unique constraint missing')
            if isinstance(constraint, sa.ForeignKeyConstraint):
                expected = [(fk.parent.name, fk.target_fullname) for fk in constraint.elements]
                matches = [fk for fk in inspector.get_foreign_keys(table.name)
                    if list(zip(fk['constrained_columns'], [fk['referred_table']+'.'+c for c in fk['referred_columns']])) == expected
                    and fk['options'].get('ondelete') == constraint.ondelete]
                require(bool(matches), f'{table.name}: foreign key differs')
    for name, table, columns in capture.indexes:
        require(any(i['name'] == name and i['column_names'] == columns and not i['unique']
                    for i in inspector.get_indexes(table)), f'{name}: index differs')
    for table, column in capture.columns:
        actual = {c['name']: c for c in inspector.get_columns(table)}
        check_column(actual.get(column.name), column, connection.dialect, table)
    actual = {c['name']: c for c in inspector.get_columns('content_items')}
    check_column(actual.get('archived_url_released'),
                 sa.Column('archived_url_released', sa.Boolean(), nullable=False, server_default='false'),
                 connection.dialect, 'content_items')
    for sql in capture.sql:
        function = re.search(r'CREATE OR REPLACE FUNCTION (\w+)\(.*?\).*?LANGUAGE (\w+).*?\$\$(.*?)\$\$', sql, re.S | re.I)
        if function:
            name, language, body = function.groups()
            rows = connection.execute(sa.text("""SELECT p.prosrc, l.lanname FROM pg_proc p
                JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_language l ON l.oid=p.prolang
                WHERE n.nspname='public' AND p.proname=:name"""), {'name': name}).all()
            require(len(rows) == 1 and rows[0][1] == language.lower() and normalized(rows[0][0]) == normalized(body),
                    f'{name}: stored function differs')
        trigger = re.search(r'CREATE TRIGGER (\w+)', sql, re.I)
        if trigger:
            rows = connection.execute(sa.text("SELECT pg_get_triggerdef(oid), tgenabled FROM pg_trigger WHERE NOT tgisinternal AND tgname=:name"), {'name': trigger[1]}).all()
            require(len(rows) == 1 and rows[0][1] == 'O' and normalized(rows[0][0]).replace('public.', '') == normalized(sql),
                    f'{trigger[1]}: trigger differs or disabled')
    index = next((i for i in inspector.get_indexes('content_items') if i['name']=='uq_content_items_active_site_slug'), None)
    require(index is not None and index['unique'] and index['column_names']==['site_id','slug'], 'Active URL index differs')
    predicate = str(index['dialect_options'].get('postgresql_where', ''))
    predicate = re.sub(r'::(?:text|character varying)', '', predicate)
    predicate = normalized(predicate.replace('(', '').replace(')', ''))
    require(predicate == "site_id is not null and status <> 'deleted' and not archived_url_released", 'Active URL predicate differs')
    mismatch = connection.execute(sa.text("""SELECT EXISTS(SELECT 1 FROM content_items c
        JOIN generation_tasks t ON t.id=c.task_id
        WHERE c.archived_url_released IS DISTINCT FROM content_archived_url_released(c,t))""")).scalar_one()
    require(not mismatch, 'Archived URL backfill has not completed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with engine.begin() as connection:
        current = connection.execute(sa.text('SELECT version_num FROM alembic_version')).scalars().all()
        require(current in [['0064_template_knowledge'], ['0069_archived_content_urls']], f'Unexpected migration revision: {current}')
        verify(connection, Path('migrations/versions'))
        print('Verified tables, columns, constraints, indexes, functions, triggers and backfill for 0065..0069.')
        if args.apply and current == ['0064_template_knowledge']:
            result = connection.execute(sa.text("UPDATE alembic_version SET version_num='0069_archived_content_urls' WHERE version_num='0064_template_knowledge'"))
            require(result.rowcount == 1, 'Revision changed concurrently')
            print('Aligned Alembic ledger to 0069; application tables and data unchanged.')
        else:
            print('Read-only verification completed; Alembic revision:', current[0])


if __name__ == '__main__':
    main()
