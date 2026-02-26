-- 1. Lehrer
CREATE TABLE Lehrer (
    id INT PRIMARY KEY AUTO_INCREMENT,
    kuerzel VARCHAR(10) NOT NULL UNIQUE,
    vorname VARCHAR(100) NOT NULL,
    nachname VARCHAR(100) NOT NULL,
    geburtsdatum DATE NULL,
    aktiv BOOLEAN NOT NULL DEFAULT TRUE
);

-- 2. Schuljahr
CREATE TABLE Schuljahr (
    id INT PRIMARY KEY AUTO_INCREMENT,
    bezeichnung VARCHAR(9) NOT NULL UNIQUE,   -- z.B. '2026/27'
    startdatum DATE NOT NULL,
    enddatum DATE NOT NULL,
    aktiv BOOLEAN NOT NULL DEFAULT FALSE
);

-- 3. Abschnitt (Halbjahr / Laufbahnabschnitt)
CREATE TABLE Abschnitt (
    id INT PRIMARY KEY AUTO_INCREMENT,
    schuljahr_id INT NOT NULL,
    code VARCHAR(10) NOT NULL,   -- z.B. '1', '2', 'EF.1', 'Q1.2'
    startdatum DATE NULL,
    enddatum DATE NULL,
    FOREIGN KEY (schuljahr_id) REFERENCES Schuljahr(id) ON DELETE CASCADE,
    UNIQUE (schuljahr_id, code)
);

-- 4. Klasse (Sek I Stammgruppen)
CREATE TABLE Klasse (
    id INT PRIMARY KEY AUTO_INCREMENT,
    schuljahr_id INT NOT NULL,
    jahrgangsstufe ENUM('5', '6', '7', '8', '9', '10') NOT NULL,
    bezeichnung CHAR(1) NOT NULL, -- 'a', 'b', 'c', 'd'
    klassenlehrer_id INT NULL,
    FOREIGN KEY (schuljahr_id) REFERENCES Schuljahr(id) ON DELETE CASCADE,
    FOREIGN KEY (klassenlehrer_id) REFERENCES Lehrer(id) ON DELETE SET NULL,
    UNIQUE (schuljahr_id, jahrgangsstufe, bezeichnung)
);

-- 5. Schueler
CREATE TABLE Schueler (
    id INT PRIMARY KEY AUTO_INCREMENT,
    vorname VARCHAR(100) NOT NULL,
    nachname VARCHAR(100) NOT NULL,
    geburtsdatum DATE NULL,
    aktiv BOOLEAN NOT NULL DEFAULT TRUE
);

-- 6. SchuelerStatus pro Schuljahr
CREATE TABLE SchuelerStatus (
    id INT PRIMARY KEY AUTO_INCREMENT,
    schueler_id INT NOT NULL,
    schuljahr_id INT NOT NULL,
    jahrgangsstufe ENUM('5', '6', '7', '8', '9', '10', 'EF', 'Q1', 'Q2') NOT NULL,
    klasse_id INT NULL, -- nur Sek I, in Sek II normalerweise NULL
    status_laufbahn ENUM('normal', 'wiederholt', 'uebersprungen', 'zugang', 'abgang') DEFAULT 'normal',
    FOREIGN KEY (schueler_id) REFERENCES Schueler(id) ON DELETE CASCADE,
    FOREIGN KEY (schuljahr_id) REFERENCES Schuljahr(id) ON DELETE CASCADE,
    FOREIGN KEY (klasse_id) REFERENCES Klasse(id) ON DELETE SET NULL,
    UNIQUE (schueler_id, schuljahr_id)
);

-- 7. Fach
CREATE TABLE Fach (
    id INT PRIMARY KEY AUTO_INCREMENT,
    kuerzel VARCHAR(15) NOT NULL UNIQUE,  -- z.B. D, M, E, IF, RE, PP, WPIF
    name VARCHAR(100) NOT NULL,
    aufgabenfeld ENUM('I', 'II', 'III', 'ohne') NULL
);

-- 7.X Lehrbefaehigung (welcher Lehrer darf welches Fach unterrichten)
CREATE TABLE Lehrbefaehigung (
    lehrer_id INT NOT NULL,
    fach_id INT NOT NULL,
    PRIMARY KEY (lehrer_id, fach_id),
    FOREIGN KEY (lehrer_id) REFERENCES Lehrer(id) ON DELETE CASCADE,
    FOREIGN KEY (fach_id) REFERENCES Fach(id) ON DELETE CASCADE
);

-- 8. Kurs (alle Unterrichtsgruppen, Sek I + Sek II)
CREATE TABLE Kurs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    schuljahr_id INT NOT NULL,
    abschnitt_id INT NULL,
    bezeichnung VARCHAR(50) NOT NULL,    -- z.B. '9-WP-IF-1', 'Q1-D-LK1'
    fach_id INT NOT NULL,
    lehrer_id INT NOT NULL,
    jahrgangsstufe ENUM('5', '6', '7', '8', '9', '10', 'EF', 'Q1', 'Q2') NOT NULL,
    klasse_id INT NULL,
    kursart ENUM(
        'Klassenunterricht',
        'Wahlpflicht',
        'Differenzierung',
        'Religion/Ethik',
        'Foerderkurs',
        'AG',
        'GK',
        'LK',
        'Zusatzkurs',
        'Vertiefungskurs',
        'Projektkurs'
    ) NOT NULL,
    wochenstunden DECIMAL(4,2) NULL,
    parallelgruppe INT NULL,
    FOREIGN KEY (schuljahr_id) REFERENCES Schuljahr(id) ON DELETE CASCADE,
    FOREIGN KEY (abschnitt_id) REFERENCES Abschnitt(id) ON DELETE SET NULL,
    FOREIGN KEY (fach_id) REFERENCES Fach(id),
    FOREIGN KEY (lehrer_id) REFERENCES Lehrer(id),
    FOREIGN KEY (klasse_id) REFERENCES Klasse(id),
    UNIQUE (schuljahr_id, bezeichnung),
    UNIQUE (id, schuljahr_id)
);

-- 9. Kursbelegung (Schueler <-> Kurs)
CREATE TABLE Kursbelegung (
    schueler_id INT NOT NULL,
    kurs_id INT NOT NULL,
    PRIMARY KEY (schueler_id, kurs_id),
    FOREIGN KEY (schueler_id) REFERENCES Schueler(id) ON DELETE CASCADE,
    FOREIGN KEY (kurs_id) REFERENCES Kurs(id) ON DELETE CASCADE
);

-- 10. Raum
CREATE TABLE Raum (
    id INT PRIMARY KEY AUTO_INCREMENT,
    bezeichnung VARCHAR(50) NOT NULL UNIQUE  -- z.B. B201, PH1, SpH1
);

-- 11. Wochentag
CREATE TABLE Wochentag (
    id INT PRIMARY KEY,
    name VARCHAR(20) NOT NULL UNIQUE
);

-- 12. Stundenplan (Wochenraster)
CREATE TABLE Stundenplan (
    id INT PRIMARY KEY AUTO_INCREMENT,
    kurs_id INT NOT NULL,
    schuljahr_id INT NOT NULL,
    raum_id INT NULL,
    wochentag_id INT NOT NULL,
    stunde INT NOT NULL,
    gueltig_ab DATE NOT NULL,
    gueltig_bis DATE NULL,

    FOREIGN KEY (schuljahr_id) REFERENCES Schuljahr(id) ON DELETE CASCADE,
    FOREIGN KEY (raum_id) REFERENCES Raum(id) ON DELETE SET NULL,
    FOREIGN KEY (wochentag_id) REFERENCES Wochentag(id) ON DELETE RESTRICT,

    FOREIGN KEY (kurs_id, schuljahr_id)
        REFERENCES Kurs(id, schuljahr_id)
        ON DELETE CASCADE,

    CHECK (stunde BETWEEN 1 AND 9),
    CHECK (gueltig_bis IS NULL OR gueltig_bis >= gueltig_ab),

    UNIQUE (kurs_id, wochentag_id, stunde, gueltig_ab),

    INDEX idx_stundenplan_slot (schuljahr_id, wochentag_id, stunde),
    INDEX idx_stundenplan_raum_slot (schuljahr_id, raum_id, wochentag_id, stunde),
    INDEX idx_stundenplan_gueltigkeit (gueltig_ab, gueltig_bis)
);

-- 13. Unterrichtsstunde (konkretes Ereignis im Klassenbuch)
CREATE TABLE Unterrichtsstunde (
    id INT PRIMARY KEY AUTO_INCREMENT,
    stundenplan_id INT NOT NULL,
    datum DATE NOT NULL,
    status ENUM('geplant', 'gehalten', 'entfallen', 'vertretung', 'verlegt') NOT NULL DEFAULT 'gehalten',
    thema VARCHAR(500) NULL,
    hausaufgaben TEXT NULL,

    vertretungslehrer_id INT NULL,
    tatsaechlicher_raum_id INT NULL,
    tatsaechliche_stunde INT NULL,

    ist_klausur BOOLEAN NOT NULL DEFAULT FALSE,
    notiz TEXT NULL,

    FOREIGN KEY (stundenplan_id) REFERENCES Stundenplan(id) ON DELETE CASCADE,
    FOREIGN KEY (vertretungslehrer_id) REFERENCES Lehrer(id) ON DELETE SET NULL,
    FOREIGN KEY (tatsaechlicher_raum_id) REFERENCES Raum(id) ON DELETE SET NULL,

    CHECK (tatsaechliche_stunde IS NULL OR tatsaechliche_stunde BETWEEN 1 AND 9),

    UNIQUE (stundenplan_id, datum),

    INDEX idx_unterrichtsstunde_datum (datum)
);

-- 14. Anwesenheit
CREATE TABLE Anwesenheit (
    id INT PRIMARY KEY AUTO_INCREMENT,
    unterrichtsstunde_id INT NOT NULL,
    schueler_id INT NOT NULL,
    status ENUM(
        'anwesend',
        'fehlend_unentschuldigt',
        'fehlend_entschuldigt',
        'verspaetet',
        'beurlaubt'
    ) NOT NULL DEFAULT 'anwesend',
    verspaetung_minuten INT NOT NULL DEFAULT 0,
    entschuldigungsstatus ENUM('offen', 'eingereicht', 'anerkannt', 'abgelehnt') NULL,
    anmerkung TEXT NULL,
    FOREIGN KEY (unterrichtsstunde_id) REFERENCES Unterrichtsstunde(id) ON DELETE CASCADE,
    FOREIGN KEY (schueler_id) REFERENCES Schueler(id) ON DELETE CASCADE,
    UNIQUE (unterrichtsstunde_id, schueler_id),
    CHECK (verspaetung_minuten >= 0)
);

-- 15. LehrerDeputation (schuljahresbezogen)
CREATE TABLE LehrerDeputation (
    id INT PRIMARY KEY AUTO_INCREMENT,
    lehrer_id INT NOT NULL,
    schuljahr_id INT NOT NULL,
    deputat_soll DECIMAL(5,2) NOT NULL,                  -- z.B. 25.50
    anrechnungsstunden DECIMAL(5,2) NOT NULL DEFAULT 0,  -- Entlastung fuer Aufgaben
    ermaessigungsstunden DECIMAL(5,2) NOT NULL DEFAULT 0,
    deputat_unterricht_verfuegbar DECIMAL(5,2) NOT NULL, -- fuer Stundenplan einsetzbar
    beschaeftigungsumfang_prozent DECIMAL(5,2) NULL,     -- z.B. 100.00, 75.00
    bemerkung TEXT NULL,
    FOREIGN KEY (lehrer_id) REFERENCES Lehrer(id) ON DELETE CASCADE,
    FOREIGN KEY (schuljahr_id) REFERENCES Schuljahr(id) ON DELETE CASCADE,
    UNIQUE (lehrer_id, schuljahr_id)
);
