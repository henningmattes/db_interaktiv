# SQL Browser Lab (Vue 3 + TypeScript)

Didaktische SQL-Seite, bei der SQLite komplett im Browser via WebAssembly laeuft.

## Stack

- Vue 3 + TypeScript + Vite
- sql.js (SQLite WASM)
- Web Worker fuer Query-Ausfuehrung
- TanStack Table fuer Ergebnisdarstellung
- Monaco Editor mit SQL-Highlighting

## Start

```bash
npm install
npm run dev
```

## Features

- Zwei Beispiel-Datenbanken (`Schule`, `Shop`)
- Eigene SQL-Datei (`.sql`) laden
- SQL-Abfragen im Editor ausfuehren
- Ergebnisse tabellarisch anzeigen
- Alles laeuft lokal im Browser (kein Server-Backend)
