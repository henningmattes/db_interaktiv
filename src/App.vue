<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import MonacoSqlEditor from './components/MonacoSqlEditor.vue';
import ResultTable from './components/ResultTable.vue';
import schoolSeed from './seeds/school.sql?raw';
import shopSeed from './seeds/shop.sql?raw';
import type { WorkerRequest, WorkerResponse } from './types/sqlWorker';

type SampleDatabase = {
  id: string;
  name: string;
  sql: string;
  starterQuery: string;
};

const samples: SampleDatabase[] = [
  {
    id: 'school',
    name: 'Schule',
    sql: schoolSeed,
    starterQuery: `SELECT s.name, c.title, e.score\nFROM enrollments e\nJOIN students s ON s.id = e.student_id\nJOIN courses c ON c.id = e.course_id\nORDER BY e.score DESC;`
  },
  {
    id: 'shop',
    name: 'Shop',
    sql: shopSeed,
    starterQuery: `SELECT c.name AS customer, p.name AS product, oi.quantity\nFROM order_items oi\nJOIN orders o ON o.id = oi.order_id\nJOIN customers c ON c.id = o.customer_id\nJOIN products p ON p.id = oi.product_id\nORDER BY customer;`
  }
];

const selectedSampleId = ref(samples[0].id);
const query = ref(samples[0].starterQuery);
const customDatabaseName = ref('Eigene Datenbank');
const customDatabaseSql = ref('');
const resultColumns = ref<string[]>([]);
const resultRows = ref<Record<string, unknown>[]>([]);
const status = ref('Initialisierung...');
const infoMessage = ref('');
const errorMessage = ref('');
const isBusy = ref(true);

let sqlWorker: Worker | null = null;

const selectedSample = computed(() => {
  return samples.find((sample) => sample.id === selectedSampleId.value) ?? samples[0];
});

const sendToWorker = (message: WorkerRequest): void => {
  if (!sqlWorker) {
    errorMessage.value = 'Worker ist nicht verfuegbar.';
    return;
  }

  sqlWorker.postMessage(message);
};

const onWorkerMessage = (event: MessageEvent<WorkerResponse>): void => {
  const message = event.data;

  if (message.type === 'ready') {
    isBusy.value = false;
    status.value = `Aktive Datenbank: ${message.payload.name}`;
    infoMessage.value = 'Beispieldatenbank geladen.';
    return;
  }

  if (message.type === 'databaseLoaded') {
    isBusy.value = false;
    status.value = `Aktive Datenbank: ${message.payload.name}`;
    infoMessage.value = `${message.payload.name} geladen.`;
    errorMessage.value = '';
    resultColumns.value = [];
    resultRows.value = [];
    return;
  }

  if (message.type === 'queryResult') {
    isBusy.value = false;
    resultColumns.value = message.payload.columns;
    resultRows.value = message.payload.rows;
    infoMessage.value = message.payload.message;
    errorMessage.value = '';
    return;
  }

  if (message.type === 'error') {
    isBusy.value = false;
    errorMessage.value = message.payload.message;
  }
};

const loadSample = (): void => {
  const sample = selectedSample.value;
  query.value = sample.starterQuery;
  infoMessage.value = '';
  errorMessage.value = '';
  isBusy.value = true;

  sendToWorker({
    type: 'loadDatabase',
    payload: {
      name: sample.name,
      sql: sample.sql
    }
  });
};

const runQuery = (): void => {
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
    return;
  }

  const sql = await file.text();
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
    return;
  }

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

onMounted(() => {
  sqlWorker = new Worker(new URL('./workers/sqlWorker.ts', import.meta.url), { type: 'module' });
  sqlWorker.addEventListener('message', onWorkerMessage);

  sendToWorker({
    type: 'init',
    payload: {
      name: selectedSample.value.name,
      seedSql: selectedSample.value.sql
    }
  });
});

onBeforeUnmount(() => {
  if (!sqlWorker) {
    return;
  }

  sqlWorker.removeEventListener('message', onWorkerMessage);
  sqlWorker.terminate();
  sqlWorker = null;
});
</script>

<template>
  <main class="page">
    <section class="card controls">
      <h1>SQL Browser Lab</h1>
      <p>SQL lokal im Browser ausfuehren: Demo-Datenbanken laden oder eigene SQL-Datei importieren.</p>

      <div class="row">
        <label>
          Beispiel-Datenbank
          <select v-model="selectedSampleId" :disabled="isBusy">
            <option v-for="sample in samples" :key="sample.id" :value="sample.id">
              {{ sample.name }}
            </option>
          </select>
        </label>

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

      <p class="status">{{ status }}</p>
      <p v-if="infoMessage" class="info">{{ infoMessage }}</p>
      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
    </section>

    <section class="card">
      <div class="editor-head">
        <h2>SQL Editor</h2>
        <button type="button" @click="runQuery" :disabled="isBusy">Abfrage ausfuehren</button>
      </div>
      <MonacoSqlEditor v-model="query" />
    </section>

    <section class="card">
      <h2>Ergebnis</h2>
      <ResultTable v-if="resultColumns.length > 0" :columns="resultColumns" :rows="resultRows" />
      <p v-else class="empty">Noch keine Ergebniszeilen vorhanden.</p>
    </section>
  </main>
</template>
