<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import DatabaseDesignTab from './components/DatabaseDesignTab.vue';
import MonacoSqlEditor from './components/MonacoSqlEditor.vue';
import ResultTable from './components/ResultTable.vue';
import classbookSchemaSql from '../db_DigitalesKlassenbuch/01_schema.sql?raw';
import classbookDataSql from '../db_DigitalesKlassenbuch/02_beispieldaten.sql?raw';
import { mysqlToSqlite } from './lib/mysqlToSqlite';
import type { DatabaseSchema, WorkerRequest, WorkerResponse } from './types/sqlWorker';

type SampleDatabase = {
  id: string;
  name: string;
  loadSql: () => Promise<string>;
  starterQuery: string;
};

type AppTab = 'sql' | 'design';

const classbookSample: SampleDatabase = {
  id: 'digitales_klassenbuch',
  name: 'Digitales Klassenbuch',
  loadSql: async () => {
    // Dialekt-Anpassung fuer die Ausfuehrung in SQLite/sql.js.
    return mysqlToSqlite(`${classbookSchemaSql}\n\n${classbookDataSql}`);
  },
  starterQuery:
    'SELECT k.bezeichnung AS kurs, COUNT(*) AS belegungen FROM Kursbelegung kb JOIN Kurs k ON k.id = kb.kurs_id GROUP BY k.id, k.bezeichnung ORDER BY belegungen DESC LIMIT 20;'
};

const activeTab = ref<AppTab>('sql');
const query = ref(classbookSample.starterQuery);
const customDatabaseName = ref('Eigene Datenbank');
const customDatabaseSql = ref('');
const resultColumns = ref<string[]>([]);
const resultRows = ref<Record<string, unknown>[]>([]);
const schema = ref<DatabaseSchema>([]);
const status = ref('Initialisierung...');
const infoMessage = ref('');
const errorMessage = ref('');
const isBusy = ref(true);
const isLoadPanelOpen = ref(false);

let sqlWorker: Worker | null = null;
const sampleSqlCache = new Map<string, string>();
let workerStartTime = 0;

const appLog = (...parts: unknown[]): void => {
  console.info('[App]', ...parts);
};

const appError = (...parts: unknown[]): void => {
  console.error('[App]', ...parts);
};

const schemaSummary = (inputSchema: DatabaseSchema): string => {
  const tableCount = inputSchema.length;
  const firstTables = inputSchema
    .slice(0, 6)
    .map((table) => `${table.name}(${table.columns.length})`)
    .join(', ');

  return `tables=${tableCount}${firstTables ? ` [${firstTables}]` : ''}`;
};

const getSampleSql = async (sample: SampleDatabase): Promise<string> => {
  const cached = sampleSqlCache.get(sample.id);
  if (cached) {
    appLog(`Sample-SQL Cache HIT (${sample.id}) len=${cached.length}`);
    return cached;
  }

  const start = performance.now();
  appLog(`Sample-SQL Cache MISS (${sample.id}) - load start`);
  const sql = await sample.loadSql();
  const end = performance.now();
  appLog(`Sample-SQL loaded (${sample.id}) len=${sql.length} in ${(end - start).toFixed(1)}ms`);
  sampleSqlCache.set(sample.id, sql);
  return sql;
};

const sendToWorker = (message: WorkerRequest): void => {
  if (!sqlWorker) {
    errorMessage.value = 'Worker ist nicht verfuegbar.';
    appError('sendToWorker failed: worker is null', message.type);
    return;
  }

  if (message.type === 'init') {
    appLog(`-> Worker init name=${message.payload.name} seedSqlLen=${message.payload.seedSql.length}`);
  } else if (message.type === 'loadDatabase') {
    appLog(`-> Worker loadDatabase name=${message.payload.name} sqlLen=${message.payload.sql.length}`);
  } else {
    appLog(`-> Worker runQuery sqlLen=${message.payload.sql.length}`);
  }

  sqlWorker.postMessage(message);
};

const onWorkerMessage = (event: MessageEvent<WorkerResponse>): void => {
  const message = event.data;
  const elapsed = workerStartTime > 0 ? `${(performance.now() - workerStartTime).toFixed(1)}ms` : '-';
  appLog(`< - Worker ${message.type} after ${elapsed}`);

  if (message.type === 'ready') {
    isBusy.value = false;
    status.value = `Aktive Datenbank: ${message.payload.name}`;
    schema.value = message.payload.schema;
    infoMessage.value = 'Beispieldatenbank geladen.';
    errorMessage.value = '';
    appLog(`ready: db=${message.payload.name} ${schemaSummary(message.payload.schema)}`);
    return;
  }

  if (message.type === 'databaseLoaded') {
    isBusy.value = false;
    status.value = `Aktive Datenbank: ${message.payload.name}`;
    schema.value = message.payload.schema;
    infoMessage.value = `${message.payload.name} geladen.`;
    errorMessage.value = '';
    resultColumns.value = [];
    resultRows.value = [];
    appLog(`databaseLoaded: db=${message.payload.name} ${schemaSummary(message.payload.schema)}`);
    return;
  }

  if (message.type === 'queryResult') {
    isBusy.value = false;
    schema.value = message.payload.schema;
    resultColumns.value = message.payload.columns;
    resultRows.value = message.payload.rows;
    infoMessage.value = message.payload.message;
    errorMessage.value = '';
    appLog(
      `queryResult: cols=${message.payload.columns.length} rows=${message.payload.rows.length} ${schemaSummary(message.payload.schema)}`
    );
    return;
  }

  if (message.type === 'error') {
    isBusy.value = false;
    errorMessage.value = message.payload.message;
    appError(`workerError: ${message.payload.message}`);
  }
};

const onWorkerRuntimeError = (event: ErrorEvent): void => {
  isBusy.value = false;
  errorMessage.value = `Worker Runtime Error: ${event.message}`;
  appError('Worker runtime error', event.message, event.filename, event.lineno, event.colno);
};

const onWorkerMessageError = (event: MessageEvent): void => {
  isBusy.value = false;
  errorMessage.value = 'Worker Message Error';
  appError('Worker message error', event.data);
};

const loadSample = async (): Promise<void> => {
  const sample = classbookSample;
  appLog(`loadSample clicked: ${sample.name}`);
  try {
    workerStartTime = performance.now();
    const sql = await getSampleSql(sample);

    query.value = sample.starterQuery;
    infoMessage.value = '';
    errorMessage.value = '';
    isBusy.value = true;

    sendToWorker({
      type: 'loadDatabase',
      payload: {
        name: sample.name,
        sql
      }
    });
  } catch (error) {
    isBusy.value = false;
    errorMessage.value =
      error instanceof Error ? error.message : 'Beispieldatenbank konnte nicht geladen werden.';
    appError('loadSample failed', error);
  }
};

const runQuery = (): void => {
  appLog(`runQuery clicked sqlLen=${query.value.length}`);
  workerStartTime = performance.now();
  infoMessage.value = '';
  errorMessage.value = '';
  isBusy.value = true;

  sendToWorker({
    type: 'runQuery',
    payload: {
      sql: query.value
    }
  });
};

const loadCustomSql = async (event: Event): Promise<void> => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];

  if (!file) {
    appLog('loadCustomSql: no file selected');
    return;
  }

  appLog(`loadCustomSql file=${file.name}`);
  const sql = await file.text();
  appLog(`loadCustomSql read file len=${sql.length}`);
  workerStartTime = performance.now();
  infoMessage.value = '';
  errorMessage.value = '';
  isBusy.value = true;

  sendToWorker({
    type: 'loadDatabase',
    payload: {
      name: file.name,
      sql
    }
  });

  target.value = '';
};

const loadCustomSqlFromEditor = (): void => {
  const sql = customDatabaseSql.value.trim();
  if (!sql) {
    errorMessage.value = 'Bitte SQL fuer die eigene Datenbank eingeben.';
    appError('loadCustomSqlFromEditor: empty SQL input');
    return;
  }

  appLog(`loadCustomSqlFromEditor name=${customDatabaseName.value.trim() || 'Eigene Datenbank'} sqlLen=${sql.length}`);
  workerStartTime = performance.now();
  infoMessage.value = '';
  errorMessage.value = '';
  isBusy.value = true;

  sendToWorker({
    type: 'loadDatabase',
    payload: {
      name: customDatabaseName.value.trim() || 'Eigene Datenbank',
      sql
    }
  });
};

const loadDesignedSchema = (payload: { name: string; sql: string }): void => {
  appLog(`loadDesignedSchema name=${payload.name} sqlLen=${payload.sql.length}`);
  workerStartTime = performance.now();
  infoMessage.value = '';
  errorMessage.value = '';
  isBusy.value = true;

  sendToWorker({
    type: 'loadDatabase',
    payload
  });
};

onMounted(() => {
  appLog('onMounted: creating SQL worker');
  sqlWorker = new Worker(new URL('./workers/sqlWorker.ts', import.meta.url), { type: 'module' });
  sqlWorker.addEventListener('message', onWorkerMessage);
  sqlWorker.addEventListener('error', onWorkerRuntimeError);
  sqlWorker.addEventListener('messageerror', onWorkerMessageError);

  const initDatabase = async (): Promise<void> => {
    workerStartTime = performance.now();
    appLog('initDatabase start');
    try {
      const sample = classbookSample;
      const sql = await getSampleSql(sample);

      sendToWorker({
        type: 'init',
        payload: {
          name: sample.name,
          seedSql: sql
        }
      });
    } catch (error) {
      isBusy.value = false;
      errorMessage.value =
        error instanceof Error ? error.message : 'Initiale Beispieldatenbank konnte nicht geladen werden.';
      appError('initDatabase failed', error);
    }
  };

  void initDatabase();
});

onBeforeUnmount(() => {
  if (!sqlWorker) {
    return;
  }

  sqlWorker.removeEventListener('message', onWorkerMessage);
  sqlWorker.removeEventListener('error', onWorkerRuntimeError);
  sqlWorker.removeEventListener('messageerror', onWorkerMessageError);
  sqlWorker.terminate();
  sqlWorker = null;
});
</script>

<template>
  <main class="page">
    <section class="card tab-switcher">
      <div>
        <h1>SQL Browser Lab</h1>
        <p class="status">{{ status }}</p>
        <p v-if="errorMessage" class="error status-error">{{ errorMessage }}</p>
      </div>
      <nav class="tab-nav" aria-label="Ansichten">
        <a
          href="#"
          role="tab"
          :aria-selected="activeTab === 'sql'"
          class="tab-link"
          :class="{ 'tab-link--active': activeTab === 'sql' }"
          @click.prevent="activeTab = 'sql'"
        >
          SQL-Statements
        </a>
        <a
          href="#"
          role="tab"
          :aria-selected="activeTab === 'design'"
          class="tab-link"
          :class="{ 'tab-link--active': activeTab === 'design' }"
          @click.prevent="activeTab = 'design'"
        >
          Datenbank-Entwurf
        </a>
      </nav>
    </section>

    <template v-if="activeTab === 'sql'">
      <section class="card">
        <div class="schema-head">
          <div>
            <h2>Datenbank laden und Schema ansehen</h2>
          </div>
          <button type="button" @click="isLoadPanelOpen = !isLoadPanelOpen" :disabled="isBusy">
            {{ isLoadPanelOpen ? 'Datenbank-Lader ausblenden' : 'Datenbank laden' }}
          </button>
        </div>

        <div v-if="isLoadPanelOpen" class="loader-panel">
          <div class="row">
            <p class="sample-name">
              Beispiel-Datenbank: <strong>{{ classbookSample.name }}</strong>
            </p>
            <button type="button" @click="loadSample" :disabled="isBusy">Beispiel laden</button>
          </div>

          <div class="row upload-row">
            <label>
              Eigene SQL-Datei (.sql)
              <input type="file" accept=".sql,text/sql" @change="loadCustomSql" :disabled="isBusy" />
            </label>
          </div>

          <div class="inline-sql">
            <label>
              Name der eigenen Datenbank
              <input v-model="customDatabaseName" type="text" :disabled="isBusy" />
            </label>
            <label>
              SQL-Skript fuer eigene Datenbank
              <textarea
                v-model="customDatabaseSql"
                rows="5"
                placeholder="CREATE TABLE ...; INSERT INTO ...;"
                :disabled="isBusy"
              />
            </label>
            <button type="button" @click="loadCustomSqlFromEditor" :disabled="isBusy">
              SQL-Skript als DB laden
            </button>
          </div>
        </div>

        <h2>Datenbankschema</h2>
        <div v-if="schema.length > 0" class="schema-list">
          <p v-for="table in schema" :key="table.name" class="schema-line">
            <span class="schema-table">{{ table.name }}</span>(
            <span v-for="(column, index) in table.columns" :key="`${table.name}-${column.name}`">
              <span class="schema-column" :class="{ 'schema-column--pk': column.isPrimaryKey }">
                {{ column.name }}
              </span>
              <span v-if="column.type" class="schema-type">: {{ column.type }}</span>
              <span v-if="index < table.columns.length - 1">, </span>
            </span>)
          </p>
        </div>
        <p v-else-if="isBusy" class="empty">Schema wird geladen...</p>
        <p v-else class="empty">Kein Datenbankschema verfuegbar.</p>
      </section>

      <section class="card">
        <div class="editor-head">
          <h2>SQL-Statements</h2>
          <button type="button" @click="runQuery" :disabled="isBusy">Ausfuehren</button>
        </div>
        <MonacoSqlEditor v-model="query" />
        <p v-if="infoMessage" class="info">{{ infoMessage }}</p>
        <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      </section>

      <section class="card">
        <h2>Ausgabe</h2>
        <ResultTable v-if="resultColumns.length > 0" :columns="resultColumns" :rows="resultRows" />
        <p v-else class="empty">Noch keine Ergebniszeilen vorhanden.</p>
      </section>
    </template>

    <section v-else class="card">
      <DatabaseDesignTab :schema="schema" :is-busy="isBusy" @load-designed-schema="loadDesignedSchema" />
      <p v-if="infoMessage" class="info">{{ infoMessage }}</p>
      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
    </section>
  </main>
</template>
