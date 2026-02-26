import type { DatabaseSchema, SchemaForeignKey, SchemaTable } from '../types/sqlWorker';

export type ERAttribute = {
  name: string;
  type: string;
  isPrimaryKey: boolean;
};

export type EREntity = {
  id: string;
  name: string;
  attributes: ERAttribute[];
};

export type ERCardinality = '1' | 'N';

export type ERRelationshipEndpoint = {
  entityId: string;
  cardinality: ERCardinality;
};

export type ERRelationship = {
  id: string;
  name: string;
  endpoints: ERRelationshipEndpoint[];
  attributes: ERAttribute[];
};

export type ERModel = {
  entities: EREntity[];
  relationships: ERRelationship[];
};

export type FunctionalDependency = {
  left: string[];
  right: string[];
};

export type ParsedDependencySet = {
  dependencies: FunctionalDependency[];
  errors: string[];
};

const normalizeName = (value: string): string => {
  const normalized = value.trim().toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
  return normalized.length > 0 ? normalized : 'item';
};

const quoteIdentifier = (value: string): string => {
  return `"${value.replace(/"/g, '""')}"`;
};

const ensureUnique = (preferred: string, used: Set<string>): string => {
  let next = preferred;
  let index = 2;

  while (used.has(next)) {
    next = `${preferred}_${index}`;
    index += 1;
  }

  used.add(next);
  return next;
};

const uniqueValues = (values: string[]): string[] => {
  return [...new Set(values.map((value) => value.trim()).filter((value) => value.length > 0))];
};

const getPrimaryAttributes = (entity: EREntity): ERAttribute[] => {
  const primaryAttributes = entity.attributes.filter((attribute) => attribute.isPrimaryKey);
  if (primaryAttributes.length > 0) {
    return primaryAttributes;
  }

  if (entity.attributes.length > 0) {
    return [entity.attributes[0]];
  }

  return [
    {
      name: 'id',
      type: 'INTEGER',
      isPrimaryKey: true
    }
  ];
};

const isAssociativeTable = (table: SchemaTable): boolean => {
  if (table.foreignKeys.length < 2) {
    return false;
  }

  const primaryKeyColumns = table.columns.filter((column) => column.isPrimaryKey).map((column) => column.name);
  if (primaryKeyColumns.length === 0) {
    return false;
  }

  const foreignKeyColumns = new Set(table.foreignKeys.map((foreignKey) => foreignKey.columnName));
  return primaryKeyColumns.every((columnName) => foreignKeyColumns.has(columnName));
};

const buildForeignKeyColumnName = (entityId: string, attributeName: string, used: Set<string>): string => {
  return ensureUnique(`${normalizeName(entityId)}_${normalizeName(attributeName)}`, used);
};

const addForeignKeyColumns = (
  targetTable: SchemaTable,
  sourceEntity: EREntity,
  usedColumnNames: Set<string>
): SchemaForeignKey[] => {
  const createdForeignKeys: SchemaForeignKey[] = [];

  for (const attribute of getPrimaryAttributes(sourceEntity)) {
    const columnName = buildForeignKeyColumnName(sourceEntity.id, attribute.name, usedColumnNames);

    targetTable.columns.push({
      name: columnName,
      type: attribute.type || 'INTEGER',
      isPrimaryKey: false
    });

    createdForeignKeys.push({
      columnName,
      referencedTable: sourceEntity.id,
      referencedColumn: attribute.name
    });
  }

  return createdForeignKeys;
};

const closure = (attributes: Set<string>, dependencies: FunctionalDependency[]): Set<string> => {
  const result = new Set(attributes);
  let changed = true;

  while (changed) {
    changed = false;

    for (const dependency of dependencies) {
      const coversLeft = dependency.left.every((attribute) => result.has(attribute));
      if (!coversLeft) {
        continue;
      }

      for (const attribute of dependency.right) {
        if (!result.has(attribute)) {
          result.add(attribute);
          changed = true;
        }
      }
    }
  }

  return result;
};

const combinations = <T>(values: T[], pickCount: number): T[][] => {
  if (pickCount === 0) {
    return [[]];
  }

  if (pickCount > values.length) {
    return [];
  }

  if (pickCount === 1) {
    return values.map((value) => [value]);
  }

  const result: T[][] = [];

  for (let index = 0; index <= values.length - pickCount; index += 1) {
    const head = values[index];
    const tails = combinations(values.slice(index + 1), pickCount - 1);

    for (const tail of tails) {
      result.push([head, ...tail]);
    }
  }

  return result;
};

export const relationalToErModel = (schema: DatabaseSchema): ERModel => {
  const associativeTables = new Set(schema.filter((table) => isAssociativeTable(table)).map((table) => table.name));

  const entities: EREntity[] = schema
    .filter((table) => !associativeTables.has(table.name))
    .map((table) => ({
      id: table.name,
      name: table.name,
      attributes: table.columns.map((column) => ({
        name: column.name,
        type: column.type,
        isPrimaryKey: column.isPrimaryKey
      }))
    }));

  const entityIds = new Set(entities.map((entity) => entity.id));
  const relationships: ERRelationship[] = [];

  for (const table of schema) {
    if (associativeTables.has(table.name)) {
      const byReferencedTable = new Map<string, SchemaForeignKey>();
      for (const foreignKey of table.foreignKeys) {
        if (!byReferencedTable.has(foreignKey.referencedTable)) {
          byReferencedTable.set(foreignKey.referencedTable, foreignKey);
        }
      }

      const endpoints = [...byReferencedTable.values()]
        .map((foreignKey) => foreignKey.referencedTable)
        .filter((entityId) => entityIds.has(entityId))
        .map((entityId) => ({
          entityId,
          cardinality: 'N' as ERCardinality
        }));

      if (endpoints.length >= 2) {
        const foreignKeyColumns = new Set(table.foreignKeys.map((foreignKey) => foreignKey.columnName));

        relationships.push({
          id: table.name,
          name: table.name,
          endpoints,
          attributes: table.columns
            .filter((column) => !foreignKeyColumns.has(column.name))
            .map((column) => ({
              name: column.name,
              type: column.type,
              isPrimaryKey: column.isPrimaryKey
            }))
        });
      }

      continue;
    }

    const groupedReferences = new Map<string, SchemaForeignKey[]>();
    for (const foreignKey of table.foreignKeys) {
      const current = groupedReferences.get(foreignKey.referencedTable) ?? [];
      current.push(foreignKey);
      groupedReferences.set(foreignKey.referencedTable, current);
    }

    for (const referencedTable of groupedReferences.keys()) {
      if (!entityIds.has(table.name) || !entityIds.has(referencedTable)) {
        continue;
      }

      relationships.push({
        id: `${table.name}_to_${referencedTable}`,
        name: `${table.name}_${referencedTable}`,
        endpoints: [
          {
            entityId: table.name,
            cardinality: 'N'
          },
          {
            entityId: referencedTable,
            cardinality: '1'
          }
        ],
        attributes: []
      });
    }
  }

  return {
    entities,
    relationships
  };
};

export const erModelToRelational = (model: ERModel): DatabaseSchema => {
  const tables = new Map<string, SchemaTable>();

  for (const entity of model.entities) {
    tables.set(entity.id, {
      name: entity.id,
      columns: entity.attributes.map((attribute) => ({
        name: attribute.name,
        type: attribute.type || 'TEXT',
        isPrimaryKey: attribute.isPrimaryKey
      })),
      foreignKeys: []
    });
  }

  const usedTableNames = new Set(tables.keys());

  for (const relationship of model.relationships) {
    const endpoints = relationship.endpoints
      .map((endpoint) => ({
        endpoint,
        entity: model.entities.find((entity) => entity.id === endpoint.entityId)
      }))
      .filter((entry): entry is { endpoint: ERRelationshipEndpoint; entity: EREntity } => entry.entity != null);

    if (endpoints.length < 2) {
      continue;
    }

    const oneEndpoint = endpoints.find((entry) => entry.endpoint.cardinality === '1');
    const manyEndpoint = endpoints.find((entry) => entry.endpoint.cardinality === 'N');

    if (endpoints.length === 2 && relationship.attributes.length === 0 && oneEndpoint && manyEndpoint) {
      const manyTable = tables.get(manyEndpoint.entity.id);
      if (!manyTable) {
        continue;
      }

      const usedColumnNames = new Set(manyTable.columns.map((column) => column.name));
      const foreignKeys = addForeignKeyColumns(manyTable, oneEndpoint.entity, usedColumnNames);
      manyTable.foreignKeys.push(...foreignKeys);
      continue;
    }

    const relationName = ensureUnique(normalizeName(relationship.name || relationship.id), usedTableNames);
    const relationTable: SchemaTable = {
      name: relationName,
      columns: [],
      foreignKeys: []
    };

    const usedColumnNames = new Set<string>();

    for (const entry of endpoints) {
      const primaryAttributes = getPrimaryAttributes(entry.entity);

      for (const attribute of primaryAttributes) {
        const columnName = buildForeignKeyColumnName(entry.entity.id, attribute.name, usedColumnNames);
        relationTable.columns.push({
          name: columnName,
          type: attribute.type || 'INTEGER',
          isPrimaryKey: true
        });
        relationTable.foreignKeys.push({
          columnName,
          referencedTable: entry.entity.id,
          referencedColumn: attribute.name
        });
      }
    }

    for (const attribute of relationship.attributes) {
      const columnName = ensureUnique(normalizeName(attribute.name), usedColumnNames);
      relationTable.columns.push({
        name: columnName,
        type: attribute.type || 'TEXT',
        isPrimaryKey: false
      });
    }

    tables.set(relationTable.name, relationTable);
  }

  return [...tables.values()];
};

export const relationalSchemaToSql = (schema: DatabaseSchema): string => {
  const dropStatements = schema
    .slice()
    .reverse()
    .map((table) => `DROP TABLE IF EXISTS ${quoteIdentifier(table.name)};`)
    .join('\n');

  const createStatements = schema
    .map((table) => {
      const columnStatements = table.columns.map((column) => {
        const fallbackType = column.type.trim().length > 0 ? column.type : 'TEXT';
        return `  ${quoteIdentifier(column.name)} ${fallbackType}`;
      });

      const primaryColumns = table.columns.filter((column) => column.isPrimaryKey).map((column) => column.name);
      if (primaryColumns.length > 0) {
        columnStatements.push(`  PRIMARY KEY (${primaryColumns.map(quoteIdentifier).join(', ')})`);
      }

      for (const foreignKey of table.foreignKeys) {
        columnStatements.push(
          `  FOREIGN KEY (${quoteIdentifier(foreignKey.columnName)}) REFERENCES ${quoteIdentifier(
            foreignKey.referencedTable
          )} (${quoteIdentifier(foreignKey.referencedColumn)})`
        );
      }

      return `CREATE TABLE ${quoteIdentifier(table.name)} (\n${columnStatements.join(',\n')}\n);`;
    })
    .join('\n\n');

  return `${dropStatements}\n\n${createStatements}\n`;
};

export const parseFunctionalDependencies = (text: string): ParsedDependencySet => {
  const dependencies: FunctionalDependency[] = [];
  const errors: string[] = [];

  const lines = text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith('#'));

  lines.forEach((line, index) => {
    const arrowIndex = line.indexOf('->');
    if (arrowIndex < 1) {
      errors.push(`Zeile ${index + 1}: Erwartet Format A,B -> C,D`);
      return;
    }

    const leftPart = line.slice(0, arrowIndex);
    const rightPart = line.slice(arrowIndex + 2);

    const left = uniqueValues(leftPart.split(','));
    const right = uniqueValues(rightPart.split(','));

    if (left.length === 0 || right.length === 0) {
      errors.push(`Zeile ${index + 1}: Linke und rechte Seite duerfen nicht leer sein.`);
      return;
    }

    dependencies.push({ left, right });
  });

  return {
    dependencies,
    errors
  };
};

export const findCandidateKeys = (attributes: string[], dependencies: FunctionalDependency[]): string[][] => {
  const normalizedAttributes = uniqueValues(attributes);

  if (normalizedAttributes.length === 0) {
    return [];
  }

  const allAttributes = new Set(normalizedAttributes);

  const normalizedDependencies = dependencies
    .map((dependency) => ({
      left: uniqueValues(dependency.left).filter((attribute) => allAttributes.has(attribute)),
      right: uniqueValues(dependency.right).filter((attribute) => allAttributes.has(attribute))
    }))
    .filter((dependency) => dependency.left.length > 0 && dependency.right.length > 0);

  const rightAttributes = new Set(normalizedDependencies.flatMap((dependency) => dependency.right));
  const mandatoryAttributes = normalizedAttributes.filter((attribute) => !rightAttributes.has(attribute));
  const optionalAttributes = normalizedAttributes.filter((attribute) => !mandatoryAttributes.includes(attribute));

  if (optionalAttributes.length > 12) {
    return [];
  }

  const candidateKeys: string[][] = [];

  for (let pickCount = 0; pickCount <= optionalAttributes.length; pickCount += 1) {
    const optionalCombinations = combinations(optionalAttributes, pickCount);

    for (const optionalCombination of optionalCombinations) {
      const nextKey = uniqueValues([...mandatoryAttributes, ...optionalCombination]);
      const nextKeySet = new Set(nextKey);
      const nextClosure = closure(nextKeySet, normalizedDependencies);

      const isSuperKey = normalizedAttributes.every((attribute) => nextClosure.has(attribute));
      if (!isSuperKey) {
        continue;
      }

      const isMinimal = !candidateKeys.some((candidateKey) => {
        return candidateKey.every((attribute) => nextKeySet.has(attribute));
      });

      if (isMinimal) {
        candidateKeys.push(nextKey);
      }
    }

    if (candidateKeys.length > 0) {
      break;
    }
  }

  return candidateKeys;
};

export const inferPrimaryAttributes = (
  attributes: string[],
  dependencies: FunctionalDependency[]
): {
  primaryAttributes: string[];
  candidateKeys: string[][];
} => {
  const candidateKeys = findCandidateKeys(attributes, dependencies);
  if (candidateKeys.length === 0) {
    return {
      candidateKeys: [],
      primaryAttributes: []
    };
  }

  const smallestSize = Math.min(...candidateKeys.map((candidateKey) => candidateKey.length));
  const smallestKeys = candidateKeys.filter((candidateKey) => candidateKey.length === smallestSize);
  const primaryAttributeSet = new Set(smallestKeys.flat());

  return {
    candidateKeys,
    primaryAttributes: [...primaryAttributeSet]
  };
};
