export type SchemaColumn = {
  name: string;
  type: string;
  isPrimaryKey: boolean;
};

export type SchemaForeignKey = {
  columnName: string;
  referencedTable: string;
  referencedColumn: string;
};

export type SchemaTable = {
  name: string;
  columns: SchemaColumn[];
  foreignKeys: SchemaForeignKey[];
};

export type DatabaseSchema = SchemaTable[];

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
        schema: DatabaseSchema;
      };
    }
  | {
      type: 'databaseLoaded';
      payload: {
        name: string;
        schema: DatabaseSchema;
      };
    }
  | {
      type: 'queryResult';
      payload: {
        columns: string[];
        rows: Record<string, unknown>[];
        rowCount: number;
        message: string;
        schema: DatabaseSchema;
      };
    }
  | {
      type: 'error';
      payload: {
        message: string;
      };
    };
