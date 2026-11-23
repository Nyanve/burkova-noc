# Búrková noc – riešenie

Zadanie: `README.md` z `burkova-noc.zip`. Python 3.9+, bez závislostí. Dáta nie sú priložené, priečinok `data/` zo zadania stačí nakopírovať vedľa `classify.py`.

```sh
python3 classify.py data/transcripts.jsonl > predictions_night1.csv   # eval (súhrn + DRIFT na stderr)
python3 test_classify.py                                              # 60/60 labeled sample + drift testy
```

Presnosť: 60/60 na `labeled_sample.jsonl`; 99,97 % na syntetickej „druhej noci“ (3 000 hovorov, 33 typov produkčných zmien, viď NOTES.md).

- `predictions_night1.csv` – label pre všetkých 11 400 hovorov
- [REPORT.md](REPORT.md) – čísla (2), mail klientke (3), čo ďalej (4)
- [NOTES.md](NOTES.md) – predpoklady, čo som nerobil, AI nástroje
