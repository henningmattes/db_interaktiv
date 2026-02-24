import initSqlJs, { type Database, type QueryExecResult, type SqlJsStatic } from 'sql.js';
import wasmUrl from 'sql.js/dist/sql-wasm.wasm?url';
import type { DatabaseSchema, WorkerRequest, WorkerResponse } from '../types/sqlWorker';

let SQL: SqlJsStatic | null = null;
let db: Database | null = null;

const postMessageSafe = (message: WorkerResponse): void => {
  self.postMessage(message);
};

const ensureRuntime = async (): Promise<void> => {
  if (!SQL) {
    SQL = await initSqlJs({
      locateFile: () => wasmUrl
    });
  }
};

const replaceDatabase = (seedSql: string): void => {
  if (!SQL) {
    throw new Error('SQL.js runtime ist nicht initialisiert.');
  }

  db?.close();
  db = new SQL.Database();

  if (seedSql.trim().length > 0) {
    db.exec(seedSql);
  }
};

const toRows = (result: QueryExecResult): Record<string, unknown>[] => {
  return result.values.map((valueSet) => {
    const row: Record<string, unknown> = {};

    for (let index = 0; index < result.columns.length; index += 1) {
      row[result.columns[index]] = valueSet[index];
    }

    return row;
  });
};

const readSchema = (): DatabaseSchema => {
  if (!db) {
    return [];
  }

  const schemaResult = db.exec(`
    SELECT
      m.name AS tableName,
      p.name AS columnName,
      p.type AS columnType,
      p.pk AS isPrimaryKey,
      p.cid AS columnOrder
    FROM sqlite_master m
    JOIN pragma_table_info(m.name) p
    WHERE m.type = 'table'
      AND m.name NOT LIKE 'sqlite_%'
    ORDER BY m.name, p.cid
  `);

  if (schemaResult.length === 0) {
    return [];
  }

  const rows = toRows(schemaResult[0]);
  const tableMap = new Map<string, DatabaseSchema[number]>();

  for (const row of rows) {
    const tableName = String(row.tableName);
    const columnName = String(row.columnName);
    const columnType = String(row.columnType ?? '');
    const isPrimaryKey = Number(row.isPrimaryKey ?? 0) > 0;

    if (!tableMap.has(tableName)) {
      tableMap.set(tableName, {
        name: tableName,
        columns: [],
        foreignKeys: []
      });
    }

    tableMap.get(tableName)?.columns.push({
      name: columnName,
      type: columnType,
      isPrimaryKey
    });
  }

  const foreignKeyResult = db.exec(`
    SELECT
      m.name AS tableName,
      fk."from" AS columnName,
      fk."table" AS referencedTable,
      fk."to" AS referencedColumn
    FROM sqlite_master m
    JOIN pragma_foreign_key_list(m.name) fk
    WHERE m.type = 'table'
      AND m.name NOT LIKE 'sqlite_%'
    ORDER BY m.name, fk.id, fk.seq
  `);

  if (foreignKeyResult.length > 0) {
    const fkRows = toRows(foreignKeyResult[0]);

    for (const row of fkRows) {
      const tableName = String(row.tableName);
      if (!tableMap.has(tableName)) {
        continue;
      }

      tableMap.get(tableName)?.foreignKeys.push({
        columnName: String(row.columnName),
        referencedTable: String(row.referencedTable),
        referencedColumn: String(row.referencedColumn ?? '')
      });
    }
  }

  return [...tableMap.values()];
};

self.onmessage = async (event: MessageEvent<WorkerRequest>): Promise<void> => {
  try {
    const message = event.data;

    if (message.type === 'init') {
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
      if (!statement) {
        throw new Error('Bitte eine SQL-Abfrage eingeben.');
      }

      const results = db.exec(statement);
      if (results.length === 0) {
        const changed = db.getRowsModified();
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
      const rows = toRows(lastResult);

      postMessageSafe({
        type: 'queryResult',
        payload: {
          columns: lastResult.columns,
          rows,
          rowCount: rows.length,
          message: `${rows.length} Zeilen gelesen.`,
          schema: readSchema()
        }
      });
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unbekannter Fehler im SQL-Worker.';
    postMessageSafe({
      type: 'error',
      payload: {
        message
      }
    });
  }
};
