import random
import csv
import os
import math
from datetime import date, timedelta
from collections import defaultdict

# ==========================================
# KONFIGURATION
# ==========================================
SCHULJAHR = '2026/27'
SCHULJAHR_START = date(2026, 8, 1)
SCHULJAHR_END = date(2027, 7, 31)

FAECHER = [
    ('D', 'Deutsch', 'I'), ('E', 'Englisch', 'I'), ('F', 'Französisch', 'I'), ('L', 'Latein', 'I'), ('S', 'Spanisch', 'I'),
    ('KU', 'Kunst', 'I'), ('MU', 'Musik', 'I'), ('GE', 'Geschichte', 'II'), ('EK', 'Erdkunde', 'II'), ('SW', 'Sozialwissenschaften', 'II'),
    ('PL', 'Philosophie', 'II'), ('PA', 'Pädagogik', 'II'), ('M', 'Mathematik', 'III'), ('BI', 'Biologie', 'III'),
    ('CH', 'Chemie', 'III'), ('PH', 'Physik', 'III'), ('IF', 'Informatik', 'III'), ('ER', 'Evangelische Religionslehre', 'ohne'),
    ('KR', 'Katholische Religionslehre', 'ohne'), ('SP', 'Sport', 'ohne')
]

KLASSEN_SEK_I = {
    '5': {'a': 28, 'b': 29, 'c': 30, 'd': 31}, '6': {'a': 28, 'b': 29, 'c': 29, 'd': 30},
    '7': {'a': 28, 'b': 28, 'c': 30, 'd': 31}, '8': {'a': 29, 'b': 29, 'c': 30, 'd': 31},
    '9': {'a': 30, 'b': 29, 'c': 29, 'd': 28}, '10': {'a': 29, 'b': 29, 'c': 30}
}

RAEUME = (
    [f'R-{jg}{bez}' for jg, klassen in KLASSEN_SEK_I.items() for bez in klassen] +
    [f'Physikraum {i}' for i in range(1, 4)] +
    [f'Chemieraum {i}' for i in range(1, 4)] +
    [f'Biologieraum {i}' for i in range(1, 4)] +
    [f'Computerraum {i}' for i in range(1, 4)] +
    [f'Turnhalle {i}' for i in range(1, 4)] +
    [f'Kursraum {i}' for i in range(1, 21)]
)

STUFEN_SEK_II = {'EF': 117, 'Q1': 110, 'Q2': 103}

VERWANDTE_FAECHER = {
    'M': ['PH', 'IF', 'CH', 'SP'], 'D': ['GE', 'PA', 'PL', 'E'], 'E': ['F', 'S', 'L', 'GE'],
    'BI': ['CH', 'SP', 'M'], 'GE': ['SW', 'D', 'PL'], 'PH': ['M', 'IF']
}

WOCHENTAGE = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']
SEK_I_STUNDEN = 6 # 1. bis 6. Stunde jeden Tag (1-6)

# ==========================================
# HILFSFUNKTIONEN
# ==========================================
def random_date(start_year, end_year):
    start = date(start_year, 1, 1)
    return start + timedelta(days=random.randint(0, (date(end_year, 12, 31) - start).days))

def generate_kuerzel(vorname, nachname, used_kuerzel):
    k = f"{vorname[0]}{nachname[:2]}".upper()
    original_k = k
    counter = 1
    while k in used_kuerzel:
        k = f"{original_k[:2]}{counter}"
        counter += 1
    used_kuerzel.add(k)
    return k

def load_names_from_files(out_dir):
    vornamen_m, vornamen_w, nachnamen = [], [], []
    vp, np = os.path.join(out_dir, 'vornamen.txt'), os.path.join(out_dir, 'nachnamen.txt')
    if os.path.exists(vp):
        with open(vp, 'r', encoding='utf-8') as f:
            mode = None
            for line in (l.strip() for l in f if l.strip()):
                if line == '# Männlich': mode = 'M'
                elif line == '# Weiblich': mode = 'W'
                elif mode == 'M': vornamen_m.append(line)
                elif mode == 'W': vornamen_w.append(line)
    if os.path.exists(np):
        with open(np, 'r', encoding='utf-8') as f:
            nachnamen = [l.strip() for l in f if l.strip() and not l.startswith('#')]
    return vornamen_m, vornamen_w, nachnamen

def export_csv(out_dir, filename, headers, data):
    filepath = os.path.join(out_dir, filename)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';', quotechar='"')
        writer.writerow(headers)
        writer.writerows(data)
    print(f"Erstellt: {filepath} ({len(data)} Zeilen)")

def pick_slots(freie_slots, target_std):
    blocks = []
    singles = []
    day_slots = defaultdict(list)
    for wt, st in freie_slots:
        day_slots[wt].append((wt, st))
        
    import random
    wts = list(range(5))
    random.shuffle(wts)
    for wt in wts:
        s_list = sorted(day_slots[wt], key=lambda x: x[1])
        used_for_blocks = set()
        for b_start in [1, 3, 5, 8]:
            if (wt, b_start) in s_list and (wt, b_start+1) in s_list:
                blocks.append([(wt, b_start), (wt, b_start+1)])
                used_for_blocks.update([(wt, b_start), (wt, b_start+1)])
        for s in s_list:
            if s not in used_for_blocks:
                singles.append(s)
                
    random.shuffle(blocks)
    random.shuffle(singles)
                
    picked = []
    remaining = target_std
    used_days = defaultdict(int) # wt -> anzahl stunden

    # 1. Bevorzuge saubere Doppelblöcke
    while remaining >= 2 and blocks:
        # Finde einen Block an einem Tag, an dem wir noch NICHTS haben
        b_idx = next((i for i, b in enumerate(blocks) if used_days[b[0][0]] == 0), -1)
        if b_idx != -1:
            b = blocks.pop(b_idx)
            picked.extend(b)
            used_days[b[0][0]] += 2
            remaining -= 2
            # Entferne alle restlichen Slots dieses Tages
            singles = [s for s in singles if s[0] != b[0][0]]
            blocks = [bx for bx in blocks if bx[0][0] != b[0][0]]
        else:
            break

    # 2. Fülle mit Einzelstunden an noch unberührten Tagen auf
    while remaining > 0 and singles:
        s_idx = next((i for i, s in enumerate(singles) if used_days[s[0]] == 0), -1)
        if s_idx != -1:
            s = singles.pop(s_idx)
            picked.append(s)
            used_days[s[0]] += 1
            remaining -= 1
        else:
            break

    # 3. Fallback: Wir müssen Stunden irgendwo reinquetschen, wo schon etwas liegt. ABER: Niemals mehr als 2 Stunden pro Tag!
    while remaining > 0:
        if singles:
            # Suche Single an Tag mit bisher max 1 Stunde
            s_idx = next((i for i, s in enumerate(singles) if used_days[s[0]] < 2), -1)
            if s_idx != -1:
                s = singles.pop(s_idx)
                picked.append(s)
                used_days[s[0]] += 1
                remaining -= 1
            else:
                 s = singles.pop(0)
                 picked.append(s)
                 used_days[s[0]] += 1
                 remaining -= 1
        elif blocks:
            b = blocks.pop(0)
            picked.append(b[0]) # Nimm nur eine Stunde aus dem Block, um den Rest zu füllen
            used_days[b[0][0]] += 1
            remaining -= 1
        else:
            break

    for p in picked:
        if p in freie_slots:
            freie_slots.remove(p)
            
    return picked

# ==========================================
# HAUPTSKRIPT (SCHEDULE FIRST)
# ==========================================
def main():
    out_dir = 'db_DigitalesKlassenbuch'
    os.makedirs(out_dir, exist_ok=True)
    v_m, v_w, nachnamen_list = load_names_from_files(out_dir)
    if not v_m: v_m = ['Thomas', 'Michael']; v_w = ['Sabine', 'Susanne']; nachnamen_list = ['Müller', 'Schmidt']

    fach_to_id = {k: i for i, (k, _, _) in enumerate(FAECHER, 1)}
    
    raum_dict = {r: i for i, r in enumerate(RAEUME, 1)}
    raeume_sp = [r for r in RAEUME if r.startswith('SpH')]
    raeume_if = [r for r in RAEUME if r.startswith('IF')]
    raeume_nw = [r for r in RAEUME if r.startswith('NW')]
    raeume_allg = [r for r in RAEUME if r.startswith('R')] + ['Aula']

    # --- 1. GLOBALE RASTER & OBJEKTE ---
    kurs_objekte = [] # dicts mit allem, was wir haben
    
    # --- 2. SEK I GENERIERUNG UND BLOCKUNG ---
    # Jede Klasse bekommt ein 30-Slot Grid (5 Tage x 6 Stunden)
    # Slot = (wochentag_idx 0-4, stunde 1-6)
    sek_i_klassen_kurse = [('D',4), ('M',4), ('E',4), ('BI',2), ('PH',2), ('KU',2), ('MU',2), ('GE',2), ('EK',2), ('SP',3), ('IF',1)]
    # Summe oben = 28. Bleiben 2 fuer Reli = 30 perfekt. (WP in Jg 7-10 klauen wir Stunden von Nebenfächern, aber wir machen es vereinfacht)
    
    klasse_bez_to_id = {}
    klasse_id_counter = 1
    
    # Klassen-Definition
    for jg, klassen in KLASSEN_SEK_I.items():
        for bez, anzahl in klassen.items():
            klasse_bez_to_id[f'{jg}{bez}'] = klasse_id_counter
            klasse_id_counter += 1

    for jg, klassen in KLASSEN_SEK_I.items():
        # A) Jahrgangsbänder (alle Klassen des Jg gleichzeitig)
        # z.B. Mi 3+4 für Reli
        band_reli = [(2, 3), (2, 4)] # Mi 3,4 (Block 2)
        band_wp = [(3, 8), (3, 9), (4, 1)] # Do 8,9 (Block 4) + Fr 1
        band_kumu = [(1, 1), (1, 2)] # Di 1,2 (Block 1) für KU/MU in Jg 9, 10
        
        # Reli Kurse generieren
        jg_reli_kurse = []
        for rel_fach in ['ER', 'KR', 'PL']:
            c = {'fach': rel_fach, 'stunden': 2, 'jg': jg, 'art': 'Religion/Ethik', 'bez': f'{jg}-{rel_fach}', 'slots': band_reli.copy(), 'is_seki': True}
            kurs_objekte.append(c)
            jg_reli_kurse.append(c)
            
        # WP Kurse (Jg 7-10)
        jg_wp_kurse = []
        if int(jg) >= 7:
            for wp_fach in ['F', 'L', 'IF']:
                c = {'fach': wp_fach, 'stunden': 3, 'jg': jg, 'art': 'Wahlpflicht', 'bez': f'{jg}-WP-{wp_fach}', 'slots': band_wp.copy(), 'is_seki': True}
                kurs_objekte.append(c)
                jg_wp_kurse.append(c)
                
        # KU/MU Kurse (Jg 9-10)
        jg_kumu_kurse = []
        if int(jg) >= 9:
            for kumu_fach in ['KU', 'MU']:
                c = {'fach': kumu_fach, 'stunden': 2, 'jg': jg, 'art': 'Wahlpflicht', 'bez': f'{jg}-{kumu_fach}-Band', 'slots': band_kumu.copy(), 'is_seki': True}
                kurs_objekte.append(c)
                jg_kumu_kurse.append(c)
                
        # B) Klassen intern abarbeiten
        for bez, anzahl in klassen.items():
            kl_id = klasse_bez_to_id[f'{jg}{bez}']
            # Die Klassen-Fächer verteilen
            local_faecher = sek_i_klassen_kurse.copy()
            if int(jg) >= 9:
                 local_faecher = [('D',4), ('M',4), ('E',4), ('BI',2), ('PH',2), ('GE',2), ('EK',2), ('SP',3)]
            elif int(jg) >= 7:
                 local_faecher = [('D',4), ('M',4), ('E',4), ('BI',2), ('PH',2), ('KU',2), ('MU',1), ('GE',2), ('EK',2), ('SP',2)]
            else:
                 local_faecher = [('D',4), ('M',4), ('E',4), ('BI',2), ('PH',2), ('KU',2), ('MU',2), ('GE',2), ('EK',2), ('SP',3), ('IF',1)]
            
            # 1. Berechne Gesamtstunden dieser Klasse
            total_std = sum(std for f, std in local_faecher)
            total_std += 2 # Reli
            if int(jg) >= 7: total_std += 3 # WP
            if int(jg) >= 9: total_std += 2 # KU/MU
            
            # 2. Erstelle exakt passende freie Slots
            freie_slots = []
            for wt in range(5):
                for st in range(1, 7): # Basis: 1-6
                    freie_slots.append((wt, st))
                    
            hours_to_add = total_std - 30
            wt_to_extend = 0
            while hours_to_add > 0:
                if hours_to_add >= 2:
                    freie_slots.append((wt_to_extend, 8))
                    freie_slots.append((wt_to_extend, 9))
                    hours_to_add -= 2
                else:
                    freie_slots.append((wt_to_extend, 7))
                    hours_to_add -= 1
                wt_to_extend = (wt_to_extend + 1) % 5
                
            # Reservierte Bänder entfernen
            for s in band_reli:
                if s in freie_slots: freie_slots.remove(s)
            if int(jg) >= 7:
                for s in band_wp:
                    if s in freie_slots: freie_slots.remove(s)
            if int(jg) >= 9:
                for s in band_kumu:
                    if s in freie_slots: freie_slots.remove(s)
            
            # Wichtig: Nach Stunden sortieren (große zuerst), damit wir die Doppelstunden gut legen können
            local_faecher = sorted(local_faecher, key=lambda x: -x[1])
            
            for fach, std in local_faecher:
                c = {'fach': fach, 'stunden': std, 'jg': jg, 'klasse': bez, 'art': 'Klassenunterricht', 'bez': f'{jg}{bez}-{fach}', 'slots': [], 'is_seki': True}
                picked = pick_slots(freie_slots, std)
                c['slots'] = picked
                kurs_objekte.append(c)


    # --- 3. SEK II GENERIERUNG (Schienen-Modell) ---
    sek_ii_stunden = {'GK': 3, 'LK': 5}
    sek_ii_schienen = [
        [(0,1),(0,2),(3,3)], [(0,3),(0,4),(3,4)], [(0,5),(0,6),(3,5)],
        [(1,1),(1,2),(4,1)], [(1,3),(1,4),(4,2)], [(1,5),(1,6),(4,3)],
        [(2,1),(2,2),(4,4)], [(2,3),(2,4),(4,5)], [(2,5),(2,6),(4,6)],
        [(0,8),(0,9),(2,8),(2,9),(4,8)], 
        [(1,8),(1,9),(3,8),(3,9),(4,7)]
    ]
    
    for jg, anzahl in STUFEN_SEK_II.items():
        anzahl_gk = math.ceil(anzahl / 22)
        anzahl_lk = math.ceil(anzahl / 15) if jg != 'EF' else 0
        
        # Ordne Fächer auf Schienen (vereinfacht: reihum)
        schiene_gk_idx = 0
        schiene_lk_idx = 9 # LK Schienen fangen später an
        
        for fach in ['D', 'M', 'E', 'SP', 'BI', 'GE', 'KU', 'SW', 'PH', 'CH', 'ER', 'PL']:
            num_gks = anzahl_gk if fach in ['D','M','E','SP'] else max(1, anzahl_gk // 2)
            for i in range(num_gks):
                c = {'fach': fach, 'stunden': sek_ii_stunden['GK'], 'jg': jg, 'art': 'GK', 'bez': f'{jg}-{fach}-GK{i+1}', 'slots': sek_ii_schienen[schiene_gk_idx].copy(), 'is_seki': False}
                kurs_objekte.append(c)
                schiene_gk_idx = (schiene_gk_idx + 1) % 9
                
            if jg != 'EF' and fach in ['D', 'M', 'E', 'BI', 'GE']:
                for i in range(anzahl_lk):
                    c = {'fach': fach, 'stunden': sek_ii_stunden['LK'], 'jg': jg, 'art': 'LK', 'bez': f'{jg}-{fach}-LK{i+1}', 'slots': sek_ii_schienen[schiene_lk_idx].copy(), 'is_seki': False}
                    kurs_objekte.append(c)
                    schiene_lk_idx = 9 if schiene_lk_idx == 10 else 10



    # --- 5. LEHRER GENERIEREN (Fitting Algorithm) ---
    lehrkraefte = [] # id, faecher, kuerzel, slots
    lehrer_id_counter = 1
    unversorgte_kurse = kurs_objekte.copy()
    used_kuerzel = set()

    while unversorgte_kurse:
        # Finde faecher, die am meisten gebraucht werden
        fach_count = defaultdict(int)
        for c in unversorgte_kurse: fach_count[c['fach']] += 1
        hauptfach = max(fach_count.items(), key=lambda x: x[1])[0]
        
        faecher = [hauptfach]
        if hauptfach in VERWANDTE_FAECHER and random.random() < 0.7: faecher.append(random.choice(VERWANDTE_FAECHER[hauptfach]))
        else: faecher.append(random.choice(list(fach_count.keys())))
        
        # Lehrer anlegen
        is_male = random.choice([True, False])
        vorname = random.choice(v_m if is_male else v_w)
        nachname = random.choice(nachnamen_list)
        l_dict = {
            'id': lehrer_id_counter, 'kuerzel': generate_kuerzel(vorname, nachname, used_kuerzel),
            'vorname': vorname, 'nachname': nachname, 'geb': random_date(1960, 1995),
            'faecher': set(faecher), 'slots': set(), 'zugewiesen_stunden': 0
        }
        
        # Kurse aufladen bis max 26 h
        kurse_fuer_diesen_lehrer = []
        
        # Pass 1: Genau die beiden Faecher
        for c in unversorgte_kurse:
            if c['fach'] in l_dict['faecher']:
                kollision = any(s in l_dict['slots'] for s in c['slots'])
                if not kollision and l_dict['zugewiesen_stunden'] + c['stunden'] <= 26:
                    kurse_fuer_diesen_lehrer.append(c)
                    l_dict['zugewiesen_stunden'] += c['stunden']
                    l_dict['slots'].update(c['slots'])
                    
        # Pass 2: Wenn der Lehrer stark unterbelegt ist (unter 15 Stunden), darf er fachfremd aushelfen
        if l_dict['zugewiesen_stunden'] < 15:
            for c in unversorgte_kurse:
                if c not in kurse_fuer_diesen_lehrer:
                    kollision = any(s in l_dict['slots'] for s in c['slots'])
                    if not kollision and l_dict['zugewiesen_stunden'] + c['stunden'] <= 26:
                        kurse_fuer_diesen_lehrer.append(c)
                        l_dict['zugewiesen_stunden'] += c['stunden']
                        l_dict['slots'].update(c['slots'])
                        l_dict['faecher'].add(c['fach']) # Fach offiziell hinzufügen
                        if l_dict['zugewiesen_stunden'] >= 20:
                            break

        # Zuweisung eintragen und von Todos loeschen
        for c in kurse_fuer_diesen_lehrer:
            c['lehrer_id'] = l_dict['id']
            unversorgte_kurse.remove(c)
            
        lehrkraefte.append(l_dict)
        lehrer_id_counter += 1

    # --- 6. DATEN UMGIESSEN & CSV OBJEKTE ERSTELLEN ---
    lehrer_data = []
    lehrer_deputation_data = []
    lehrbefaehigung_data = []
    for l in lehrkraefte:
        lehrer_data.append([l['id'], l['kuerzel'], l['vorname'], l['nachname'], l['geb'], 1])
        soll = max(l['zugewiesen_stunden'], 13) # Unterstes legales Limit simulieren
        umfang = round((soll / 25.5) * 100, 2)
        lehrer_deputation_data.append([l['id'], l['id'], 1, soll, 0, 0, l['zugewiesen_stunden'], umfang, ''])
        for fach in l['faecher']:
            lehrbefaehigung_data.append([l['id'], fach_to_id[fach]])

    klasse_data = []
    for bez, kid in klasse_bez_to_id.items():
        jg = bez[:-1] if len(bez) == 2 else bez[:-1] # 5a -> 5, 10a -> 10
        klasse = bez[-1]
        moegliche_kl = [l['id'] for l in lehrkraefte if 'D' in l['faecher'] or 'M' in l['faecher'] or 'E' in l['faecher']]
        kl_id = random.choice(moegliche_kl) if moegliche_kl else lehrkraefte[0]['id']
        klasse_data.append([kid, 1, jg, klasse, kl_id])

    # --- RAUMZUWEISUNG (Kollisionsfrei) ---
    raum_dict = {name: i for i, name in enumerate(RAEUME, 1)}
    raum_belegung = defaultdict(set) # r_id -> set of (wt_idx, st)
    
    def assign_room(c, possible_rooms):
        for r_name in possible_rooms:
            r_id = raum_dict[r_name]
            # Prüfen ob Raum in allen benötigten Slots frei ist
            if all((wt, st) not in raum_belegung[r_id] for (wt, st) in c['slots']):
                for (wt, st) in c['slots']:
                    raum_belegung[r_id].add((wt, st))
                c['raum_id'] = r_id
                return True
        return False

    # 1. Fachräume verteilen (harte Anforderung)
    fachraum_map = {
        'PH': [f'Physikraum {i}' for i in range(1, 4)],
        'CH': [f'Chemieraum {i}' for i in range(1, 4)],
        'BI': [f'Biologieraum {i}' for i in range(1, 4)],
        'IF': [f'Computerraum {i}' for i in range(1, 4)],
        'SP': [f'Turnhalle {i}' for i in range(1, 4)]
    }
    for c in kurs_objekte:
        if c['fach'] in fachraum_map:
            assigned = assign_room(c, fachraum_map[c['fach']])
            if not assigned:
                # Fallback auf generische Kursräume wenn Fachräume voll
                assign_room(c, [f'Kursraum {i}' for i in range(1, 21)])

    # 2. Klassenräume (für klassengebundene Kurse, die keine Fachräume sind)
    for c in kurs_objekte:
        if 'raum_id' not in c and c.get('is_seki') and c.get('klasse'):
            # Eigener Klassenraum
            my_room = f"R-{c['jg']}{c['klasse']}"
            assigned = assign_room(c, [my_room])
            if not assigned:
                assign_room(c, [f'Kursraum {i}' for i in range(1, 21)])

    # 3. Rest (Kurse der Sek II, WP, Reli-Bänder etc.)
    generic_rooms = [f'Kursraum {i}' for i in range(1, 21)] + [f'R-{jg}{bez}' for jg, klassen in KLASSEN_SEK_I.items() for bez in klassen]
    for c in kurs_objekte:
        if 'raum_id' not in c:
            assign_room(c, generic_rooms)

    kurs_data = []
    stundenplan_data = []
    kurs_id_counter = 1
    sp_id_counter = 1
    
    for c in kurs_objekte:
        kid = klasse_bez_to_id.get(f"{c['jg']}{c.get('klasse')}", '')
        # id, schuljahr, abschnitt, bez, fach, lehrer, jg, kl_id, kursart, wochenstd, parallel
        kurs_row = [kurs_id_counter, 1, '', c['bez'], fach_to_id[c['fach']], c['lehrer_id'], c['jg'], kid, c['art'], c['stunden'], '']
        kurs_data.append(kurs_row)
        c['id'] = kurs_id_counter
        
        # Stundenplan Slots erstellen
        for (wt_idx, st) in c['slots']:
            # Wenn ein Kurs absolut keinen Raum gefunden haben sollte (extremst unwahrscheinlich bei so vielen Räumen), r_id = NULL
            r_id = c.get('raum_id', '') 
            stundenplan_data.append([sp_id_counter, kurs_id_counter, 1, r_id, wt_idx + 1, st, '2026-08-01', ''])
            sp_id_counter += 1
            
        kurs_id_counter += 1

    # --- 7. SCHUELER BELEGUNGEN ---
    schueler_data = []
    schueler_status_data = []
    kursbelegung_data = []
    schueler_id_counter = 1
    
    kursbelegung_dict = defaultdict(list) # fuer Anwesenheit (kurs_id -> [schueler_ids])

    # Helper: Kurse finden
    kurse_by_jg = defaultdict(list)
    kurse_by_klasse = defaultdict(list)
    for c in kurs_objekte:
        kurse_by_jg[c['jg']].append(c)
        if c.get('klasse'): kurse_by_klasse[f"{c['jg']}{c['klasse']}"].append(c)

    for jg, klassen in KLASSEN_SEK_I.items():
        base_y = 2026 - int(jg) - 6
        for bez, anzahl in klassen.items():
            kl_id = klasse_bez_to_id[f'{jg}{bez}']
            k_kurse = kurse_by_klasse[f'{jg}{bez}']
            reli_k = [x for x in kurse_by_jg[jg] if x['art'] == 'Religion/Ethik']
            wp_k = [x for x in kurse_by_jg[jg] if x['art'] == 'Wahlpflicht' and x['fach'] not in ['KU', 'MU']]
            kumu_k = [x for x in kurse_by_jg[jg] if x['art'] == 'Wahlpflicht' and x['fach'] in ['KU', 'MU']]
            
            for _ in range(anzahl):
                ism = random.choice([True, False])
                schueler_data.append([schueler_id_counter, random.choice(v_m if ism else v_w), random.choice(nachnamen_list), random_date(base_y, base_y+1), 1])
                schueler_status_data.append([schueler_id_counter, schueler_id_counter, 1, jg, kl_id, 'normal'])
                
                # Alle Klassenkurse belegen
                for c in k_kurse: 
                    kursbelegung_data.append([schueler_id_counter, c['id']])
                    kursbelegung_dict[c['id']].append(schueler_id_counter)
                
                # 1 Reli Kurs belegen
                if reli_k: 
                    wc = random.choice(reli_k)
                    kursbelegung_data.append([schueler_id_counter, wc['id']])
                    kursbelegung_dict[wc['id']].append(schueler_id_counter)
                    
                # 1 WP Kurs belegen
                if wp_k:
                    wc = random.choice(wp_k)
                    kursbelegung_data.append([schueler_id_counter, wc['id']])
                    kursbelegung_dict[wc['id']].append(schueler_id_counter)
                    
                # 1 KU/MU Kurs belegen (Jg 9-10)
                if kumu_k:
                    wc = random.choice(kumu_k)
                    kursbelegung_data.append([schueler_id_counter, wc['id']])
                    kursbelegung_dict[wc['id']].append(schueler_id_counter)

                schueler_id_counter += 1

    for jg, anzahl in STUFEN_SEK_II.items():
        base_y = 2026 - {'EF':10, 'Q1':11, 'Q2':12}[jg] - 6
        jg_gks = [c for c in kurse_by_jg[jg] if c['art'] == 'GK']
        jg_lks = [c for c in kurse_by_jg[jg] if c['art'] == 'LK']
        
        for _ in range(anzahl):
            ism = random.choice([True, False])
            schueler_data.append([schueler_id_counter, random.choice(v_m if ism else v_w), random.choice(nachnamen_list), random_date(base_y, base_y+1), 1])
            schueler_status_data.append([schueler_id_counter, schueler_id_counter, 1, jg, '', 'normal'])
            
            # 2 LKs
            if jg != 'EF' and len(jg_lks) >= 2:
                for c in random.sample(jg_lks, 2): 
                    kursbelegung_data.append([schueler_id_counter, c['id']])
                    kursbelegung_dict[c['id']].append(schueler_id_counter)
            
            # 8 GKs
            if len(jg_gks) >= 8:
                for c in random.sample(jg_gks, 8):
                    kursbelegung_data.append([schueler_id_counter, c['id']])
                    kursbelegung_dict[c['id']].append(schueler_id_counter)
            
            schueler_id_counter += 1

    # --- 8. AUSROLLEN: UNTERRICHTSSTUNDE & ANWESENHEIT ---
    unterrichtsstunde_data = []
    anwesenheit_data = []
    us_id_counter = 1
    anw_id_counter = 1
    
    sim_start = date(2026, 8, 3) # Montag
    sp_by_wt = defaultdict(list)
    for sp in stundenplan_data: sp_by_wt[sp[4]].append(sp)
        
    for day_offset in range(26):
        curr_date = sim_start + timedelta(days=day_offset)
        if curr_date.weekday() > 4: continue
        wt_id = curr_date.weekday() + 1
        
        for sp in sp_by_wt[wt_id]:
            sp_id, k_id = sp[0], sp[1]
            status = random.choices(['gehalten', 'entfallen', 'vertretung'], weights=[0.92, 0.04, 0.04])[0]
            v_id = random.choice(lehrkraefte)['id'] if status == 'vertretung' else ''
            ist_kl = 1 if random.random() < 0.02 else 0
            
            unterrichtsstunde_data.append([us_id_counter, sp_id, curr_date, status, '', '', v_id, '', '', ist_kl, ''])
            
            if status in ['gehalten', 'vertretung']:
                for sid in kursbelegung_dict[k_id]:
                    ast = random.choices(['anwesend', 'fehlend_entschuldigt', 'fehlend_unentschuldigt', 'verspaetet'], weights=[0.92, 0.04, 0.02, 0.02])[0]
                    v_min = random.randint(5, 30) if ast == 'verspaetet' else 0
                    anwesenheit_data.append([anw_id_counter, us_id_counter, sid, ast, v_min, '', ''])
                    anw_id_counter += 1
            us_id_counter += 1


    # --- 9. EXPORTE ---
    schuljahr_data = [[1, SCHULJAHR, SCHULJAHR_START, SCHULJAHR_END, 1]]
    abschnitt_data = [
        [1, 1, '1. Hj', '2026-08-01', '2027-01-31'],
        [2, 1, '2. Hj', '2027-02-01', '2027-07-31']
    ]
    fach_data = [[i, k, n, a] for i, (k, n, a) in enumerate(FAECHER, 1)]
    wochentag_data = [[i+1, tag] for i, tag in enumerate(WOCHENTAGE)]
    raum_data = [[i, r] for i, r in enumerate(RAEUME, 1)]
    
    export_csv(out_dir, 'schuljahr.csv', ['id', 'bezeichnung', 'startdatum', 'enddatum', 'aktiv'], schuljahr_data)
    export_csv(out_dir, 'wochentag.csv', ['id', 'name'], wochentag_data)
    export_csv(out_dir, 'abschnitt.csv', ['id', 'schuljahr_id', 'code', 'startdatum', 'enddatum'], abschnitt_data)
    export_csv(out_dir, 'fach.csv', ['id', 'kuerzel', 'name', 'aufgabenfeld'], fach_data)
    export_csv(out_dir, 'raum.csv', ['id', 'bezeichnung'], raum_data)
    export_csv(out_dir, 'lehrer.csv', ['id', 'kuerzel', 'vorname', 'nachname', 'geburtsdatum', 'aktiv'], lehrer_data)
    export_csv(out_dir, 'lehrbefaehigung.csv', ['lehrer_id', 'fach_id'], lehrbefaehigung_data)
    export_csv(out_dir, 'klasse.csv', ['id', 'schuljahr_id', 'jahrgangsstufe', 'bezeichnung', 'klassenlehrer_id'], klasse_data)
    export_csv(out_dir, 'schueler.csv', ['id', 'vorname', 'nachname', 'geburtsdatum', 'aktiv'], schueler_data)
    export_csv(out_dir, 'schueler_status.csv', ['id', 'schueler_id', 'schuljahr_id', 'jahrgangsstufe', 'klasse_id', 'status_laufbahn'], schueler_status_data)
    
    export_csv(out_dir, 'kurs.csv', ['id', 'schuljahr_id', 'abschnitt_id', 'bezeichnung', 'fach_id', 'lehrer_id', 'jahrgangsstufe', 'klasse_id', 'kursart', 'wochenstunden', 'parallelgruppe'], kurs_data)
    export_csv(out_dir, 'kursbelegung.csv', ['schueler_id', 'kurs_id'], kursbelegung_data)
    export_csv(out_dir, 'lehrer_deputation.csv', ['id', 'lehrer_id', 'schuljahr_id', 'deputat_soll', 'anrechnungsstunden', 'ermaessigungsstunden', 'deputat_unterricht_verfuegbar', 'beschaeftigungsumfang_prozent', 'bemerkung'], lehrer_deputation_data)
    export_csv(out_dir, 'stundenplan.csv', ['id', 'kurs_id', 'schuljahr_id', 'raum_id', 'wochentag_id', 'stunde', 'gueltig_ab', 'gueltig_bis'], stundenplan_data)
    export_csv(out_dir, 'unterrichtsstunde.csv', ['id', 'stundenplan_id', 'datum', 'status', 'thema', 'hausaufgaben', 'vertretungslehrer_id', 'tatsaechlicher_raum_id', 'tatsaechliche_stunde', 'ist_klausur', 'notiz'], unterrichtsstunde_data)
    export_csv(out_dir, 'anwesenheit.csv', ['id', 'unterrichtsstunde_id', 'schueler_id', 'status', 'verspaetung_minuten', 'entschuldigungsstatus', 'anmerkung'], anwesenheit_data)

    print(f"\nGenerierung abgeschlossen: {len(lehrkraefte)} Lehrer fuer einen lückenlosen Sek I Stundenplan generiert!")

if __name__ == '__main__':
    main()
