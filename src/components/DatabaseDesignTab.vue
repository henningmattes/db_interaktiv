<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import type { DatabaseSchema } from '../types/sqlWorker';
import {
  erModelToRelational,
  inferPrimaryAttributes,
  parseFunctionalDependencies,
  relationalSchemaToSql,
  relationalToErModel,
  type ERCardinality,
  type ERAttribute,
  type ERModel,
  type FunctionalDependency
} from '../lib/databaseDesign';

const props = defineProps<{
  schema: DatabaseSchema;
  isBusy: boolean;
}>();

const emit = defineEmits<{
  loadDesignedSchema: [payload: { name: string; sql: string }];
}>();

type DiagramNode = {
  key: string;
  id: string;
  label: string;
  kind: 'entity' | 'relationship';
  x: number;
  y: number;
  width: number;
  height: number;
  attributes: ERAttribute[];
  endpoints: { entityId: string; cardinality: '1' | 'N' }[];
};

type DragState = {
  key: string;
  pointerOffsetX: number;
  pointerOffsetY: number;
};

type TableInference = {
  candidateKeys: string[][];
  primaryAttributes: Set<string>;
  errors: string[];
};

type FdAttributeNode = {
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

type FdDeterminantNode = {
  key: string;
  left: string[];
  right: string[];
  x: number;
  y: number;
  width: number;
  height: number;
};

const ENTITY_WIDTH = 220;
const RELATIONSHIP_WIDTH = 180;
const MIN_ENTITY_HEIGHT = 82;
const MIN_RELATIONSHIP_HEIGHT = 84;
const FD_NODE_WIDTH = 128;
const FD_NODE_HEIGHT = 42;
const FD_DETERMINANT_WIDTH = 176;
const FD_DETERMINANT_HEIGHT = 46;

const erModel = ref<ERModel>({ entities: [], relationships: [] });
const erJson = ref('');
const hasManualErChanges = ref(false);

const designInfo = ref('');
const designError = ref('');

const diagramRef = ref<HTMLElement | null>(null);
const diagramSize = reactive({
  width: 1200,
  height: 760
});
const positions = reactive<Record<string, { x: number; y: number }>>({});
let dragState: DragState | null = null;
const linkDraft = reactive({
  isActive: false,
  sourceEntityId: '',
  x: 0,
  y: 0
});
let resizeObserver: ResizeObserver | null = null;

const fdByTable = reactive<Record<string, string>>({});
const selectedFdTable = ref('');
const selectedFdDeterminantKey = ref('');
const fdDraftLeftAttributes = ref<string[]>([]);
const fdDraftRightAttribute = ref('');
const selectedEntityId = ref('');
const selectedRelationshipId = ref('');

const newEntityName = ref('');
const newEntityPrimaryAttribute = reactive({
  name: 'id',
  type: 'INTEGER'
});

const newEntityAttribute = reactive({
  name: '',
  type: 'TEXT',
  isPrimaryKey: false
});

const relationshipDraft = reactive({
  name: '',
  leftEntityId: '',
  rightEntityId: '',
  leftCardinality: 'N' as ERCardinality,
  rightCardinality: 'N' as ERCardinality
});

const relationshipAttributeDraft = reactive({
  name: '',
  type: 'TEXT',
  isPrimaryKey: false
});

const entityKey = (entityId: string): string => `entity:${entityId}`;
const relationshipKey = (relationshipId: string): string => `relationship:${relationshipId}`;

const clearStatus = (): void => {
  designInfo.value = '';
  designError.value = '';
};

const syncErJson = (): void => {
  erJson.value = JSON.stringify(erModel.value, null, 2);
};

const toId = (value: string): string => {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_]/g, '');

  return normalized.length > 0 ? normalized : 'item';
};

const ensureUniqueId = (preferred: string, used: Set<string>): string => {
  if (!used.has(preferred)) {
    return preferred;
  }

  let index = 2;
  let next = `${preferred}_${index}`;

  while (used.has(next)) {
    index += 1;
    next = `${preferred}_${index}`;
  }

  return next;
};

const applyManualChange = (message: string): void => {
  hasManualErChanges.value = true;
  layoutNodes();
  syncErJson();
  clearStatus();
  designInfo.value = message;
};

const refreshDiagramSize = (): void => {
  if (!diagramRef.value) {
    return;
  }

  const bounds = diagramRef.value.getBoundingClientRect();
  diagramSize.width = Math.max(1, Math.round(bounds.width));
  diagramSize.height = Math.max(1, Math.round(bounds.height));
};

const layoutNodes = (): void => {
  const keysInModel = new Set<string>();
  const allItems: Array<{ key: string }> = [];
  const columnsPerRow = Math.max(1, Math.floor(Math.max(diagramSize.width - 48, 220) / 240));

  erModel.value.entities.forEach((entity) => {
    const key = entityKey(entity.id);
    keysInModel.add(key);
    allItems.push({ key });
  });

  erModel.value.relationships.forEach((relationship) => {
    const key = relationshipKey(relationship.id);
    keysInModel.add(key);
    allItems.push({ key });
  });

  allItems.forEach((item, index) => {
    if (positions[item.key]) {
      return;
    }

    const column = index % columnsPerRow;
    const row = Math.floor(index / columnsPerRow);
    positions[item.key] = {
      x: 24 + column * 240,
      y: 24 + row * 170
    };
  });

  for (const key of Object.keys(positions)) {
    if (!keysInModel.has(key)) {
      delete positions[key];
    }
  }
};

const buildErFromSchema = (): void => {
  erModel.value = relationalToErModel(props.schema);
  hasManualErChanges.value = false;
  layoutNodes();
  syncErJson();
  clearStatus();
  designInfo.value = 'ER-Modell aus dem aktuellen Relationenschema erzeugt.';
};

watch(
  () => props.schema,
  () => {
    if (!hasManualErChanges.value) {
      buildErFromSchema();
    }
  },
  { deep: true, immediate: true }
);

watch(
  () => props.schema.map((table) => table.name),
  (tableNames) => {
    if (tableNames.length === 0) {
      selectedFdTable.value = '';
      return;
    }

    if (!tableNames.includes(selectedFdTable.value)) {
      selectedFdTable.value = tableNames[0];
    }
  },
  { immediate: true }
);

const selectedEntity = computed(() => {
  return erModel.value.entities.find((entity) => entity.id === selectedEntityId.value) ?? null;
});

const selectedRelationship = computed(() => {
  return erModel.value.relationships.find((relationship) => relationship.id === selectedRelationshipId.value) ?? null;
});

watch(
  () => erModel.value.entities.map((entity) => entity.id),
  (entityIds) => {
    if (entityIds.length === 0) {
      selectedEntityId.value = '';
      relationshipDraft.leftEntityId = '';
      relationshipDraft.rightEntityId = '';
      return;
    }

    if (!entityIds.includes(selectedEntityId.value)) {
      selectedEntityId.value = entityIds[0];
    }

    if (!entityIds.includes(relationshipDraft.leftEntityId)) {
      relationshipDraft.leftEntityId = entityIds[0];
    }

    if (!entityIds.includes(relationshipDraft.rightEntityId)) {
      relationshipDraft.rightEntityId = entityIds[Math.min(1, entityIds.length - 1)];
    }
  },
  { immediate: true }
);

watch(
  () => erModel.value.relationships.map((relationship) => relationship.id),
  (relationshipIds) => {
    if (relationshipIds.length === 0) {
      selectedRelationshipId.value = '';
      return;
    }

    if (!relationshipIds.includes(selectedRelationshipId.value)) {
      selectedRelationshipId.value = relationshipIds[0];
    }
  },
  { immediate: true }
);

const parseErModel = (value: unknown): ERModel => {
  if (typeof value !== 'object' || value == null) {
    throw new Error('JSON muss ein Objekt sein.');
  }

  const candidate = value as { entities?: unknown; relationships?: unknown };
  if (!Array.isArray(candidate.entities) || !Array.isArray(candidate.relationships)) {
    throw new Error('JSON muss die Felder entities[] und relationships[] enthalten.');
  }

  const entities = candidate.entities.map((entity, index) => {
    if (typeof entity !== 'object' || entity == null) {
      throw new Error(`Entity ${index + 1} ist ungueltig.`);
    }

    const rawEntity = entity as {
      id?: unknown;
      name?: unknown;
      attributes?: unknown;
    };

    if (typeof rawEntity.id !== 'string' || rawEntity.id.trim().length === 0) {
      throw new Error(`Entity ${index + 1}: id fehlt.`);
    }

    if (!Array.isArray(rawEntity.attributes)) {
      throw new Error(`Entity ${rawEntity.id}: attributes[] fehlt.`);
    }

    const attributes = rawEntity.attributes.map((attribute, attributeIndex) => {
      if (typeof attribute !== 'object' || attribute == null) {
        throw new Error(`Entity ${rawEntity.id}: Attribut ${attributeIndex + 1} ist ungueltig.`);
      }

      const rawAttribute = attribute as {
        name?: unknown;
        type?: unknown;
        isPrimaryKey?: unknown;
      };

      if (typeof rawAttribute.name !== 'string' || rawAttribute.name.trim().length === 0) {
        throw new Error(`Entity ${rawEntity.id}: Attribut ${attributeIndex + 1} ohne Namen.`);
      }

      return {
        name: rawAttribute.name,
        type: typeof rawAttribute.type === 'string' ? rawAttribute.type : 'TEXT',
        isPrimaryKey: Boolean(rawAttribute.isPrimaryKey)
      };
    });

    return {
      id: rawEntity.id,
      name: typeof rawEntity.name === 'string' && rawEntity.name.trim().length > 0 ? rawEntity.name : rawEntity.id,
      attributes
    };
  });

  const entityIds = new Set(entities.map((entity) => entity.id));

  const relationships = candidate.relationships.map((relationship, index) => {
    if (typeof relationship !== 'object' || relationship == null) {
      throw new Error(`Relationship ${index + 1} ist ungueltig.`);
    }

    const rawRelationship = relationship as {
      id?: unknown;
      name?: unknown;
      endpoints?: unknown;
      attributes?: unknown;
    };

    if (typeof rawRelationship.id !== 'string' || rawRelationship.id.trim().length === 0) {
      throw new Error(`Relationship ${index + 1}: id fehlt.`);
    }

    if (!Array.isArray(rawRelationship.endpoints) || rawRelationship.endpoints.length < 2) {
      throw new Error(`Relationship ${rawRelationship.id}: mind. zwei Endpunkte notwendig.`);
    }

    const endpoints = rawRelationship.endpoints.map((endpoint, endpointIndex) => {
      if (typeof endpoint !== 'object' || endpoint == null) {
        throw new Error(`Relationship ${rawRelationship.id}: Endpunkt ${endpointIndex + 1} ist ungueltig.`);
      }

      const rawEndpoint = endpoint as {
        entityId?: unknown;
        cardinality?: unknown;
      };

      if (typeof rawEndpoint.entityId !== 'string' || !entityIds.has(rawEndpoint.entityId)) {
        throw new Error(`Relationship ${rawRelationship.id}: Endpunkt ${endpointIndex + 1} verweist auf unbekannte Entity.`);
      }

      const cardinality: '1' | 'N' = rawEndpoint.cardinality === '1' ? '1' : 'N';

      return {
        entityId: rawEndpoint.entityId,
        cardinality
      };
    });

    const attributes = Array.isArray(rawRelationship.attributes)
      ? rawRelationship.attributes.map((attribute) => {
          if (typeof attribute !== 'object' || attribute == null) {
            return {
              name: 'attribute',
              type: 'TEXT',
              isPrimaryKey: false
            };
          }

          const rawAttribute = attribute as {
            name?: unknown;
            type?: unknown;
            isPrimaryKey?: unknown;
          };

          return {
            name: typeof rawAttribute.name === 'string' && rawAttribute.name.trim().length > 0 ? rawAttribute.name : 'attribute',
            type: typeof rawAttribute.type === 'string' ? rawAttribute.type : 'TEXT',
            isPrimaryKey: Boolean(rawAttribute.isPrimaryKey)
          };
        })
      : [];

    return {
      id: rawRelationship.id,
      name:
        typeof rawRelationship.name === 'string' && rawRelationship.name.trim().length > 0
          ? rawRelationship.name
          : rawRelationship.id,
      endpoints,
      attributes
    };
  });

  return {
    entities,
    relationships
  };
};

const applyErJson = (): void => {
  clearStatus();

  try {
    const parsed = JSON.parse(erJson.value) as unknown;
    erModel.value = parseErModel(parsed);
    hasManualErChanges.value = true;
    layoutNodes();
    syncErJson();
    designInfo.value = 'ER-Modell aus JSON uebernommen.';
  } catch (error) {
    designError.value = error instanceof Error ? error.message : 'ER-JSON konnte nicht verarbeitet werden.';
  }
};

const addEntity = (): void => {
  clearStatus();

  const label = newEntityName.value.trim();
  if (!label) {
    designError.value = 'Bitte einen Entity-Namen eingeben.';
    return;
  }

  const primaryAttributeName = newEntityPrimaryAttribute.name.trim();
  if (!primaryAttributeName) {
    designError.value = 'Bitte ein Primaerschluesselattribut fuer die neue Entity angeben.';
    return;
  }

  const entityId = ensureUniqueId(toId(label), new Set(erModel.value.entities.map((entity) => entity.id)));

  erModel.value.entities.push({
    id: entityId,
    name: label,
    attributes: [
      {
        name: primaryAttributeName,
        type: newEntityPrimaryAttribute.type.trim() || 'INTEGER',
        isPrimaryKey: true
      }
    ]
  });

  selectedEntityId.value = entityId;
  newEntityName.value = '';

  applyManualChange(`Entity "${entityId}" angelegt.`);
};

const removeSelectedEntity = (): void => {
  clearStatus();

  const entity = selectedEntity.value;
  if (!entity) {
    designError.value = 'Bitte zuerst eine Entity auswaehlen.';
    return;
  }

  const targetId = entity.id;
  erModel.value.entities = erModel.value.entities.filter((candidate) => candidate.id !== targetId);
  erModel.value.relationships = erModel.value.relationships
    .map((relationship) => ({
      ...relationship,
      endpoints: relationship.endpoints.filter((endpoint) => endpoint.entityId !== targetId)
    }))
    .filter((relationship) => relationship.endpoints.length >= 2);

  applyManualChange(`Entity "${targetId}" entfernt.`);
};

const saveSelectedEntityLabel = (): void => {
  clearStatus();

  if (!selectedEntity.value) {
    designError.value = 'Bitte zuerst eine Entity auswaehlen.';
    return;
  }

  const nextLabel = selectedEntity.value.name.trim();
  if (!nextLabel) {
    designError.value = 'Entity-Name darf nicht leer sein.';
    return;
  }

  selectedEntity.value.name = nextLabel;
  applyManualChange(`Entity "${selectedEntity.value.id}" aktualisiert.`);
};

const addAttributeToSelectedEntity = (): void => {
  clearStatus();

  if (!selectedEntity.value) {
    designError.value = 'Bitte zuerst eine Entity auswaehlen.';
    return;
  }

  const attributeName = newEntityAttribute.name.trim();
  if (!attributeName) {
    designError.value = 'Bitte Attributnamen eingeben.';
    return;
  }

  const alreadyExists = selectedEntity.value.attributes.some((attribute) => attribute.name === attributeName);
  if (alreadyExists) {
    designError.value = `Attribut "${attributeName}" existiert bereits in dieser Entity.`;
    return;
  }

  selectedEntity.value.attributes.push({
    name: attributeName,
    type: newEntityAttribute.type.trim() || 'TEXT',
    isPrimaryKey: newEntityAttribute.isPrimaryKey
  });

  newEntityAttribute.name = '';
  newEntityAttribute.type = 'TEXT';
  newEntityAttribute.isPrimaryKey = false;
  applyManualChange(`Attribut "${attributeName}" hinzugefuegt.`);
};

const removeAttributeFromSelectedEntity = (attributeName: string): void => {
  clearStatus();

  if (!selectedEntity.value) {
    designError.value = 'Bitte zuerst eine Entity auswaehlen.';
    return;
  }

  if (selectedEntity.value.attributes.length <= 1) {
    designError.value = 'Eine Entity muss mindestens ein Attribut behalten.';
    return;
  }

  selectedEntity.value.attributes = selectedEntity.value.attributes.filter((attribute) => attribute.name !== attributeName);
  applyManualChange(`Attribut "${attributeName}" entfernt.`);
};

const toggleEntityAttributePrimary = (attributeName: string): void => {
  clearStatus();

  if (!selectedEntity.value) {
    return;
  }

  const attribute = selectedEntity.value.attributes.find((candidate) => candidate.name === attributeName);
  if (!attribute) {
    return;
  }

  attribute.isPrimaryKey = !attribute.isPrimaryKey;
  applyManualChange(`Primaerschluessel-Markierung fuer "${attributeName}" aktualisiert.`);
};

const createRelationshipBetweenEntities = (
  leftEntityId: string,
  rightEntityId: string,
  leftCardinality: ERCardinality,
  rightCardinality: ERCardinality,
  name?: string
): void => {
  const relationshipLabel = name?.trim().length ? name.trim() : `${leftEntityId}_${rightEntityId}`;
  const relationshipId = ensureUniqueId(
    toId(relationshipLabel),
    new Set(erModel.value.relationships.map((relationship) => relationship.id))
  );

  erModel.value.relationships.push({
    id: relationshipId,
    name: relationshipLabel,
    endpoints: [
      {
        entityId: leftEntityId,
        cardinality: leftCardinality
      },
      {
        entityId: rightEntityId,
        cardinality: rightCardinality
      }
    ],
    attributes: []
  });

  selectedRelationshipId.value = relationshipId;
  applyManualChange(`Beziehung "${relationshipId}" angelegt.`);
};

const addRelationship = (): void => {
  clearStatus();

  if (erModel.value.entities.length < 2) {
    designError.value = 'Mindestens zwei Entities sind fuer eine Beziehung erforderlich.';
    return;
  }

  if (!relationshipDraft.leftEntityId || !relationshipDraft.rightEntityId) {
    designError.value = 'Bitte beide Endpunkte fuer die neue Beziehung auswaehlen.';
    return;
  }

  createRelationshipBetweenEntities(
    relationshipDraft.leftEntityId,
    relationshipDraft.rightEntityId,
    relationshipDraft.leftCardinality,
    relationshipDraft.rightCardinality,
    relationshipDraft.name
  );
  relationshipDraft.name = '';
};

const removeSelectedRelationship = (): void => {
  clearStatus();

  if (!selectedRelationship.value) {
    designError.value = 'Bitte zuerst eine Beziehung auswaehlen.';
    return;
  }

  const relationshipId = selectedRelationship.value.id;
  erModel.value.relationships = erModel.value.relationships.filter((relationship) => relationship.id !== relationshipId);
  applyManualChange(`Beziehung "${relationshipId}" entfernt.`);
};

const saveSelectedRelationshipLabel = (): void => {
  clearStatus();

  if (!selectedRelationship.value) {
    designError.value = 'Bitte zuerst eine Beziehung auswaehlen.';
    return;
  }

  const nextLabel = selectedRelationship.value.name.trim();
  if (!nextLabel) {
    designError.value = 'Beziehungsname darf nicht leer sein.';
    return;
  }

  selectedRelationship.value.name = nextLabel;
  applyManualChange(`Beziehung "${selectedRelationship.value.id}" aktualisiert.`);
};

const addEndpointToSelectedRelationship = (): void => {
  clearStatus();

  if (!selectedRelationship.value || erModel.value.entities.length === 0) {
    designError.value = 'Bitte zuerst eine Beziehung und mindestens eine Entity auswaehlen.';
    return;
  }

  selectedRelationship.value.endpoints.push({
    entityId: erModel.value.entities[0].id,
    cardinality: 'N'
  });

  applyManualChange(`Neuer Endpunkt fuer "${selectedRelationship.value.id}" hinzugefuegt.`);
};

const removeEndpointFromSelectedRelationship = (index: number): void => {
  clearStatus();

  if (!selectedRelationship.value) {
    return;
  }

  if (selectedRelationship.value.endpoints.length <= 2) {
    designError.value = 'Eine Beziehung benoetigt mindestens zwei Endpunkte.';
    return;
  }

  selectedRelationship.value.endpoints.splice(index, 1);
  applyManualChange(`Endpunkt aus "${selectedRelationship.value.id}" entfernt.`);
};

const updateSelectedRelationshipEndpointEntity = (index: number, entityId: string): void => {
  clearStatus();

  if (!selectedRelationship.value || !erModel.value.entities.some((entity) => entity.id === entityId)) {
    return;
  }

  if (!selectedRelationship.value.endpoints[index]) {
    return;
  }

  selectedRelationship.value.endpoints[index].entityId = entityId;
  applyManualChange(`Endpunkt ${index + 1} aktualisiert.`);
};

const updateSelectedRelationshipEndpointCardinality = (index: number, cardinality: ERCardinality): void => {
  clearStatus();

  if (!selectedRelationship.value || !selectedRelationship.value.endpoints[index]) {
    return;
  }

  selectedRelationship.value.endpoints[index].cardinality = cardinality;
  applyManualChange(`Kardinalitaet fuer Endpunkt ${index + 1} aktualisiert.`);
};

const addAttributeToSelectedRelationship = (): void => {
  clearStatus();

  if (!selectedRelationship.value) {
    designError.value = 'Bitte zuerst eine Beziehung auswaehlen.';
    return;
  }

  const attributeName = relationshipAttributeDraft.name.trim();
  if (!attributeName) {
    designError.value = 'Bitte Attributnamen eingeben.';
    return;
  }

  const alreadyExists = selectedRelationship.value.attributes.some((attribute) => attribute.name === attributeName);
  if (alreadyExists) {
    designError.value = `Attribut "${attributeName}" existiert bereits in dieser Beziehung.`;
    return;
  }

  selectedRelationship.value.attributes.push({
    name: attributeName,
    type: relationshipAttributeDraft.type.trim() || 'TEXT',
    isPrimaryKey: relationshipAttributeDraft.isPrimaryKey
  });

  relationshipAttributeDraft.name = '';
  relationshipAttributeDraft.type = 'TEXT';
  relationshipAttributeDraft.isPrimaryKey = false;
  applyManualChange(`Beziehungsattribut "${attributeName}" hinzugefuegt.`);
};

const removeAttributeFromSelectedRelationship = (attributeName: string): void => {
  clearStatus();

  if (!selectedRelationship.value) {
    return;
  }

  selectedRelationship.value.attributes = selectedRelationship.value.attributes.filter(
    (attribute) => attribute.name !== attributeName
  );
  applyManualChange(`Beziehungsattribut "${attributeName}" entfernt.`);
};

const toggleRelationshipAttributePrimary = (attributeName: string): void => {
  clearStatus();

  if (!selectedRelationship.value) {
    return;
  }

  const attribute = selectedRelationship.value.attributes.find((candidate) => candidate.name === attributeName);
  if (!attribute) {
    return;
  }

  attribute.isPrimaryKey = !attribute.isPrimaryKey;
  applyManualChange(`Primaerschluessel-Markierung fuer "${attributeName}" aktualisiert.`);
};

const generatedSchema = computed<DatabaseSchema>(() => {
  return erModelToRelational(erModel.value);
});

const generatedSql = computed(() => {
  return relationalSchemaToSql(generatedSchema.value);
});

const loadGeneratedSchema = (): void => {
  clearStatus();

  if (generatedSchema.value.length === 0) {
    designError.value = 'Kein relationales Schema vorhanden.';
    return;
  }

  emit('loadDesignedSchema', {
    name: 'Entwurf aus ER-Modell',
    sql: generatedSql.value
  });

  designInfo.value = 'Generiertes Relationenschema als aktive Datenbank geladen.';
};

const sortAttributes = (values: string[]): string[] => {
  return [...values].sort((left, right) => left.localeCompare(right));
};

const determinantKey = (attributes: string[]): string => {
  return sortAttributes([...new Set(attributes)]).join('|');
};

const formatDeterminantLabel = (attributes: string[]): string => {
  return `{${sortAttributes(attributes).join(', ')}}`;
};

const parseDeterminantKey = (key: string): string[] => {
  return key
    .split('|')
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
};

const normalizeDependencies = (
  dependencies: FunctionalDependency[],
  allowedAttributes: string[]
): FunctionalDependency[] => {
  const allowed = new Set(allowedAttributes);
  const grouped = new Map<string, { left: string[]; right: Set<string> }>();

  for (const dependency of dependencies) {
    const left = sortAttributes(
      [...new Set(dependency.left.map((item) => item.trim()).filter((item) => allowed.has(item)))]
    );
    const right = sortAttributes(
      [...new Set(dependency.right.map((item) => item.trim()).filter((item) => allowed.has(item)))]
    );

    if (left.length === 0 || right.length === 0) {
      continue;
    }

    const key = determinantKey(left);
    if (!grouped.has(key)) {
      grouped.set(key, {
        left,
        right: new Set()
      });
    }

    right.forEach((attribute) => grouped.get(key)?.right.add(attribute));
  }

  return [...grouped.values()]
    .map((entry) => ({
      left: entry.left,
      right: sortAttributes([...entry.right])
    }))
    .sort((left, right) => determinantKey(left.left).localeCompare(determinantKey(right.left)));
};

const serializeDependencies = (dependencies: FunctionalDependency[]): string => {
  return dependencies.map((dependency) => `${dependency.left.join(',')} -> ${dependency.right.join(',')}`).join('\n');
};

const selectedFdTableSchema = computed(() => {
  return props.schema.find((table) => table.name === selectedFdTable.value) ?? null;
});

const selectedFdAttributes = computed(() => {
  return selectedFdTableSchema.value?.columns.map((column) => column.name) ?? [];
});

const selectedFdParsing = computed(() => {
  if (!selectedFdTable.value) {
    return {
      dependencies: [] as FunctionalDependency[],
      errors: [] as string[]
    };
  }

  const parsed = parseFunctionalDependencies(fdByTable[selectedFdTable.value] ?? '');
  return {
    dependencies: normalizeDependencies(parsed.dependencies, selectedFdAttributes.value),
    errors: parsed.errors
  };
});

const canEditFdGraph = computed(() => {
  return selectedFdParsing.value.errors.length === 0 && selectedFdAttributes.value.length > 0;
});

const updateSelectedTableDependencies = (dependencies: FunctionalDependency[]): void => {
  if (!selectedFdTable.value) {
    return;
  }

  const normalized = normalizeDependencies(dependencies, selectedFdAttributes.value);
  fdByTable[selectedFdTable.value] = serializeDependencies(normalized);
};

const withSelectedDependencies = (updater: (dependencies: FunctionalDependency[]) => FunctionalDependency[]): void => {
  clearStatus();

  if (!canEditFdGraph.value) {
    designError.value = 'Bitte zuerst syntaktisch gueltige FDs eingeben.';
    return;
  }

  const next = updater(selectedFdParsing.value.dependencies);
  updateSelectedTableDependencies(next);
};

const fdDraftLeftLabel = computed(() => {
  if (fdDraftLeftAttributes.value.length === 0) {
    return '{ }';
  }

  return `{ ${sortAttributes(fdDraftLeftAttributes.value).join(', ')} }`;
});

const fdDeterminantNodes = computed<FdDeterminantNode[]>(() => {
  const dependencies = selectedFdParsing.value.dependencies;
  if (dependencies.length === 0) {
    return [];
  }

  const slotWidth = FD_DETERMINANT_WIDTH + 26;
  const columns = Math.max(1, Math.floor((diagramSize.width - 24) / slotWidth));
  const top = 148;

  return dependencies.map((dependency, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    return {
      key: determinantKey(dependency.left),
      left: dependency.left,
      right: dependency.right,
      x: 12 + column * slotWidth,
      y: top + row * 76,
      width: FD_DETERMINANT_WIDTH,
      height: FD_DETERMINANT_HEIGHT
    };
  });
});

const fdAttributeNodes = computed<FdAttributeNode[]>(() => {
  const attributes = selectedFdAttributes.value;
  if (attributes.length === 0) {
    return [];
  }

  const slotWidth = FD_NODE_WIDTH + 24;
  const columns = Math.max(1, Math.floor((diagramSize.width - 24) / slotWidth));

  return attributes.map((attribute, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    return {
      name: attribute,
      x: 12 + column * slotWidth,
      y: 18 + row * 56,
      width: FD_NODE_WIDTH,
      height: FD_NODE_HEIGHT
    };
  });
});

const fdDeterminantByKey = computed(() => {
  return new Map(fdDeterminantNodes.value.map((node) => [node.key, node]));
});

const selectedFdDeterminant = computed(() => {
  return fdDeterminantByKey.value.get(selectedFdDeterminantKey.value) ?? null;
});

const selectedFdAttributeSet = computed(() => {
  return new Set(selectedFdAttributes.value);
});

watch(
  () => selectedFdAttributes.value,
  (attributes) => {
    const allowed = new Set(attributes);
    fdDraftLeftAttributes.value = sortAttributes(fdDraftLeftAttributes.value.filter((attribute) => allowed.has(attribute)));

    if (!allowed.has(fdDraftRightAttribute.value)) {
      fdDraftRightAttribute.value = attributes[0] ?? '';
    }
  },
  { immediate: true, deep: true }
);

watch(
  () => fdDeterminantNodes.value.map((node) => node.key),
  (keys) => {
    if (selectedFdDeterminantKey.value && !keys.includes(selectedFdDeterminantKey.value)) {
      selectedFdDeterminantKey.value = '';
    }
  },
  { immediate: true }
);

const toggleDraftLeftAttribute = (attribute: string): void => {
  if (!selectedFdAttributeSet.value.has(attribute)) {
    return;
  }

  if (fdDraftLeftAttributes.value.includes(attribute)) {
    fdDraftLeftAttributes.value = fdDraftLeftAttributes.value.filter((item) => item !== attribute);
    return;
  }

  fdDraftLeftAttributes.value = sortAttributes([...fdDraftLeftAttributes.value, attribute]);
};

const selectDeterminantFromDraft = (): void => {
  clearStatus();

  if (fdDraftLeftAttributes.value.length === 0) {
    designError.value = 'Bitte erst Attribute fuer die linke Seite auswaehlen.';
    return;
  }

  const key = determinantKey(fdDraftLeftAttributes.value);
  if (!fdDeterminantByKey.value.has(key)) {
    designError.value = 'Diese Determinante existiert noch nicht. Fuege zuerst eine FD hinzu.';
    return;
  }

  selectedFdDeterminantKey.value = key;
  designInfo.value = `Determinante ${fdDraftLeftLabel.value} ausgewaehlt.`;
};

const addFdFromDraft = (): void => {
  clearStatus();

  if (!canEditFdGraph.value) {
    designError.value = 'Bitte zuerst syntaktisch gueltige FDs eingeben.';
    return;
  }

  if (fdDraftLeftAttributes.value.length === 0 || !fdDraftRightAttribute.value) {
    designError.value = 'Bitte linke Attributmenge und rechtes Attribut waehlen.';
    return;
  }

  const left = sortAttributes(fdDraftLeftAttributes.value);
  const right = fdDraftRightAttribute.value;

  withSelectedDependencies((dependencies) => {
    const key = determinantKey(left);
    const next = dependencies.map((dependency) => ({
      left: [...dependency.left],
      right: [...dependency.right]
    }));

    const existing = next.find((dependency) => determinantKey(dependency.left) === key);
    if (existing) {
      if (!existing.right.includes(right)) {
        existing.right = sortAttributes([...existing.right, right]);
      }
    } else {
      next.push({
        left,
        right: [right]
      });
    }

    return next;
  });

  selectedFdDeterminantKey.value = determinantKey(left);
  designInfo.value = `FD ${fdDraftLeftLabel.value} -> ${right} hinzugefuegt.`;
};

const removeSelectedFdDeterminant = (): void => {
  clearStatus();

  if (!selectedFdDeterminant.value) {
    designError.value = 'Bitte zuerst eine Determinante auswaehlen.';
    return;
  }

  const key = selectedFdDeterminant.value.key;
  withSelectedDependencies((dependencies) => {
    return dependencies.filter((dependency) => determinantKey(dependency.left) !== key);
  });

  selectedFdDeterminantKey.value = '';
  designInfo.value = 'Determinante und zugehoerige FDs entfernt.';
};

const toggleDependencyForSelectedDeterminant = (attribute: string): void => {
  clearStatus();

  const selected = selectedFdDeterminant.value;
  if (!selected) {
    toggleDraftLeftAttribute(attribute);
    return;
  }

  withSelectedDependencies((dependencies) => {
    const key = selected.key;
    const next = dependencies.map((dependency) => ({
      left: [...dependency.left],
      right: [...dependency.right]
    }));
    const target = next.find((dependency) => determinantKey(dependency.left) === key);

    if (!target) {
      next.push({
        left: selected.left,
        right: [attribute]
      });
      return next;
    }

    if (target.right.includes(attribute)) {
      target.right = target.right.filter((item) => item !== attribute);
    } else {
      target.right = sortAttributes([...target.right, attribute]);
    }

    return next.filter((dependency) => dependency.right.length > 0);
  });
};

const selectFdDeterminant = (key: string): void => {
  clearStatus();
  selectedFdDeterminantKey.value = key;
};

const resetFdGraphMode = (): void => {
  selectedFdDeterminantKey.value = '';
};

const isAttributeOnSelectedRightSide = (attribute: string): boolean => {
  return selectedFdDeterminant.value?.right.includes(attribute) ?? false;
};

const isAttributeInDraftLeftSide = (attribute: string): boolean => {
  return fdDraftLeftAttributes.value.includes(attribute);
};

const fdGraphEdges = computed(() => {
  const attributeMap = new Map(
    fdAttributeNodes.value.map((node) => [
      node.name,
      {
        cx: node.x + node.width / 2,
        cy: node.y + node.height / 2
      }
    ])
  );

  const compositionEdges: Array<{ id: string; x1: number; y1: number; x2: number; y2: number }> = [];
  const dependencyEdges: Array<{ id: string; x1: number; y1: number; x2: number; y2: number; isSelected: boolean }> = [];

  fdDeterminantNodes.value.forEach((determinant) => {
    determinant.left.forEach((attribute) => {
      const point = attributeMap.get(attribute);
      if (!point) {
        return;
      }

      compositionEdges.push({
        id: `composition-${determinant.key}-${attribute}`,
        x1: point.cx,
        y1: point.cy + FD_NODE_HEIGHT / 2 - 4,
        x2: determinant.x + determinant.width / 2,
        y2: determinant.y + 6
      });
    });

    determinant.right.forEach((attribute) => {
      const point = attributeMap.get(attribute);
      if (!point) {
        return;
      }

      dependencyEdges.push({
        id: `dependency-${determinant.key}-${attribute}`,
        x1: determinant.x + determinant.width / 2,
        y1: determinant.y + 6,
        x2: point.cx,
        y2: point.cy + FD_NODE_HEIGHT / 2 - 4,
        isSelected: determinant.key === selectedFdDeterminantKey.value
      });
    });
  });

  return {
    compositionEdges,
    dependencyEdges
  };
});

const fdGraphHeight = computed(() => {
  const attributeBottom = fdAttributeNodes.value.reduce((max, node) => Math.max(max, node.y + node.height), 0);
  const determinantBottom = fdDeterminantNodes.value.reduce((max, node) => Math.max(max, node.y + node.height), 0);
  return Math.max(260, attributeBottom + 24, determinantBottom + 24);
});

const currentFdInput = computed({
  get: () => {
    if (!selectedFdTable.value) {
      return '';
    }

    return fdByTable[selectedFdTable.value] ?? '';
  },
  set: (nextValue: string) => {
    if (!selectedFdTable.value) {
      return;
    }

    fdByTable[selectedFdTable.value] = nextValue;
  }
});

const buildInferenceForSchema = (schema: DatabaseSchema): Record<string, TableInference> => {
  const inference: Record<string, TableInference> = {};

  for (const table of schema) {
    const parsedDependencies = parseFunctionalDependencies(fdByTable[table.name] ?? '');
    const recognition = inferPrimaryAttributes(
      table.columns.map((column) => column.name),
      parsedDependencies.dependencies
    );

    inference[table.name] = {
      candidateKeys: recognition.candidateKeys,
      primaryAttributes: new Set(recognition.primaryAttributes),
      errors: parsedDependencies.errors
    };
  }

  return inference;
};

const sourceInference = computed(() => {
  return buildInferenceForSchema(props.schema);
});

const generatedInference = computed(() => {
  return buildInferenceForSchema(generatedSchema.value);
});

const selectedTableInference = computed(() => {
  if (!selectedFdTable.value) {
    return null;
  }

  return sourceInference.value[selectedFdTable.value] ?? null;
});

const selectedCandidateKeysText = computed(() => {
  if (!selectedTableInference.value) {
    return '';
  }

  return selectedTableInference.value.candidateKeys.map((candidateKey) => `{${candidateKey.join(', ')}}`).join(', ');
});

const entityNodes = computed<DiagramNode[]>(() => {
  return erModel.value.entities.map((entity) => {
    const key = entityKey(entity.id);
    const position = positions[key] ?? { x: 24, y: 24 };
    const height = Math.max(MIN_ENTITY_HEIGHT, 54 + entity.attributes.length * 18);

    return {
      key,
      id: entity.id,
      label: entity.name,
      kind: 'entity',
      x: position.x,
      y: position.y,
      width: ENTITY_WIDTH,
      height,
      attributes: entity.attributes,
      endpoints: []
    };
  });
});

const relationshipNodes = computed<DiagramNode[]>(() => {
  return erModel.value.relationships.map((relationship) => {
    const key = relationshipKey(relationship.id);
    const position = positions[key] ?? { x: 24, y: 24 };
    const endpointLines = Math.max(1, relationship.endpoints.length);
    const height = Math.max(MIN_RELATIONSHIP_HEIGHT, 44 + endpointLines * 16 + relationship.attributes.length * 14);

    return {
      key,
      id: relationship.id,
      label: relationship.name,
      kind: 'relationship',
      x: position.x,
      y: position.y,
      width: RELATIONSHIP_WIDTH,
      height,
      attributes: relationship.attributes,
      endpoints: relationship.endpoints
    };
  });
});

const nodeMap = computed(() => {
  const map = new Map<string, DiagramNode>();

  entityNodes.value.forEach((node) => map.set(node.key, node));
  relationshipNodes.value.forEach((node) => map.set(node.key, node));

  return map;
});

const toDiagramPoint = (event: PointerEvent): { x: number; y: number } | null => {
  if (!diagramRef.value) {
    return null;
  }

  const bounds = diagramRef.value.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(bounds.width, event.clientX - bounds.left)),
    y: Math.max(0, Math.min(bounds.height, event.clientY - bounds.top))
  };
};

const endLinkDrag = (): void => {
  linkDraft.isActive = false;
  linkDraft.sourceEntityId = '';
  window.removeEventListener('pointermove', onLinkDragMove);
  window.removeEventListener('pointerup', finishLinkDrag);
};

function onLinkDragMove(event: PointerEvent): void {
  if (!linkDraft.isActive) {
    return;
  }

  const point = toDiagramPoint(event);
  if (!point) {
    return;
  }

  linkDraft.x = point.x;
  linkDraft.y = point.y;
}

function finishLinkDrag(event: PointerEvent): void {
  if (!linkDraft.isActive) {
    return;
  }

  const sourceEntityId = linkDraft.sourceEntityId;
  const targetElement = document.elementFromPoint(event.clientX, event.clientY) as HTMLElement | null;
  const targetEntityId = targetElement?.closest<HTMLElement>('[data-entity-id]')?.dataset.entityId;

  endLinkDrag();

  if (!sourceEntityId || !targetEntityId || sourceEntityId === targetEntityId) {
    return;
  }

  createRelationshipBetweenEntities(
    sourceEntityId,
    targetEntityId,
    relationshipDraft.leftCardinality,
    relationshipDraft.rightCardinality
  );
}

const startLinkDrag = (event: PointerEvent, sourceEntityId: string): void => {
  clearStatus();
  if (props.isBusy || !diagramRef.value) {
    return;
  }

  event.preventDefault();
  event.stopPropagation();

  const sourceNode = nodeMap.value.get(entityKey(sourceEntityId));
  if (!sourceNode) {
    return;
  }

  const sourceX = sourceNode.x + sourceNode.width / 2;
  const sourceY = sourceNode.y + sourceNode.height / 2;

  linkDraft.isActive = true;
  linkDraft.sourceEntityId = sourceEntityId;
  linkDraft.x = sourceX;
  linkDraft.y = sourceY;

  const point = toDiagramPoint(event);
  if (point) {
    linkDraft.x = point.x;
    linkDraft.y = point.y;
  }

  window.addEventListener('pointermove', onLinkDragMove);
  window.addEventListener('pointerup', finishLinkDrag);
};

const activeLinkPreview = computed(() => {
  if (!linkDraft.isActive) {
    return null;
  }

  const sourceNode = nodeMap.value.get(entityKey(linkDraft.sourceEntityId));
  if (!sourceNode) {
    return null;
  }

  return {
    x1: sourceNode.x + sourceNode.width / 2,
    y1: sourceNode.y + sourceNode.height / 2,
    x2: linkDraft.x,
    y2: linkDraft.y
  };
});

const edges = computed(() => {
  const calculatedEdges: Array<{
    id: string;
    x1: number;
    y1: number;
    x2: number;
    y2: number;
    label: string;
    lx: number;
    ly: number;
  }> = [];

  relationshipNodes.value.forEach((relationshipNode) => {
    relationshipNode.endpoints.forEach((endpoint) => {
      const entityNode = nodeMap.value.get(entityKey(endpoint.entityId));
      if (!entityNode) {
        return;
      }

      const x1 = relationshipNode.x + relationshipNode.width / 2;
      const y1 = relationshipNode.y + relationshipNode.height / 2;
      const x2 = entityNode.x + entityNode.width / 2;
      const y2 = entityNode.y + entityNode.height / 2;

      calculatedEdges.push({
        id: `${relationshipNode.id}-${endpoint.entityId}`,
        x1,
        y1,
        x2,
        y2,
        label: endpoint.cardinality,
        lx: x1 + (x2 - x1) * 0.82,
        ly: y1 + (y2 - y1) * 0.82
      });
    });
  });

  return calculatedEdges;
});

const beginDrag = (event: PointerEvent, nodeKey: string): void => {
  if (!diagramRef.value || !positions[nodeKey]) {
    return;
  }

  event.preventDefault();
  const bounds = diagramRef.value.getBoundingClientRect();
  const currentPosition = positions[nodeKey];

  dragState = {
    key: nodeKey,
    pointerOffsetX: event.clientX - bounds.left - currentPosition.x,
    pointerOffsetY: event.clientY - bounds.top - currentPosition.y
  };

  window.addEventListener('pointermove', onDragMove);
  window.addEventListener('pointerup', endDrag);
};

const onDragMove = (event: PointerEvent): void => {
  if (!dragState || !diagramRef.value) {
    return;
  }

  const node = nodeMap.value.get(dragState.key);
  if (!node) {
    return;
  }

  const bounds = diagramRef.value.getBoundingClientRect();
  const maxX = Math.max(0, bounds.width - node.width);
  const maxY = Math.max(0, bounds.height - node.height);

  const nextX = event.clientX - bounds.left - dragState.pointerOffsetX;
  const nextY = event.clientY - bounds.top - dragState.pointerOffsetY;

  positions[dragState.key] = {
    x: Math.min(maxX, Math.max(0, nextX)),
    y: Math.min(maxY, Math.max(0, nextY))
  };
};

const endDrag = (): void => {
  dragState = null;
  window.removeEventListener('pointermove', onDragMove);
  window.removeEventListener('pointerup', endDrag);
};

onBeforeUnmount(() => {
  endDrag();
  endLinkDrag();
  resizeObserver?.disconnect();
  resizeObserver = null;
});

onMounted(() => {
  refreshDiagramSize();

  if (!diagramRef.value) {
    return;
  }

  resizeObserver = new ResizeObserver(() => {
    refreshDiagramSize();
  });

  resizeObserver.observe(diagramRef.value);
});
</script>

<template>
  <section class="design-grid">
    <article class="panel">
      <header class="panel-head">
        <div>
          <h2>Datenbank-Entwurf</h2>
          <p class="muted">ER-Diagramm auf Basis des aktuellen Relationenschemas, inklusive Rueckueberfuehrung.</p>
        </div>
        <div class="panel-actions">
          <button type="button" :disabled="isBusy" @click="buildErFromSchema">Aus Relationenschema erzeugen</button>
          <button type="button" :disabled="isBusy || generatedSchema.length === 0" @click="loadGeneratedSchema">
            Als DB laden
          </button>
        </div>
      </header>

      <div class="editor-grid">
        <section class="editor-card">
          <h3>Entities</h3>

          <label>
            Neue Entity
            <input v-model="newEntityName" type="text" :disabled="isBusy" placeholder="z. B. schueler" />
          </label>
          <div class="three-cols">
            <label>
              PK-Attribut
              <input v-model="newEntityPrimaryAttribute.name" type="text" :disabled="isBusy" />
            </label>
            <label>
              PK-Typ
              <input v-model="newEntityPrimaryAttribute.type" type="text" :disabled="isBusy" />
            </label>
            <div class="align-end">
              <button type="button" :disabled="isBusy" @click="addEntity">Entity anlegen</button>
            </div>
          </div>

          <label>
            Ausgewaehlte Entity
            <select v-model="selectedEntityId" :disabled="isBusy || erModel.entities.length === 0">
              <option v-for="entity in erModel.entities" :key="`edit-entity-${entity.id}`" :value="entity.id">
                {{ entity.id }}
              </option>
            </select>
          </label>

          <template v-if="selectedEntity">
            <label>
              Anzeigename
              <input v-model="selectedEntity.name" type="text" :disabled="isBusy" />
            </label>

            <div class="row-actions">
              <button type="button" :disabled="isBusy" @click="saveSelectedEntityLabel">Entity-Name speichern</button>
              <button type="button" class="danger" :disabled="isBusy" @click="removeSelectedEntity">Entity loeschen</button>
            </div>

            <h4>Attribute</h4>
            <div class="three-cols">
              <label>
                Name
                <input v-model="newEntityAttribute.name" type="text" :disabled="isBusy" />
              </label>
              <label>
                Typ
                <input v-model="newEntityAttribute.type" type="text" :disabled="isBusy" />
              </label>
              <label class="checkbox-row">
                <input v-model="newEntityAttribute.isPrimaryKey" type="checkbox" :disabled="isBusy" />
                Primarattribut
              </label>
            </div>
            <button type="button" :disabled="isBusy" @click="addAttributeToSelectedEntity">Attribut hinzufuegen</button>

            <ul class="edit-list">
              <li v-for="attribute in selectedEntity.attributes" :key="`attr-${selectedEntity.id}-${attribute.name}`">
                <span>
                  <span :class="{ underline: attribute.isPrimaryKey }">{{ attribute.name }}</span>
                  <small> : {{ attribute.type || 'TEXT' }}</small>
                </span>
                <div class="inline-actions">
                  <button type="button" :disabled="isBusy" @click="toggleEntityAttributePrimary(attribute.name)">
                    PK umschalten
                  </button>
                  <button
                    type="button"
                    class="danger"
                    :disabled="isBusy || selectedEntity.attributes.length <= 1"
                    @click="removeAttributeFromSelectedEntity(attribute.name)"
                  >
                    Entfernen
                  </button>
                </div>
              </li>
            </ul>
          </template>
        </section>

        <section class="editor-card">
          <h3>Beziehungen</h3>

          <label>
            Neue Beziehung
            <input v-model="relationshipDraft.name" type="text" :disabled="isBusy" placeholder="z. B. belegt" />
          </label>
          <div class="two-cols">
            <label>
              Endpunkt 1 (Entity)
              <select v-model="relationshipDraft.leftEntityId" :disabled="isBusy || erModel.entities.length === 0">
                <option v-for="entity in erModel.entities" :key="`rel-left-${entity.id}`" :value="entity.id">
                  {{ entity.id }}
                </option>
              </select>
            </label>
            <label>
              Endpunkt 1 Kardinalitaet
              <select v-model="relationshipDraft.leftCardinality" :disabled="isBusy">
                <option value="1">1</option>
                <option value="N">N</option>
              </select>
            </label>
          </div>
          <div class="two-cols">
            <label>
              Endpunkt 2 (Entity)
              <select v-model="relationshipDraft.rightEntityId" :disabled="isBusy || erModel.entities.length === 0">
                <option v-for="entity in erModel.entities" :key="`rel-right-${entity.id}`" :value="entity.id">
                  {{ entity.id }}
                </option>
              </select>
            </label>
            <label>
              Endpunkt 2 Kardinalitaet
              <select v-model="relationshipDraft.rightCardinality" :disabled="isBusy">
                <option value="1">1</option>
                <option value="N">N</option>
              </select>
            </label>
          </div>
          <button type="button" :disabled="isBusy" @click="addRelationship">Beziehung anlegen</button>

          <label>
            Ausgewaehlte Beziehung
            <select v-model="selectedRelationshipId" :disabled="isBusy || erModel.relationships.length === 0">
              <option
                v-for="relationship in erModel.relationships"
                :key="`edit-relationship-${relationship.id}`"
                :value="relationship.id"
              >
                {{ relationship.id }}
              </option>
            </select>
          </label>

          <template v-if="selectedRelationship">
            <label>
              Anzeigename
              <input v-model="selectedRelationship.name" type="text" :disabled="isBusy" />
            </label>
            <div class="row-actions">
              <button type="button" :disabled="isBusy" @click="saveSelectedRelationshipLabel">
                Beziehungsname speichern
              </button>
              <button type="button" class="danger" :disabled="isBusy" @click="removeSelectedRelationship">
                Beziehung loeschen
              </button>
            </div>

            <h4>Endpunkte</h4>
            <ul class="edit-list">
              <li v-for="(endpoint, index) in selectedRelationship.endpoints" :key="`endpoint-${selectedRelationship.id}-${index}`">
                <div class="two-cols grow">
                  <label>
                    Entity
                    <select
                      :value="endpoint.entityId"
                      :disabled="isBusy || erModel.entities.length === 0"
                      @change="updateSelectedRelationshipEndpointEntity(index, ($event.target as HTMLSelectElement).value)"
                    >
                      <option v-for="entity in erModel.entities" :key="`entity-choice-${entity.id}`" :value="entity.id">
                        {{ entity.id }}
                      </option>
                    </select>
                  </label>
                  <label>
                    Kardinalitaet
                    <select
                      :value="endpoint.cardinality"
                      :disabled="isBusy"
                      @change="
                        updateSelectedRelationshipEndpointCardinality(
                          index,
                          ($event.target as HTMLSelectElement).value as ERCardinality
                        )
                      "
                    >
                      <option value="1">1</option>
                      <option value="N">N</option>
                    </select>
                  </label>
                </div>
                <button
                  type="button"
                  class="danger"
                  :disabled="isBusy || selectedRelationship.endpoints.length <= 2"
                  @click="removeEndpointFromSelectedRelationship(index)"
                >
                  Entfernen
                </button>
              </li>
            </ul>
            <button type="button" :disabled="isBusy" @click="addEndpointToSelectedRelationship">Endpunkt hinzufuegen</button>

            <h4>Beziehungsattribute</h4>
            <div class="three-cols">
              <label>
                Name
                <input v-model="relationshipAttributeDraft.name" type="text" :disabled="isBusy" />
              </label>
              <label>
                Typ
                <input v-model="relationshipAttributeDraft.type" type="text" :disabled="isBusy" />
              </label>
              <label class="checkbox-row">
                <input v-model="relationshipAttributeDraft.isPrimaryKey" type="checkbox" :disabled="isBusy" />
                Primarattribut
              </label>
            </div>
            <button type="button" :disabled="isBusy" @click="addAttributeToSelectedRelationship">
              Beziehungsattribut hinzufuegen
            </button>

            <ul class="edit-list">
              <li
                v-for="attribute in selectedRelationship.attributes"
                :key="`rel-attr-${selectedRelationship.id}-${attribute.name}`"
              >
                <span>
                  <span :class="{ underline: attribute.isPrimaryKey }">{{ attribute.name }}</span>
                  <small> : {{ attribute.type || 'TEXT' }}</small>
                </span>
                <div class="inline-actions">
                  <button type="button" :disabled="isBusy" @click="toggleRelationshipAttributePrimary(attribute.name)">
                    PK umschalten
                  </button>
                  <button
                    type="button"
                    class="danger"
                    :disabled="isBusy"
                    @click="removeAttributeFromSelectedRelationship(attribute.name)"
                  >
                    Entfernen
                  </button>
                </div>
              </li>
            </ul>
          </template>
        </section>
      </div>

      <p class="diagram-hint">Beziehung direkt zeichnen: Griffpunkt einer Entity ziehen und auf einer zweiten Entity loslassen.</p>

      <div ref="diagramRef" class="diagram-shell">
        <svg
          class="diagram-lines"
          :viewBox="`0 0 ${diagramSize.width} ${diagramSize.height}`"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <line
            v-for="edge in edges"
            :key="edge.id"
            :x1="edge.x1"
            :y1="edge.y1"
            :x2="edge.x2"
            :y2="edge.y2"
            class="diagram-line"
          />
          <text v-for="edge in edges" :key="`${edge.id}-label`" :x="edge.lx" :y="edge.ly" class="diagram-label">
            {{ edge.label }}
          </text>
          <line
            v-if="activeLinkPreview"
            :x1="activeLinkPreview.x1"
            :y1="activeLinkPreview.y1"
            :x2="activeLinkPreview.x2"
            :y2="activeLinkPreview.y2"
            class="diagram-line diagram-line--preview"
          />
        </svg>

        <section
          v-for="node in entityNodes"
          :key="node.key"
          class="diagram-node entity-node"
          :data-entity-id="node.id"
          :style="{ left: `${node.x}px`, top: `${node.y}px`, width: `${node.width}px`, minHeight: `${node.height}px` }"
          @pointerdown="beginDrag($event, node.key)"
        >
          <h3>{{ node.label }}</h3>
          <ul>
            <li v-for="attribute in node.attributes" :key="`${node.id}-${attribute.name}`">
              <span :class="{ underline: attribute.isPrimaryKey }">{{ attribute.name }}</span>
              <small v-if="attribute.type">: {{ attribute.type }}</small>
            </li>
          </ul>
          <button
            type="button"
            class="connection-handle"
            :disabled="isBusy"
            title="Beziehung von dieser Entity ziehen"
            @pointerdown.stop="startLinkDrag($event, node.id)"
          />
        </section>

        <section
          v-for="node in relationshipNodes"
          :key="node.key"
          class="diagram-node relationship-node"
          :style="{ left: `${node.x}px`, top: `${node.y}px`, width: `${node.width}px`, minHeight: `${node.height}px` }"
          @pointerdown="beginDrag($event, node.key)"
        >
          <h3>{{ node.label }}</h3>
          <p class="compact">Teilnehmer: {{ node.endpoints.map((endpoint) => endpoint.entityId).join(', ') }}</p>
          <p class="compact" v-if="node.attributes.length > 0">
            Attribute: {{ node.attributes.map((attribute) => attribute.name).join(', ') }}
          </p>
        </section>
      </div>

      <div class="grid-two">
        <section>
          <h3>ER-Modell JSON</h3>
          <textarea
            v-model="erJson"
            class="code-input"
            rows="14"
            spellcheck="false"
            :disabled="isBusy"
          />
          <div class="row-actions">
            <button type="button" :disabled="isBusy" @click="applyErJson">JSON uebernehmen</button>
          </div>
        </section>

        <section>
          <h3>Relationenschema (aus ER)</h3>
          <div class="schema-list" v-if="generatedSchema.length > 0">
            <p v-for="table in generatedSchema" :key="`generated-${table.name}`" class="schema-line">
              <span class="schema-table">{{ table.name }}</span
              >(
              <span v-for="(column, index) in table.columns" :key="`${table.name}-${column.name}`">
                <span
                  class="schema-column"
                  :class="{
                    'schema-column--pk': column.isPrimaryKey,
                    'schema-column--fdpk': generatedInference[table.name]?.primaryAttributes.has(column.name)
                  }"
                >
                  {{ column.name }}
                </span>
                <span v-if="column.type" class="schema-type">: {{ column.type }}</span>
                <span v-if="index < table.columns.length - 1">, </span>
              </span>
              )
            </p>
          </div>
          <p v-else class="muted">Noch kein aus ER abgeleitetes Relationenschema vorhanden.</p>

          <details class="sql-preview">
            <summary>SQL-Vorschau des generierten Schemas</summary>
            <textarea :value="generatedSql" class="code-input" rows="12" readonly spellcheck="false" />
          </details>
        </section>
      </div>

      <h3>FD-Analyse und Primaerattribut-Erkennung</h3>
      <div class="fd-controls">
        <label>
          Tabelle
          <select v-model="selectedFdTable" :disabled="isBusy || schema.length === 0">
            <option v-for="table in schema" :key="`fd-${table.name}`" :value="table.name">{{ table.name }}</option>
          </select>
        </label>
        <label>
          Functional Dependencies (eine pro Zeile, Format: A,B -> C)
          <textarea
            v-model="currentFdInput"
            class="code-input"
            rows="6"
            spellcheck="false"
            :disabled="isBusy || !selectedFdTable"
            placeholder="id -> name\nstudent_id,course_id -> score"
          />
        </label>
      </div>

      <div v-if="selectedFdTable" class="fd-graph-wrap">
        <div class="fd-graph-toolbar">
          <p class="muted">
            Entwurfsmenge: <span class="fd-inline-code">{{ fdDraftLeftLabel }}</span> |
            Zielattribut:
          </p>
          <select v-model="fdDraftRightAttribute" :disabled="isBusy || selectedFdAttributes.length === 0">
            <option v-for="attribute in selectedFdAttributes" :key="`fd-target-${attribute}`" :value="attribute">
              {{ attribute }}
            </option>
          </select>
          <button type="button" :disabled="isBusy || !canEditFdGraph" @click="addFdFromDraft">FD aus Entwurf hinzufuegen</button>
          <button type="button" :disabled="isBusy || !canEditFdGraph" @click="selectDeterminantFromDraft">
            Determinante auswaehlen
          </button>
          <button type="button" :disabled="isBusy || !selectedFdDeterminant" @click="removeSelectedFdDeterminant">
            Determinante loeschen
          </button>
          <button type="button" :disabled="isBusy || !selectedFdDeterminant" @click="resetFdGraphMode">
            Entwurfsmodus
          </button>
        </div>

        <p class="fd-tip">
          Klick auf Attributknoten:
          <span v-if="selectedFdDeterminant">
            fuegt fuer die aktive Determinante Kanten hinzu/entfernt sie.
          </span>
          <span v-else> waehlt Attribute fuer die linke Entwurfsmenge aus.</span>
        </p>

        <div
          class="fd-graph-shell"
          :class="{ 'fd-graph-shell--disabled': !canEditFdGraph }"
          :style="{ height: `${fdGraphHeight}px` }"
        >
          <svg
            class="fd-graph-svg"
            :viewBox="`0 0 ${diagramSize.width} ${fdGraphHeight}`"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <defs>
              <marker id="fdArrowHead" markerWidth="8" markerHeight="8" refX="7" refY="3.5" orient="auto">
                <polygon points="0 0, 8 3.5, 0 7" fill="#3c647c" />
              </marker>
            </defs>

            <line
              v-for="edge in fdGraphEdges.compositionEdges"
              :key="edge.id"
              :x1="edge.x1"
              :y1="edge.y1"
              :x2="edge.x2"
              :y2="edge.y2"
              class="fd-edge fd-edge--composition"
            />
            <line
              v-for="edge in fdGraphEdges.dependencyEdges"
              :key="edge.id"
              :x1="edge.x1"
              :y1="edge.y1"
              :x2="edge.x2"
              :y2="edge.y2"
              class="fd-edge"
              :class="{ 'fd-edge--selected': edge.isSelected }"
              marker-end="url(#fdArrowHead)"
            />
          </svg>

          <button
            v-for="node in fdAttributeNodes"
            :key="`fd-attr-${node.name}`"
            type="button"
            class="fd-node fd-node--attribute"
            :class="{
              'fd-node--draft': isAttributeInDraftLeftSide(node.name),
              'fd-node--active-right': selectedFdDeterminant && isAttributeOnSelectedRightSide(node.name)
            }"
            :style="{ left: `${node.x}px`, top: `${node.y}px`, width: `${node.width}px`, height: `${node.height}px` }"
            :disabled="isBusy || !canEditFdGraph"
            @click="toggleDependencyForSelectedDeterminant(node.name)"
          >
            {{ node.name }}
          </button>

          <button
            v-for="node in fdDeterminantNodes"
            :key="`fd-det-${node.key}`"
            type="button"
            class="fd-node fd-node--determinant"
            :class="{ 'fd-node--selected': node.key === selectedFdDeterminantKey }"
            :style="{ left: `${node.x}px`, top: `${node.y}px`, width: `${node.width}px`, height: `${node.height}px` }"
            :disabled="isBusy || !canEditFdGraph"
            @click="selectFdDeterminant(node.key)"
          >
            {{ formatDeterminantLabel(node.left) }}
          </button>
        </div>

        <p v-if="selectedFdParsing.errors.length > 0" class="error">
          FD-Syntaxfehler: {{ selectedFdParsing.errors.join(' | ') }}
        </p>
      </div>

      <div v-if="selectedTableInference" class="fd-result">
        <p v-if="selectedTableInference.errors.length > 0" class="error">
          {{ selectedTableInference.errors.join(' | ') }}
        </p>
        <p v-if="selectedTableInference.candidateKeys.length > 0">
          Kandidatenschluessel: {{ selectedCandidateKeysText }}
        </p>
        <p v-else class="muted">Mit den aktuellen FDs wurden keine Kandidatenschluessel erkannt.</p>
      </div>

      <h3>Aktuelles Relationenschema (mit FD-Hinweisen)</h3>
      <div class="schema-list" v-if="schema.length > 0">
        <p v-for="table in schema" :key="`source-${table.name}`" class="schema-line">
          <span class="schema-table">{{ table.name }}</span
          >(
          <span v-for="(column, index) in table.columns" :key="`${table.name}-source-${column.name}`">
            <span
              class="schema-column"
              :class="{
                'schema-column--pk': column.isPrimaryKey,
                'schema-column--fdpk': sourceInference[table.name]?.primaryAttributes.has(column.name)
              }"
            >
              {{ column.name }}
            </span>
            <span v-if="column.type" class="schema-type">: {{ column.type }}</span>
            <span v-if="index < table.columns.length - 1">, </span>
          </span>
          )
        </p>
        <p class="schema-note">Durchgezogen = DB-PK, gestrichelt = aus FDs erkannter Primaerattribut-Kandidat.</p>
      </div>

      <p v-if="designInfo" class="info">{{ designInfo }}</p>
      <p v-if="designError" class="error">{{ designError }}</p>
    </article>
  </section>
</template>

<style scoped>
.design-grid {
  display: grid;
  gap: 1rem;
}

.panel {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 0.85rem;
  background: #ffffff;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 0.75rem;
}

.panel-actions {
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.editor-grid {
  margin-top: 0.85rem;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.85rem;
}

.editor-card {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: #fbfdff;
  padding: 0.7rem;
  display: grid;
  gap: 0.5rem;
}

.editor-card h3 {
  margin: 0;
}

.editor-card h4 {
  margin: 0.4rem 0 0;
  font-size: 0.9rem;
}

.editor-card label {
  display: grid;
  gap: 0.25rem;
  font-size: 0.84rem;
}

.editor-card input[type='text'],
.editor-card select {
  min-height: 2.15rem;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.3rem 0.45rem;
  font: inherit;
  background: #ffffff;
}

.two-cols,
.three-cols {
  display: grid;
  gap: 0.55rem;
}

.two-cols {
  grid-template-columns: 1fr 1fr;
}

.three-cols {
  grid-template-columns: 1fr 1fr 1fr;
}

.align-end {
  display: flex;
  align-items: end;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.edit-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.45rem;
}

.edit-list li {
  display: flex;
  justify-content: space-between;
  gap: 0.55rem;
  align-items: center;
  border: 1px solid #dfe6ed;
  border-radius: 8px;
  padding: 0.35rem 0.45rem;
  font-size: 0.84rem;
}

.inline-actions {
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.danger {
  background: #cc5a4f;
}

.danger:hover:enabled {
  background: #b24c42;
}

.grow {
  flex: 1;
}

.muted {
  color: #566879;
  font-size: 0.9rem;
}

.diagram-shell {
  margin-top: 0.8rem;
  position: relative;
  height: 520px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background:
    radial-gradient(circle at 15% 20%, #fbfff5 0, transparent 40%),
    radial-gradient(circle at 80% 25%, #f3fcff 0, transparent 34%),
    #f8fafb;
  overflow: hidden;
}

.diagram-hint {
  margin: 0.75rem 0 0;
  color: #4f6678;
  font-size: 0.84rem;
}

.diagram-lines {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.diagram-line {
  stroke: #95a7b8;
  stroke-width: 1.4;
}

.diagram-line--preview {
  stroke: #2a9d8f;
  stroke-width: 2.2;
  stroke-dasharray: 7 5;
}

.diagram-label {
  fill: #2b4f65;
  font-size: 12px;
  font-weight: 600;
}

.diagram-node {
  position: absolute;
  border-radius: 10px;
  padding: 0.55rem 0.6rem;
  cursor: grab;
  user-select: none;
  box-shadow: 0 4px 10px rgba(18, 46, 68, 0.08);
}

.diagram-node:active {
  cursor: grabbing;
}

.diagram-node h3 {
  margin: 0;
  font-size: 0.92rem;
}

.entity-node {
  border: 1px solid #7aa3bf;
  background: #ffffff;
}

.connection-handle {
  position: absolute;
  right: 8px;
  bottom: 8px;
  width: 16px;
  height: 16px;
  min-height: 0;
  border-radius: 999px;
  border: 1px solid #2a9d8f;
  background: #dff7f3;
  padding: 0;
  cursor: crosshair;
}

.connection-handle:hover:enabled {
  background: #c2eee7;
}

.entity-node ul {
  list-style: none;
  margin: 0.45rem 0 0;
  padding: 0;
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 0.82rem;
}

.entity-node li {
  margin-bottom: 0.15rem;
}

.relationship-node {
  border: 1px solid #6b8a66;
  background: #f9fff6;
  font-size: 0.82rem;
}

.compact {
  margin-top: 0.4rem;
  margin-bottom: 0;
}

.grid-two {
  margin-top: 0.9rem;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.85rem;
}

.code-input {
  width: 100%;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.45rem 0.55rem;
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 0.83rem;
  line-height: 1.35;
  resize: vertical;
  background: #ffffff;
}

.row-actions {
  margin-top: 0.5rem;
  display: flex;
  gap: 0.6rem;
}

.sql-preview {
  margin-top: 0.6rem;
}

.fd-controls {
  display: grid;
  gap: 0.65rem;
  margin-bottom: 0.75rem;
}

.fd-graph-wrap {
  margin-bottom: 0.85rem;
}

.fd-graph-toolbar {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 0.45rem;
}

.fd-graph-toolbar select {
  min-height: 2rem;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0.2rem 0.45rem;
  background: #ffffff;
}

.fd-inline-code {
  font-family: "IBM Plex Mono", Consolas, monospace;
}

.fd-tip {
  margin: 0.2rem 0 0.45rem;
  color: #536b7d;
  font-size: 0.84rem;
}

.fd-graph-shell {
  position: relative;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background:
    linear-gradient(180deg, rgba(248, 252, 255, 0.92) 0%, rgba(250, 255, 248, 0.92) 100%),
    #ffffff;
  overflow: hidden;
}

.fd-graph-shell--disabled {
  opacity: 0.7;
}

.fd-graph-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.fd-edge {
  stroke: #3c647c;
  stroke-width: 1.6;
}

.fd-edge--composition {
  stroke: #7d93a4;
  stroke-dasharray: 6 5;
}

.fd-edge--selected {
  stroke: #2a9d8f;
  stroke-width: 2.2;
}

.fd-node {
  position: absolute;
  min-height: 0;
  padding: 0.2rem 0.35rem;
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 0.8rem;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fd-node--attribute {
  border-color: #6c92ad;
  background: #ffffff;
  color: #1f3f56;
}

.fd-node--draft {
  border-color: #2a9d8f;
  background: #dcf5f1;
}

.fd-node--active-right {
  border-color: #1f7a70;
  background: #d5efe9;
}

.fd-node--determinant {
  border-color: #6c7c91;
  background: #f2f6fa;
  font-family: "IBM Plex Mono", Consolas, monospace;
}

.fd-node--selected {
  border-color: #2a9d8f;
  background: #dbf3ef;
}

.schema-list {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: #ffffff;
  padding: 0.7rem 0.85rem;
}

.schema-line {
  margin: 0.2rem 0;
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 0.86rem;
}

.schema-table {
  font-weight: 600;
}

.schema-column--pk,
.underline {
  text-decoration: underline;
  text-underline-offset: 0.16rem;
  text-decoration-thickness: 2px;
}

.schema-column--fdpk {
  text-decoration: underline dashed;
  text-underline-offset: 0.2rem;
}

.schema-type {
  color: #587288;
}

.schema-note {
  margin-top: 0.55rem;
  color: #4e6577;
  font-size: 0.84rem;
}

.info {
  color: #2a7f72;
}

.error {
  color: #b42318;
}

@media (max-width: 980px) {
  .panel-head {
    flex-direction: column;
    align-items: stretch;
  }

  .editor-grid {
    grid-template-columns: 1fr;
  }

  .grid-two {
    grid-template-columns: 1fr;
  }

  .diagram-shell {
    height: 420px;
  }

  .two-cols,
  .three-cols {
    grid-template-columns: 1fr;
  }
}
</style>
