import json, storage
d = storage.load()
with open("_seed.json", "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False)
print("trades:", len(d["trades"]), "history:", len(d["history"]), "units:", d.get("units"))
