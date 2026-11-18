"""BigQuery operations for the Jupyter kernel using Google's client library."""
from contextlib import closing
from pathlib import Path

import pandas as pd
from google.cloud import bigquery
from zizai.core.tabular import TabularOperations


def _required(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label}を指定してください。')
    return value.strip()


def _job_summary(job, project_id, *, dataset_id=None, table_id=None, rows=None):
    return pd.DataFrame([{
        'project_id': project_id,
        'dataset_id': dataset_id,
        'table_id': table_id,
        'job_id': job.job_id,
        'rows': rows,
        'status': 'completed',
    }])


def execute_sql(project_id, sql, *, schema=None, maximum_bytes_billed=None):
    """Run a GoogleSQL query using the Python environment's configured credentials."""
    project = _required(project_id, 'プロジェクトID')
    _required(sql, 'SQL')
    config = bigquery.QueryJobConfig(use_legacy_sql=False)
    if maximum_bytes_billed is not None:
        if type(maximum_bytes_billed) is not int or maximum_bytes_billed < 1:
            raise ValueError('maximum_bytes_billedには1以上の整数を指定してください。')
        config.maximum_bytes_billed = maximum_bytes_billed
    with closing(bigquery.Client(project=project)) as client:
        job = client.query(sql, job_config=config)
        rows = job.result()
        if rows.schema:
            result = rows.to_dataframe(create_bqstorage_client=False)
            if schema:
                return TabularOperations.attach_dataframe_schema(result, schema_override=schema, date_cleansing=False)
            return result
        destination = job.destination
        return _job_summary(job, project, dataset_id=getattr(destination, 'dataset_id', None),
                            table_id=getattr(destination, 'table_id', None), rows=job.num_dml_affected_rows)


def execute_sql_file(project_id, sql_file, *, encoding='utf8'):
    """Read the selected SQL file locally, then run it as GoogleSQL."""
    return execute_sql(project_id, Path(sql_file).read_text(encoding=encoding))


def load_data(project_id, dataset_id, table_id, data, *, write_disposition='WRITE_EMPTY', schema=None):
    """Load Notebook table data into one explicitly selected BigQuery table."""
    project = _required(project_id, 'プロジェクトID')
    dataset = _required(dataset_id, 'データセットID')
    table = _required(table_id, 'テーブル名')
    if write_disposition not in ('WRITE_EMPTY', 'WRITE_APPEND', 'WRITE_TRUNCATE'):
        raise ValueError('書き込みモードを選択してください。')
    frame = TabularOperations.to_dataframe(data)
    if frame.empty:
        raise ValueError('入力データが空です。')
    config = bigquery.LoadJobConfig(write_disposition=write_disposition)
    if schema:
        fields = TabularOperations.parse_schema_definition(schema)
        if any(not isinstance(field, dict) or not field.get('name') or not field.get('type') for field in fields):
            raise ValueError('ロードのスキーマにはBigQuery形式の name と type を指定してください。')
        config.schema = [bigquery.SchemaField.from_api_repr(field) for field in fields]
    destination = bigquery.DatasetReference(project, dataset).table(table)
    with closing(bigquery.Client(project=project)) as client:
        job = client.load_table_from_dataframe(frame, destination, job_config=config)
        job.result()
        return _job_summary(job, project, dataset_id=dataset, table_id=table, rows=job.output_rows)
