import initSqlJs, { type Database, type QueryExecResult, type SqlJsStatic } from 'sql.js';
import wasmUrl from 'sql.js/dist/sql-wasm.wasm?url';
import type { WorkerRequest, WorkerResponse } from '../types/sqlWorker';

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

self.onmessage = async (event: MessageEvent<WorkerRequest>): Promise<void> => {
  try {
    const message = event.data;

    if (message.type === 'init') {
      await ensureRuntime();
      replaceDatabase(message.payload.seedSql);

      postMessageSafe({
        type: 'ready',
        payload: {
          name: message.payload.name
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
          name: message.payload.name
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
            message: `${changed} Zeilen veraendert.`
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
          message: `${rows.length} Zeilen gelesen.`
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
