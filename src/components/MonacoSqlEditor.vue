<script setup lang="ts">
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api';
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';
import 'monaco-editor/esm/vs/basic-languages/sql/sql.contribution';
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = defineProps<{
  modelValue: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const container = ref<HTMLElement | null>(null);
let editor: monaco.editor.IStandaloneCodeEditor | null = null;

(globalThis as typeof globalThis & {
  MonacoEnvironment?: {
    getWorker: () => Worker;
  };
}).MonacoEnvironment = {
  getWorker: () => {
    return new EditorWorker();
  }
};

onMounted(() => {
  if (!container.value) {
    return;
  }

  editor = monaco.editor.create(container.value, {
    value: props.modelValue,
    language: 'sql',
    automaticLayout: true,
    minimap: {
      enabled: false
    },
    fontSize: 14,
    lineNumbersMinChars: 3,
    padding: {
      top: 12,
      bottom: 12
    },
    theme: 'vs'
  });

  editor.onDidChangeModelContent(() => {
    if (!editor) {
      return;
    }

    emit('update:modelValue', editor.getValue());
  });
});

watch(
  () => props.modelValue,
  (nextValue) => {
    if (!editor) {
      return;
    }

    const currentValue = editor.getValue();
    if (currentValue !== nextValue) {
      editor.setValue(nextValue);
    }
  }
);

onBeforeUnmount(() => {
  editor?.dispose();
  editor = null;
});
</script>

<template>
  <div ref="container" class="editor-shell" />
</template>

<style scoped>
.editor-shell {
  width: 100%;
  height: 320px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
  background: #ffffff;
}
</style>
