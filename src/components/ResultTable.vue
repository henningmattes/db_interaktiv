<script setup lang="ts">
import { FlexRender, createColumnHelper, getCoreRowModel, useVueTable } from '@tanstack/vue-table';
import { computed } from 'vue';

const props = defineProps<{
  columns: string[];
  rows: Record<string, unknown>[];
}>();

const columnHelper = createColumnHelper<Record<string, unknown>>();

const tableColumns = computed(() => {
  return props.columns.map((columnName) => {
    return columnHelper.accessor((row) => row[columnName], {
      id: columnName,
      header: () => columnName,
      cell: (info) => {
        const value = info.getValue();
        return value == null ? '' : String(value);
      }
    });
  });
});

const table = useVueTable({
  get data() {
    return props.rows;
  },
  get columns() {
    return tableColumns.value;
  },
  getCoreRowModel: getCoreRowModel()
});
</script>

<template>
  <div class="table-wrap">
    <table>
      <thead>
        <tr v-for="headerGroup in table.getHeaderGroups()" :key="headerGroup.id">
          <th v-for="header in headerGroup.headers" :key="header.id">
            <FlexRender
              v-if="!header.isPlaceholder"
              :render="header.column.columnDef.header"
              :props="header.getContext()"
            />
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in table.getRowModel().rows" :key="row.id">
          <td v-for="cell in row.getVisibleCells()" :key="cell.id">
            <FlexRender :render="cell.column.columnDef.cell" :props="cell.getContext()" />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-wrap {
  overflow: auto;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: #ffffff;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 640px;
}

th,
td {
  text-align: left;
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid #ebedf0;
  font-size: 0.92rem;
}

th {
  position: sticky;
  top: 0;
  background: #f8fafb;
  color: #264653;
  font-weight: 600;
}

tbody tr:hover {
  background: #f3f8fb;
}
</style>
