export type WorkerRequest =
  | {
      type: 'init';
      payload: {
        seedSql: string;
        name: string;
      };
    }
  | {
      type: 'loadDatabase';
      payload: {
        sql: string;
        name: string;
      };
    }
  | {
      type: 'runQuery';
      payload: {
        sql: string;
      };
    };

export type WorkerResponse =
  | {
      type: 'ready';
      payload: {
        name: string;
      };
    }
  | {
      type: 'databaseLoaded';
      payload: {
        name: string;
      };
    }
  | {
      type: 'queryResult';
      payload: {
        columns: string[];
        rows: Record<string, unknown>[];
        rowCount: number;
        message: string;
      };
    }
  | {
      type: 'error';
      payload: {
        message: string;
      };
    };
