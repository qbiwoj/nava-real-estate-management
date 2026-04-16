# Strategia na przyszłość

## Kolejne kroki

### 1. Rozbudowane możliwości Voice AI
Obecny briefing głosowy to jednostronny odczyt kolejki. Naturalnym krokiem jest konwersacyjny agent głosowy — administrator może zapytać o konkretny wątek, podyktować odpowiedź lub oznaczyć sprawę jako zamkniętą, bez dotykania klawiatury. Możliwe też udostępnienie linii głosowej bezpośrednio mieszkańcom jako alternatywnego kanału zgłoszeń.

### 2. Iteracje na promptach i jakości odpowiedzi
Agent działa poprawnie, ale jakość szkiców odpowiedzi do mieszkańców można znacznie poprawić: lepsze dopasowanie tonu do kategorii sprawy, obsługa mieszanych wiadomości PL/EN, bardziej precyzyjne priorytety. Few-shot feedback loop już istnieje — potrzebuje więcej danych korekcyjnych i systematycznego testowania promptów (evals).

### 3. Aplikacja webowa dla mieszkańców
Panel admina to tylko jedna strona równania. Aplikacja dla mieszkańców umożliwiłaby składanie zgłoszeń, śledzenie statusu sprawy i odbieranie odpowiedzi w jednym miejscu — zamiast przez email czy SMS. Naturalnie integruje się z istniejącymi wątkami i historią wiadomości.

### 4. Obsługa wielu nieruchomości (multi-tenant)
Obecna architektura zakłada jedną nieruchomość. Dodanie warstwy tenant pozwoliłoby obsługiwać wiele budynków lub zarządców z jednej instancji — z izolacją danych, osobnymi konfiguracjami agenta i raportowaniem per-nieruchomość.

### 5. ~~Analityka i raporty~~ ✓ Zrealizowane
Dashboard z metrykami operacyjnymi został zaimplementowany.

### 6. Integracje z zewnętrznymi kanałami
Obecne webhooki wymagają ręcznego wywołania. Podłączenie prawdziwych dostawców (SendGrid dla emaila, Twilio dla SMS) zamknęłoby pętlę — wiadomości wpływają automatycznie, odpowiedzi są wysyłane bez opuszczania systemu.
