TRADING BOT: WINDOWS SERVERGA O'RNATISH
=======================================

Tayyorgarlik (kompyuterdagi bot ishlab tursa ham bo'ladi, faqat 9-qadamda to'xtatiladi)

1. Serverda Git o'rnating (git-scm.com, standart sozlamalar), so'ng CMD da (GitHub repo manzilini o'zingiznikiga almashtiring;
   repo private bo'lsa, GitHub login/token so'raydi, ularni o'zingiz kiritasiz):
      cd C:\
      git clone <REPO_MANZILI> trading_bot
   Papka ichida main.py, config.py, deploy\ ... fayllari ko'rinishi kerak.

2. Python 3.12 o'rnating: python.org -> Downloads -> Windows.
   O'rnatishda "Add python.exe to PATH" katagini BELGILANG.
   Tekshirish (CMD): python --version

3. CMD da:
      cd C:\trading_bot
      pip install -r requirements_server.txt

4. XM MT5 ni xm.com saytidan yuklab o'rnating (xuddi kompyuterdagi kabi).
   Demo hisobga login qiling: Fayl -> Подключиться к торговому счету (login/serverni o'zingiz kiriting).

5. EA ni o'rnatish va kompilyatsiya (MT5 kamida bir marta ochilgan bo'lishi kerak):
      C:\trading_bot\deploy\install_ea.bat
   Oxirida "0 errors" chiqishi kerak.

6. MT5 da: Navigator -> Советники -> BridgeEA ni grafikka SUDRAB qo'ying (ikki marta bosmang: u MetaEditor ni ochadi).
   Oynada "Разрешить алгоритмическую торговлю" belgilang, AllowedMode = demo bo'lsin, OK.
   Yuqoridagi "Алгоритмическая торговля" tugmasi yashil bo'lsin.

7. Maxfiy sozlamalar (.env):
      cd C:\trading_bot
      copy .env.example .env
      notepad .env
   TELEGRAM_TOKEN, TELEGRAM_OWNER_ID, TG_LOGIN qiymatlarini kompyuterdagi .env faylidan ko'chirib yozing.
   (Yoki kompyuterdagi .env faylini RDP orqali C:\trading_bot ga nusxalang.)

8. Tekshiruv (bitim ochmaydi):
      cd C:\trading_bot
      python check_mt5.py
   Hisob raqami, "rejim: demo" va simvollar ro'yxati chiqsa, hammasi joyida.

KO'CHIRISH PAYTI (muhim)

9. Kompyuterdagi botni TO'XTATING (terminal oynasida Ctrl+C) va kompyuterdagi MT5 ni yoping yoki undan BridgeEA ni oling.
   Sabab: bitta Telegram bot tokeni faqat bitta joydan ishlaydi (aks holda "Conflict" xatosi), va ikkita bot
   ikki marta bitim ochib yuborishi mumkin.
   Ochiq bitim bo'lsa, jurnal faylini ham ko'chiring: kompyuterdagi journal_xm_demo.db ni serverdagi
   C:\trading_bot ga nusxalang (bot o'z bitimlarini shu fayldan taniydi). Ochiq bitim bo'lmasa, kerak emas.

10. Serverda botni ishga tushiring:
      C:\trading_bot\deploy\run_bot.bat
    Bu oyna ochiq turishi kerak (yopilsa bot to'xtaydi). Bot to'xtab qolsa, 30 soniyadan keyin o'zi qayta ishga tushadi.
    Telegramda botga login yozing (bir marta).

11. Server qayta ishga tushganda hammasi o'zi boshlanishi uchun:
      C:\trading_bot\deploy\autostart.bat
    (Windows'ga kirganda MT5 ochiladi, 90 soniyadan keyin bot ishga tushadi.)

YANGILASH (men GitHub'ga o'zgarish yuklaganimda)
   1) Serverda bot oynasida Ctrl+C (botni to'xtating).
   2) CMD da:
         cd C:\trading_bot
         git pull
   3) Agar o'zgarishlar orasida mql5\BridgeEA.mq5 bo'lsa (men aytaman): deploy\install_ea.bat ni ishga tushiring va MT5 da
      BridgeEA ni grafikka qayta sudrab qo'ying.
   4) Botni qayta ishga tushiring: deploy\run_bot.bat
   .env, jurnal (journal_*.db) va tg_auth.json GitHub'ga yuklanmaydi, shuning uchun git pull ularga tegmaydi.

RDP HAQIDA
- Serverdan chiqishda "Sign out" (Выйти) QILMANG. RDP oynasini oddiy yoping (X), seans ishlashda davom etadi.
- Server qayta yonsa, avtomatik kirish (auto-logon) sozlanmagan bo'lsa, o'zingiz RDP orqali kirishingiz kerak.

QOIDALAR
- Bir vaqtda faqat BITTA bot va BITTA BridgeEA ishlasin.
- MT5 va bot bir xil Windows foydalanuvchisi ostida ishlasin (fayllar shu foydalanuvchi papkasi orqali almashadi).
- Serverga kirish parolini hech kimga bermang, kuchli parol qo'ying.
- Hozircha faqat DEMO. Real hisobga o'tish alohida qaror.
