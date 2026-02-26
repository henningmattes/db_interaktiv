import os
import csv

# ==========================================
# KONFIGURATION
# ==========================================
CSV_DIR = 'db_DigitalesKlassenbuch'
OUTPUT_FILE = '02_beispieldaten.sql'

# Exakte, abhaengigkeitsgerechte Reihenfolge
TABELLEN_REIHENFOLGE = [
    'Schuljahr',
    'Raum',
    'Wochentag',
    'Fach',
    'Lehrer',
    'Lehrbefaehigung',
    'Schueler',
    'Abschnitt',
    'Klasse',
    'SchuelerStatus',
    'LehrerDeputation',
    'Kurs',
    'Kursbelegung',
    'Stundenplan',
    'Unterrichtsstunde',
    'Anwesenheit'
]

def format_sql_value(value):
    """Konvertiert CSV-Strings in gueltiges SQL"""
    if value == '' or value is None:
        return 'NULL'
    
    # Pruefen auf Zahlen (sehr simpel)
    if value.replace('.', '', 1).isdigit() and value.count('.') <= 1:
        return value
        
    if value.lower() in ('true', 'false'):
        return value.upper()
        
    # Strings escapen (z.B. O'Connor -> O''Connor)
    escaped_value = value.replace("'", "''")
    return f"'{escaped_value}'"

def main():
    print(f"Generiere SQL-Skript: {OUTPUT_FILE} aus den CSVs im Ordner '{CSV_DIR}'...\n")
    
    out_path = os.path.join(CSV_DIR, OUTPUT_FILE)
    
    with open(out_path, 'w', encoding='utf-8') as f_out:
        f_out.write("-- ==========================================\n")
        f_out.write("-- AUTO-GENERATED SQL INSERT SCRIPT\n")
        f_out.write("-- Beispieldaten fuer Digitales Klassenbuch\n")
        f_out.write("-- ==========================================\n\n")
        
        # Foreign Keys fuer den Import temporaer ausschalten (als doppeltes Sicherheitsnetz)
        f_out.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")
        
        total_inserts = 0

        for table_name in TABELLEN_REIHENFOLGE:
            file_name = ""
            for i, char in enumerate(table_name):
                if char.isupper() and i > 0:
                    file_name += "_" + char.lower()
                else:
                    file_name += char.lower()
            file_name += ".csv"
            
            file_path = os.path.join(CSV_DIR, file_name)
            
            if not os.path.exists(file_path):
                print(f"WARNUNG: {file_name} uebersprungen (nicht gefunden).")
                continue

            with open(file_path, 'r', encoding='utf-8') as csv_file:
                csv_reader = csv.reader(csv_file, delimiter=';', quotechar='"')
                headers = next(csv_reader)
                columns = ', '.join(headers)
                
                CHUNK_SIZE = 1000
                current_chunk = []
                table_inserts = 0
                
                f_out.write(f"-- ------------------------------------------\n")
                f_out.write(f"-- Daten fuer Tabelle `{table_name}`\n")
                f_out.write(f"-- ------------------------------------------\n")

                for row in csv_reader:
                    values = [format_sql_value(v) for v in row]
                    current_chunk.append("(" + ", ".join(values) + ")")
                    table_inserts += 1
                    total_inserts += 1
                    
                    if len(current_chunk) >= CHUNK_SIZE:
                        sql = f"INSERT IGNORE INTO {table_name} ({columns}) VALUES\n"
                        sql += ",\n".join(current_chunk) + ";\n\n"
                        f_out.write(sql)
                        current_chunk = []
                
                # Restliche Rows schreiben
                if current_chunk:
                    sql = f"INSERT IGNORE INTO {table_name} ({columns}) VALUES\n"
                    sql += ",\n".join(current_chunk) + ";\n\n"
                    f_out.write(sql)

                print(f"-> {table_inserts} gepackte INSERTS generiert für '{table_name}'.")

        # Checks wieder einschalten
        f_out.write("\nSET FOREIGN_KEY_CHECKS = 1;\n")
        f_out.write("-- EOD\n")
        
    print(f"\nERFOLG! {total_inserts} Datensaetze komplett in SQL komprimiert.")
    print(f"Die Datei liegt nun bereit unter: {out_path}")

if __name__ == '__main__':
    main()
