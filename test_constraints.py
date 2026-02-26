import csv
from collections import defaultdict

def test_constraints():
    # 1. Load Kurs data to get subjects and grades
    kurse = {} # id -> (kuerzel, subject_id, jg)
    with open('db_DigitalesKlassenbuch/kurs.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            kurse[row['id']] = (row['bezeichnung'], row['fach_id'], row['jahrgangsstufe'])
            
    # 2. Load Stundenplan
    stundenplan = []
    with open('db_DigitalesKlassenbuch/stundenplan.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            stundenplan.append((row['kurs_id'], int(row['wochentag_id']) - 1, int(row['stunde']), row['raum_id']))
            
    # Group by kurs and wochentag
    kurs_day_stunden = defaultdict(list)
    kumu_slots = defaultdict(list)
    
    for kurs_id, wt, st, raum in stundenplan:
        kurs_day_stunden[(kurs_id, wt)].append(st)
        bez, fach, jg = kurse[kurs_id]
        if jg in ['9', '10'] and fach in ['6', '7']: # KU = 6, MU = 7
            kumu_slots[(jg, wt, st)].append(kurs_id)

    errors = 0
    
    # Verify blocks
    for (kurs_id, wt), stunden in kurs_day_stunden.items():
        stunden = sorted(stunden)
        if len(stunden) > 2:
            print(f"ERROR: Kurs {kurs_id} ({kurse[kurs_id][0]}) has {len(stunden)} hours on {wt}: {stunden}")
            errors += 1
        elif len(stunden) == 2:
            valid_blocks = [[1, 2], [3, 4], [5, 6], [8, 9]]
            if stunden not in valid_blocks:
                print(f"ERROR: Kurs {kurs_id} ({kurse[kurs_id][0]}) has INVALID block on {wt}: {stunden}")
                errors += 1

    # Verify KU/MU in 9/10
    jgs = defaultdict(list)
    for kurs_id, (bez, fach, jg) in kurse.items():
        if jg in ['9', '10'] and fach in ['6', '7']:
            jgs[jg].append(kurs_id)
            
    for jg, k_ids in jgs.items():
        k1 = k_ids[0]
        slots1 = set((wt, st) for (k_id, wt, st, raum) in stundenplan if k_id == k1)
        for k2 in k_ids[1:]:
            slots2 = set((wt, st) for (k_id, wt, st, raum) in stundenplan if k_id == k2)
            if slots1 != slots2:
                print(f"ERROR: KU/MU sync failed in {jg}: Kurs {k1} slots {slots1} != Kurs {k2} slots {slots2}")
                errors += 1

    # Verify Raum Collisions
    raum_slots = defaultdict(list)
    for (k_id, wt, st, raum_id) in stundenplan:
        if raum_id:
            raum_slots[(raum_id, wt, st)].append(k_id)
            
    for (raum, wt, st), kurse_ids in raum_slots.items():
        if len(kurse_ids) > 1:
            print(f"ERROR: Raumkollision in Raum {raum} am Tag {wt} Stunde {st} durch Kurse: {kurse_ids}")
            errors += 1

    if errors == 0:
        print("SUCCESS! All constraints verified.")
    else:
        print(f"FAILED with {errors} errors.")

if __name__ == '__main__':
    test_constraints()
