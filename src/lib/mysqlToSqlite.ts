const stripLineComments = (sql: string): string => {
  return sql
    .split('\n')
    .filter((line) => !line.trimStart().startsWith('-- EOD'))
    .join('\n');
};

const replaceEnumType = (sql: string): string => {
  let output = '';
  let index = 0;

  while (index < sql.length) {
    const probe = sql.slice(index);
    const enumMatch = /^ENUM\s*\(/i.exec(probe);

    if (!enumMatch) {
      output += sql[index];
      index += 1;
      continue;
    }

    output += 'TEXT';
    index += enumMatch[0].length;

    let depth = 1;
    while (index < sql.length && depth > 0) {
      const char = sql[index];
      if (char === '(') {
        depth += 1;
      } else if (char === ')') {
        depth -= 1;
      }

      index += 1;
    }
  }

  return output;
};

export const mysqlToSqlite = (sql: string): string => {
  const withoutComments = stripLineComments(sql);
  const withEnumAsText = replaceEnumType(withoutComments);

  const normalized = withEnumAsText
    .replace(/\r\n/g, '\n')
    .replace(/SET\s+FOREIGN_KEY_CHECKS\s*=\s*[01]\s*;\s*/gi, '')
    .replace(/\bINSERT\s+IGNORE\s+INTO\b/gi, 'INSERT OR IGNORE INTO')
    .replace(/\b(?:INT|INTEGER)\s+PRIMARY\s+KEY\s+AUTO_INCREMENT\b/gi, 'INTEGER PRIMARY KEY')
    .replace(/\bAUTO_INCREMENT\b/gi, '')
    .replace(/\bBOOLEAN\b/gi, 'INTEGER')
    .replace(/^\s*INDEX\s+[^\n]+\n?/gim, '')
    .replace(/,\s*\)/g, '\n)')
    .replace(/\n{3,}/g, '\n\n');

  return normalized.trim();
};
