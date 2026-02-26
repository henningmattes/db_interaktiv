import os
import csv
import mysql.connector
from mysql.connector import Error
from getpass import getpass

# ==========================================
# KONFIGURATION
# ==========================================
# Hier die Verbindungsdaten zur Datenbank anpassen
DB_HOST = 'localhost'
DB_USER = 'root'
# DB_PASSWORD = 'dein_passwort' # Besser interaktiv abfragen oder hier hartkodieren
DB_NAME = 'db_DigitalesKlassenbuch'

# Ordner, in dem die CSV-Dateien liegen (relativ zu diesem Skript)
CSV_DIR = 'db_DigitalesKlassenbuch'

# Die Import-Reihenfolge ist extrem wichtig wegen der Foreign Key Constraints!
# Von Tabellen ohne Abhängigkeiten hin zu Tabellen mit vielen Abhängigkeiten.
TABELLEN_REIHENFOLGE = [
    'Schuljahr',
    'Raum',
    'Fach',
    'Lehrer',
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

# Mapping der Python-None-Werte zu SQL NULL
def convert_value(val):
    if val == '' or val is None:
        return None
    return val

def import_csv_data(connection, cursor):
    print(f"\nStarte Import von {len(TABELLEN_REIHENFOLGE)} Tabellen in die Datenbank '{DB_NAME}'...\n")
    
    # Optional: Foreign Key Checks fuer den Import kurz deaktivieren, 
    # falls es doch mal unvorhergesehene Inkonsistenzen (z.B. Zirkelbezuege) gaebe.
    # Da unsere CSVs konsistent in der richtigen Reihenfolge sind, ist es nicht zwingend, 
    # aber "Best Practice" fuer Massenimports.
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    
    erfolgreiche_imports = 0

    for table_name in TABELLEN_REIHENFOLGE:
        # Die Dateinamen im Skript sind lowercase mit Unterstrichen
        # Mapping z.B. Schuljahr -> schuljahr.csv, LehrerDeputation -> lehrer_deputation.csv
        file_name = ""
        for i, char in enumerate(table_name):
            if char.isupper() and i > 0:
                file_name += "_" + char.lower()
            else:
                file_name += char.lower()
        file_name += ".csv"
        
        file_path = os.path.join(CSV_DIR, file_name)
        
        if not os.path.exists(file_path):
            print(f"WARNUNG: Datei {file_name} nicht gefunden. Ueberspringe Tabelle {table_name}.")
            continue

        with open(file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file, delimiter=';', quotechar='"')
            headers = next(csv_reader) # Erste Zeile sind die Spaltennamen
            
            # Baue den INSERT Befehl dynamisch
            # z.B. INSERT INTO Lehrer (id, kuerzel, vorname) VALUES (%s, %s, %s)
            placeholders = ', '.join(['%s'] * len(headers))
            columns = ', '.join(headers)
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            
            data_to_insert = []
            for row in csv_reader:
                # Leere Strings ("") in den CSVs zu SQL NULL konvertieren
                processed_row = tuple(convert_value(col) for col in row)
                data_to_insert.append(processed_row)
            
            if not data_to_insert:
                print(f"INFO: Tabelle {table_name} - CSV Datei ist leer.")
                continue

            try:
                # Massen-Insert für die gesamte Tabelle (sehr schnell)
                cursor.executemany(sql, data_to_insert)
                connection.commit()
                print(f"ERFOLG: {len(data_to_insert)} Zeilen in '{table_name}' importiert.")
                erfolgreiche_imports += 1
            except Error as e:
                connection.rollback()
                print(f"FEHLER beim Importieren von '{table_name}': {e}")
                
    # Constraints wieder aktivieren
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    print(f"\nImport abgeschlossen. {erfolgreiche_imports} von {len(TABELLEN_REIHENFOLGE)} Tabellen befuellt.")

def main():
    print("=== MySQL CSV Import-Tool fuer das Digitale Klassenbuch ===")
    
    db_pass = input(f"Passwort fuer MySQL-User '{DB_USER}': ")

    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=db_pass,
            database=DB_NAME
        )
        
        if connection.is_connected():
            db_info = connection.get_server_info()
            print(f"Verbindung zu MySQL Server (Version {db_info}) erfolgreich aufgebaut.")
            
            cursor = connection.cursor()
            
            # Wir trauen uns nicht, die Tabellen pauschal zu loeschen (TRUNCATE),
            # da dies destruktiv ist. Der Import geht davon aus, dass die Tabellen
            # leer oder frisch erzeugt (01_schema.sql) sind.
            
            import_csv_data(connection, cursor)

    except Error as e:
        print(f"\nKRITISCHER FEHLER beim Verbinden zur Datenbank: {e}")
        print("Hinweis: Stelle sicher, dass der MySQL/MariaDB Server laeuft,")
        print("         die Datenbank 'db_DigitalesKlassenbuch' angelegt ist (via 01_schema.sql),")
        print("         und das Paket 'mysql-connector-python' installiert ist (pip install mysql-connector-python).")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL-Verbindung wurde geschlossen.")

if __name__ == '__main__':
    main()
