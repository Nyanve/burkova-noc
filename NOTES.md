# NOTES

## Predpoklady (pravidlá evalu)

- **Rozhoduje stav v momente zloženia.** Čo prišlo po `hangup`, volajúci nepočul. Výnimky podľa labelov:
  - volajúci zložil počas `get_outage` a ten neskôr zlyhal alebo neodpovedal → `API_ERROR`; neskoré `ok` → `ENDED_EARLY`,
  - zložil počas prepájania a prepojenie potom zlyhalo → `TRANSFER_FAILED`.
- **Pri viacerých výsledkoch vyhráva posledný** (timeout → retry ok = `KNOWN_OUTAGE_INFORMED`, timeout → fallback hlásenie = `TICKET_CREATED`). Výnimka: zlyhanie nástroja nezruší úspech, ktorý volajúci už počul (napr. zlyhaný `update_ticket` po založenom hlásení).
- **`KNOWN_OUTAGE_INFORMED` vyžaduje, aby to bot povedal**, teda bot replika po výsledku `get_outage` a pred zložením.
- **Odmietnutá adresa** = resolver vrátil `ok`, ale bot znova volá `resolve_address`. Detekujem to zo štruktúry, nie z textu „nie“.
- **Sporné rozhodnutia** (ak ich hodnotitelia vidia inak, prevrátia sa spolu): technická chyba `resolve_address` → `API_ERROR`; hlásenie po neúspešnom prepojení → `TICKET_CREATED`; `create_ticket` dobehne `ok` po zložení → `TICKET_CREATED`; `caller_abandoned` → `TRANSFER_FAILED`; neskoré `connected` po zložení → `ENDED_EARLY`; prepojenie na zákaznícku linku → `OUT_OF_SCOPE`.
- „Zlyhanie“ v čísle 12 % neobsahuje `ENDED_EARLY`. Časť z neho (273 čakajúcich na OMS) je hraničná.

## Návrh evalu pre „ďalšiu noc“

Klasifikátor nečíta text bota ani volajúceho, len štruktúru (výsledky nástrojov, `transfer`, `route`, `hangup`). Preformulovaný flow ho preto nerozbije.
- Neznámy stav = zlyhanie. Nástroje rozpoznáva podľa časti mena alebo podľa tvaru výsledku (`*_id`).
- Udalosti triedi podľa `t`.
- Pokazený riadok zachráni (call_id + celé udalosti pred chybou). Duplicitné `call_id` a chýbajúci `hangup` beh nezhodia.
- Všetko, čo na noci 1 nebolo (stav, nástroj, typ udalosti, cieľ prepojenia, `hangup.by`, poradie), vypíše na stderr ako `DRIFT`. Na workshope hneď vidím, čo sa zmenilo, a label sa tým nemení.

**Ako som to otestoval:** v druhom, nezávislom chate som vygeneroval syntetickú „druhú noc“: 3 000 hovorov, z toho 1 193 s jednou produkčnou zmenou (33 typov: flow v15, nové chybové stavy, fallbacky, `get_outage_v2`, nové udalosti, premiešané poradie, pokazený JSON…). Labely sa určovali len zo zadania, kód som do toho chatu ukázal až potom. Výsledok bol **99,40 %**. Opravil som 3 nájdené chyby a 3 sondy, odvtedy **99,97 %** (100 % na nesporných) a výstup noci 1 je bajt po bajte rovnaký. Nové pravidlá pokrýva `test_classify.py`.

## Čo som navrhol a zmeral, ale nestaval

Moja úloha je eval (čo funguje a čo nie), nie oprava bota. Nápady na opravy som overil malými jednorazovými skriptmi na nedeľných dátach, aby mal každý návrh číslo. V odovzdaní nie sú.

- **Adresy rozdelené ASR** („se nec“, „tridsa ťštyri“):
  - Najprv som spájal susedné slová (max. 12 pokusov na vetu): 171 zo 456, 11 ms na vetu.
  - Potom som to zjednodušil na zmazanie všetkých medzier a hľadanie ulice, čísla a obce ako podreťazcov: **291 zo 456, 1 pokus, 0,45 ms, 0 zlých zhôd** na 9 451 hovoroch so známou adresou.
  - Register som poskladal z adries potvrdených v ten večer (1 870), plný register Voltiky nemám.
- **Odpoveď podľa oblasti:** v praxi sú výpadky po oblastiach. Testovacie dáta to nemodelujú (každá adresa má vlastnú poruchu, rovnaká adresa dostane v rôznych hovoroch rôzne `outage_id`), preto je to len otázka pre Voltiku.
- **SMS / následné správy:** SMS by obsahovala to isté, čo hovorí bot, takže od Voltiky stačí jeden súhlas, žiadne nové texty. Dosah po ľuďoch a cena: ~80 € za noc pre ~1 530 ľudí bez pomoci. Cena SMS je predpoklad.
- **Fallbacky:** pre každý typ zlyhania koľko hovorov by zachránil (REPORT, príloha B).

## Čo som vedome nerobil

- **LLM ani ML klasifikátor.** Dáta sú štruktúrované (37 ciest hovorom). Pravidlá sú presné, vysvetliteľné a bežia offline jedným príkazom.
- **Overenie, či resolver vrátil správnu adresu, keď volajúci povedal „áno“.** Na noci 1 to nenastáva: odpovede volajúcich sú konzistentné a `address_id` → text je 1:1.
- **Dashboard ani vizualizácie.** Klientka potrebuje odpoveď, nie graf.
- **Príčinu incidentu v OMS.** Z dát ju nezistím, preto je to otázka pre IT Voltiky (REPORT, príloha A).

## S viac časom

- Interne overiť, prečo `create_ticket` padal v tom istom okne ako OMS (spoločná závislosť?).
- Prejsť 1 100 opakovaných hovorov ako cestu zákazníka: kto volal 3× a nikdy sa nedovolal.
- Kontrolovať text bota proti udalostiam (napr. povedané ETA nesedí s `result.eta`).
- Vyskúšať vyhľadávanie adries na plnom registri Voltiky.

## Ako som použil AI nástroje

- **Claude Code, hlavný chat:** prieskum dát, `classify.py` a test, výpočty, rozbor incidentu, experimenty s adresami, prvé verzie textov.
- **Claude Code, druhý nezávislý chat (red team):** generoval syntetickú druhú noc a labely bez toho, aby videl kód. Až potom pustil klasifikátor a navrhol opravy. Nezávislosť bola zámer: chat, ktorý kód napísal, si vlastné predpoklady neotestuje.
- **Môj vstup a overenie:**
  - pochopenie zadania a rozhodnutie, čo je pre klientku dôležité,
  - nápad so spájaním rozdelených slov, odpoveď podľa oblasti a následné SMS s rovnakým obsahom, aký hovorí bot,
  - kontrola súčtov (11 400), sporných prípadov z `note` a toho, či mail nesľubuje nič mimo nášho vplyvu,
  - otázka, či je incident naozaj preťaženie (nebol),
  - skrátenie a doplnenie mailu.
- **Kde sa agent mýlil:**
  - Prvá verzia nastavovala `KNOWN_OUTAGE_INFORMED` už pri výsledku `get_outage`, nie keď to bot povedal.
  - Ignorovala prepojenie, ktoré zlyhalo až po zložení.
  - Ani jedno sa na noci 1 neprejavilo (60/60). Našiel to až red-team chat.
  - Menšie: zbytočne zamotaná podmienka pri `ADDRESS_NOT_UNDERSTOOD` (výsledok správny, ale len náhodou).
  - Agent na začiatku navrhoval mail skrátiť, hoci limit je 200 slov a treba v ňom uviesť aj incident OMS. Opravil som to.
