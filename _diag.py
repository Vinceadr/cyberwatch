import sqlite3

db_path = r'C:\Users\adrvi\AppData\Local\CyberWatch\data\db\cyberwatch.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== Articles avec date NULL par categorie ===")
rows = cur.execute(
    "SELECT c.nom, "
    "SUM(CASE WHEN a.date_publication IS NULL THEN 1 ELSE 0 END) as null_dates, "
    "SUM(CASE WHEN a.date_publication IS NOT NULL THEN 1 ELSE 0 END) as has_dates, "
    "COUNT(*) as total "
    "FROM articles a "
    "LEFT JOIN categories c ON a.categorie_id = c.id "
    "GROUP BY c.nom ORDER BY total DESC"
).fetchall()
for r in rows:
    print(f"  {r['nom']}: {r['total']} total, {r['null_dates']} NULL dates, {r['has_dates']} with dates")

print("\n=== Sample dates par categorie ===")
for cat in ['Reseaux', 'IA', 'Cybersecurite']:
    row = cur.execute(
        "SELECT a.date_publication, a.titre, s.nom "
        "FROM articles a "
        "LEFT JOIN categories c ON a.categorie_id = c.id "
        "LEFT JOIN sources s ON a.source_id = s.id "
        "WHERE c.nom = ? "
        "ORDER BY a.date_publication DESC LIMIT 3", (cat,)
    ).fetchall()
    print(f"\n  {cat}:")
    for r in row:
        print(f"    [{r['nom']}] date={r['date_publication']} | {str(r['titre'])[:50]}")

conn.close()
