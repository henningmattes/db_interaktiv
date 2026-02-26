import initSqlJs, { type Database, type QueryExecResult, type SqlJsStatic } from 'sql.js';
import wasmUrl from 'sql.js/dist/sql-wasm.wasm?url';
import type { DatabaseSchema, WorkerRequest, WorkerResponse } from '../types/sqlWorker';

let SQL: SqlJsStatic | null = null;
let db: Database | null = null;

const workerLog = (...parts: unknown[]): void => {
  console.info('[sqlWorker]', ...parts);
};

const workerError = (...parts: unknown[]): void => {
  console.error('[sqlWorker]', ...parts);
};

const postMessageSafe = (message: WorkerResponse): void => {
  self.postMessage(message);
};

const ensureRuntime = async (): Promise<void> => {
  if (!SQL) {
    workerLog('ensureRuntime: init sql.js');
    const start = performance.now();
    SQL = await initSqlJs({
      locateFile: () => wasmUrl
    });
    workerLog(`ensureRuntime: ready in ${(performance.now() - start).toFixed(1)}ms`);
  }
};

const replaceDatabase = (seedSql: string): void => {
  if (!SQL) {
    throw new Error('SQL.js runtime ist nicht initialisiert.');
  }

  db?.close();
  db = new SQL.Database();

  if (seedSql.trim().length > 0) {
    workerLog(`replaceDatabase: exec start sqlLen=${seedSql.length}`);
    const start = performance.now();
    db.exec(seedSql);
    workerLog(`replaceDatabase: exec done in ${(performance.now() - start).toFixed(1)}ms`);
  } else {
    workerLog('replaceDatabase: empty SQL, created blank DB');
  }
};

const toRows = (result: QueryExecResult, columnsOverride?: string[]): Record<string, unknown>[] => {
  const fallbackColumns =
    result.values[0]?.map((_, index) => {
      return `column_${index + 1}`;
    }) ?? [];
  const columns =
    columnsOverride ??
    (Array.isArray(result.columns) && result.columns.length > 0 ? result.columns : fallbackColumns);

  if (!Array.isArray(result.columns) || result.columns.length === 0) {
    workerLog(`toRows: result has no explicit columns, fallback used (${columns.length} columns)`);
  }

  return result.values.map((valueSet) => {
    const row: Record<string, unknown> = {};

    for (let index = 0; index < columns.length; index += 1) {
      row[columns[index]] = valueSet[index];
    }

    return row;
  });
};

const stripLeadingComments = (statement: string): string => {
  let output = statement.trimStart();

  while (output.startsWith('--') || output.startsWith('/*')) {
    if (output.startsWith('--')) {
      const nextLineBreak = output.indexOf('\n');
      if (nextLineBreak < 0) {
        return '';
      }
      output = output.slice(nextLineBreak + 1).trimStart();
      continue;
    }

    const commentEnd = output.indexOf('*/');
    if (commentEnd < 0) {
      return '';
    }
    output = output.slice(commentEnd + 2).trimStart();
  }

  return output;
};

const isLikelyReadQuery = (statement: string): boolean => {
  const stripped = stripLeadingComments(statement);
  return /^(SELECT|WITH|PRAGMA|EXPLAIN)\b/i.test(stripped);
};

const readLastChangedRows = (): number => {
  if (!db) {
    return 0;
  }

  try {
    const changesResult = db.exec('SELECT changes() AS changed');
    const changed = Number(changesResult[0]?.values?.[0]?.[0] ?? 0);
    return Number.isFinite(changed) ? changed : 0;
  } catch {
    return db.getRowsModified();
  }
};

const tryReadColumnNames = (statement: string): string[] => {
  if (!db) {
    return [];
  }

  let preparedStatement: ReturnType<Database['prepare']> | null = null;

  try {
    preparedStatement = db.prepare(statement);
    const columns = preparedStatement.getColumnNames();
    return columns.map((column) => String(column));
  } catch (error) {
    workerLog('tryReadColumnNames failed', error instanceof Error ? error.message : String(error));
    return [];
  } finally {
    preparedStatement?.free();
  }
};

const resolveResultColumns = (statement: string, result: QueryExecResult): string[] => {
  if (Array.isArray(result.columns) && result.columns.length > 0) {
    return result.columns.map((column) => String(column));
  }

  const preparedColumns = tryReadColumnNames(statement);
  if (preparedColumns.length > 0) {
    workerLog(`resolveResultColumns: using prepared column names (${preparedColumns.length})`);
    return preparedColumns;
  }

  const fallback = result.values[0]?.map((_, index) => `column_${index + 1}`) ?? [];
  workerLog(`resolveResultColumns: fallback column names (${fallback.length})`);
  return fallback;
};

const readSchema = (): DatabaseSchema => {
  if (!db) {
    workerLog('readSchema: no db');
    return [];
  }

  const tablesResult = db.exec(`
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
      AND name NOT LIKE 'sqlite_%'
    ORDER BY name
  `);

  if (tablesResult.length === 0) {
    workerLog('readSchema: table query returned 0 rows');
    return [];
  }

  const tableNames = tablesResult[0].values.map((valueSet) => String(valueSet[0]));
  if (tableNames.length === 0) {
    workerLog('readSchema: no user tables found');
    return [];
  }

  const schema: DatabaseSchema = [];

  for (const tableName of tableNames) {
    const escapedTableName = tableName.replace(/"/g, '""');
    const tableSchema: DatabaseSchema[number] = {
      name: tableName,
      columns: [],
      foreignKeys: []
    };

    const columnResult = db.exec(`PRAGMA table_info("${escapedTableName}")`);
    const columnRows = columnResult[0]?.values ?? [];

    for (const columnRow of columnRows) {
      tableSchema.columns.push({
        name: String(columnRow[1]),
        type: String(columnRow[2] ?? ''),
        isPrimaryKey: Number(columnRow[5] ?? 0) > 0
      });
    }

    const foreignKeyResult = db.exec(`PRAGMA foreign_key_list("${escapedTableName}")`);
    const foreignKeyRows = foreignKeyResult[0]?.values ?? [];

    for (const foreignKeyRow of foreignKeyRows) {
      tableSchema.foreignKeys.push({
        columnName: String(foreignKeyRow[3]),
        referencedTable: String(foreignKeyRow[2]),
        referencedColumn: String(foreignKeyRow[4] ?? '')
      });
    }

    schema.push(tableSchema);
  }

  workerLog(
    `readSchema: tables=${schema.length} first=${schema
      .slice(0, 6)
      .map((table) => `${table.name}(${table.columns.length})`)
      .join(', ')}`
  );
  return schema;
};

self.onmessage = async (event: MessageEvent<WorkerRequest>): Promise<void> => {
  try {
    const message = event.data;
    workerLog(`onmessage: type=${message.type}`);

    if (message.type === 'init') {
      workerLog(`init payload: name=${message.payload.name} sqlLen=${message.payload.seedSql.length}`);
      await ensureRuntime();
      replaceDatabase(message.payload.seedSql);

      postMessageSafe({
        type: 'ready',
        payload: {
          name: message.payload.name,
          schema: readSchema()
        }
      });
      return;
    }

    if (message.type === 'loadDatabase') {
      workerLog(`loadDatabase payload: name=${message.payload.name} sqlLen=${message.payload.sql.length}`);
      await ensureRuntime();
      replaceDatabase(message.payload.sql);

      postMessageSafe({
        type: 'databaseLoaded',
        payload: {
          name: message.payload.name,
          schema: readSchema()
        }
      });
      return;
    }

    if (message.type === 'runQuery') {
      if (!db) {
        throw new Error('Keine Datenbank geladen.');
      }

      const statement = message.payload.sql.trim();
      workerLog(`runQuery: inputLen=${message.payload.sql.length} trimmedLen=${statement.length}`);
      if (!statement) {
        throw new Error('Bitte eine SQL-Abfrage eingeben.');
      }

      const start = performance.now();
      const results = db.exec(statement);
      workerLog(`runQuery: db.exec returned ${results.length} result set(s) in ${(performance.now() - start).toFixed(1)}ms`);
      if (results.length === 0) {
        const readQuery = isLikelyReadQuery(statement);
        if (readQuery) {
          const columns = tryReadColumnNames(statement);
          workerLog(`runQuery: read query with empty result set, columns=${columns.length}`);
          postMessageSafe({
            type: 'queryResult',
            payload: {
              columns,
              rows: [],
              rowCount: 0,
              message: '0 Zeilen.',
              schema: readSchema()
            }
          });
          return;
        }

        const changed = readLastChangedRows();
        workerLog(`runQuery: no result sets, changedRows=${changed}`);
        postMessageSafe({
          type: 'queryResult',
          payload: {
            columns: [],
            rows: [],
            rowCount: 0,
            message: `${changed} Zeilen veraendert.`,
            schema: readSchema()
          }
        });
        return;
      }

      const lastResult = results[results.length - 1];
      const normalizedColumns = resolveResultColumns(statement, lastResult);
      const rows = toRows(lastResult, normalizedColumns);
      workerLog(`runQuery: lastResult columns=${normalizedColumns.length} rows=${rows.length}`);

      postMessageSafe({
        type: 'queryResult',
        payload: {
          columns: normalizedColumns,
          rows,
          rowCount: rows.length,
          message: `${rows.length} Zeilen.`,
          schema: readSchema()
        }
      });
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unbekannter Fehler im SQL-Worker.';
    workerError('error', message, error instanceof Error ? error.stack : '');
    postMessageSafe({
      type: 'error',
      payload: {
        message
      }
    });
  }
};
