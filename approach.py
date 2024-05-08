# kilka wątków czekających na lock i tyle
# brak ograniczania 50 ms między requestami
# trzeba to zrekompensować rate-limiterem 

# kilka wątków czeka na lock, jeden jest puszczany, wysyła request, odbiera odpowiedź