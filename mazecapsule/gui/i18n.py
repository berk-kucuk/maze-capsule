"""English and Turkish strings.

English is the default whatever the system locale. Turkish is one click away
in the title bar (remembered in settings.json) or `maze-capsule --lang=tr`.
`t()` falls back to English, then to the key.
"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "bug_body": "This was a bug, not something you did. Nothing was deleted; the details are in the system journal.",
        # chrome
        "tip_minimize": "Minimize",
        "tip_maximize": "Maximize / Restore",
        "tip_close": "Close",
        "tip_settings": "Settings",
        "tip_language": "Language",
        # hero
        "eyebrow": "ENCRYPTED SPACES",
        "hero_title": "Your files,\nsealed in capsules.",
        "hero_sub": "Each capsule is a separate encrypted space. Put files and folders inside, "
                    "lock it, and nothing on this system can read them without your password.",
        "point_1": "AES-256-GCM encryption — file names and folder structure included",
        "point_2": "Every capsule is one portable folder that opens on any Linux with gocryptfs",
        "point_3": "No root, no cloud, no telemetry — and a recovery key, so a lost password is not lost data",
        "btn_new": "New capsule",
        "btn_add_existing": "Add existing",
        "menu_import": "Import a backup (.capsule.tar)…",
        "menu_link": "Add a capsule folder (USB disk, another drive)…",
        "menu_link_bare": "Add a plain gocryptfs folder…",
        # list
        "sec_capsules": "YOUR CAPSULES",
        "tb_capsules": "Capsules",
        "btn_trash": "Trash",
        "drawer_hint": "Deleted capsules stay here, still encrypted, until you remove them for good.",
        "trash_empty": "The trash is empty.",
        "sec_trash": "TRASH",
        "btn_lock_all": "Lock all",
        "empty_title": "No capsules yet",
        "empty_body": "Create your first capsule — it takes a name and a password.",
        "pill_locked": "LOCKED",
        "pill_unlocked": "UNLOCKED",
        "pill_ro": "READ-ONLY",
        "pill_offline": "NOT CONNECTED",
        "created": "Created {date}",
        "size": "{size} encrypted",
        "size_pending": "measuring…",
        "loc_default": "Stored in Maze Capsule",
        "loc_linked": "Stored in {path}",
        "loc_offline": "Folder not found: {path} — plug the disk in or check the location.",
        "mounted_at": "Open at {path}",
        "no_recovery": "Recovery key not saved yet",
        "btn_save_now": "Save it now",
        "drop_hint": "Drop files here to copy them in",
        "btn_unlock": "Unlock",
        "btn_open": "Open",
        "btn_add_files": "Add files",
        "btn_add_folder": "Add folder",
        "btn_shell": "Sandbox shell",
        "btn_lock": "Lock",
        "tip_more": "More",
        "low_space": "Only {free} free on this disk",
        # menu
        "m_rename": "Rename…",
        "m_password": "Change password…",
        "m_recovery": "Show recovery key…",
        "m_check": "Check integrity…",
        "m_export": "Export backup…",
        "m_location": "Show capsule folder",
        "m_delete": "Move to trash…",
        "m_forget": "Remove from list…",
        "m_lock_force": "Lock when files are closed",
        "trash_row": "Deleted {date}",
        "btn_restore": "Restore",
        "btn_purge": "Delete forever…",
        # dialogs, general
        "btn_cancel": "Cancel",
        "btn_close": "Close",
        "btn_done": "Done",
        "btn_create": "Create capsule",
        "btn_save": "Save",
        "btn_continue": "Continue",
        "btn_copy": "Copy",
        "btn_copied": "Copied",
        "btn_save_file": "Save to file…",
        "f_name": "NAME",
        "f_password": "PASSWORD",
        "f_confirm": "CONFIRM PASSWORD",
        "f_current": "CURRENT PASSWORD",
        "f_new": "NEW PASSWORD",
        "f_location": "LOCATION",
        "f_recovery": "RECOVERY KEY",
        "f_autolock": "AUTO-LOCK",
        "show_pw": "Show",
        "hide_pw": "Hide",
        "ph_name": "e.g. Documents, Photos, Work",
        "ph_recovery": "xxxxxxxx-xxxxxxxx-… (64 characters)",
        "loc_default_opt": "Maze Capsule's folder (recommended)",
        "loc_custom_opt": "A folder I choose — a USB disk, another drive…",
        "loc_choose": "Choose folder…",
        "loc_none": "No folder chosen",
        "name_visible": "The capsule's name is visible on this computer. Its contents, file names "
                        "and folder structure are encrypted.",
        "strength_0": "Too short — at least {n} characters",
        "strength_1": "Weak",
        "strength_2": "Fair",
        "strength_3": "Good",
        "strength_4": "Strong",
        "pw_mismatch": "The passwords do not match.",
        "pw_hint": "Use a passphrase of several words. There is no way to read a capsule "
                   "without its password or recovery key — not even for Maze Linux.",
        # new
        "new_title": "New capsule",
        "creating": "Creating the capsule and sealing its key…",
        # recovery
        "rk_title": "Your recovery key",
        "rk_body_new": "If you ever forget the password, this key is the only way back into "
                       "“{name}”. Write it down or save it somewhere outside this computer — a "
                       "password manager, paper, a USB stick. Anyone with this key can open the "
                       "capsule, so keep it private.",
        "rk_body_show": "This key opens “{name}” without the password. Keep it private.",
        "rk_stored": "I have stored the recovery key somewhere safe",
        "rk_confirm": "To confirm, type the last 8 characters of the key",
        "rk_wrong": "That does not match the end of the key.",
        "rk_saved_to": "Saved to {path}",
        "rk_file_note": "Maze Capsule recovery key — keep this file private.\n"
                        "Capsule: {name}\nCreated: {date}\n\n{recovery_key}\n\n"
                        "To open the capsule with it:\n"
                        "  gocryptfs -masterkey=stdin <capsule>/vault <mount point>\n",
        "rk_later_title": "Skip saving the recovery key?",
        "rk_later_body": "Without it, a forgotten password means the files in this capsule are "
                         "gone for good. You can save it later from the capsule's menu.",
        "rk_later_btn": "Save it later",
        # unlock
        "unlock_title": "Unlock “{name}”",
        "unlock_ro": "Read-only — nothing can be changed or added",
        "unlock_forgot": "Forgot the password? Use the recovery key",
        "unlock_use_pw": "Use the password instead",
        "unlocking": "Unlocking…",
        "autolock_off": "Off",
        "autolock_m": "After {n} minutes idle",
        "autolock_h": "After {n} hour idle",
        "autolock_hs": "After {n} hours idle",
        "after_rk_title": "Set a new password?",
        "after_rk_body": "“{name}” is open with its recovery key. Set a new password now so you "
                         "can unlock it normally next time.",
        "after_rk_btn": "Set new password",
        "after_rk_later": "Not now",
        # password prompt
        "ask_pw_title": "Password for “{name}”",
        "ask_pw_recovery": "Enter the password to show the recovery key.",
        "ask_pw_check": "Enter the password to check every file in the capsule.",
        "checking": "Checking every file…",
        "verifying": "Checking…",
        # change password
        "cp_title": "Change password",
        "cp_body": "The files are not re-encrypted; only the key that unlocks them is sealed "
                   "again under the new password. The recovery key stays the same.",
        "cp_use_rk": "I forgot the current password — use the recovery key",
        "cp_working": "Changing the password and verifying it…",
        "cp_done": "Password changed and verified for “{name}”.",
        # rename
        "rn_title": "Rename capsule",
        # integrity
        "ck_ok_title": "Every file is intact",
        "ck_ok_body": "All files and folders in “{name}” were decrypted and authenticated. "
                      "Nothing was changed.",
        "ck_bad_title": "Damaged files found",
        "ck_bad_body": "Some encrypted files in “{name}” failed authentication — a disk error "
                       "or something outside Maze Capsule changed them. Nothing was changed or "
                       "removed. Copy your intact files out and restore the damaged ones from a backup.",
        # delete / trash
        "del_title": "Move “{name}” to the trash?",
        "del_body": "The capsule is moved to Maze Capsule's trash, still encrypted. Nothing is "
                    "deleted: you can restore it at any time.",
        "del_btn": "Move to trash",
        "forget_title": "Remove “{name}” from the list?",
        "forget_body": "The capsule's folder stays where it is ({path}) and nothing is deleted. "
                       "You can add it again with “Add existing”.",
        "forget_btn": "Remove from list",
        "purge_title": "Delete “{name}” forever?",
        "purge_body": "This permanently deletes the capsule and every file inside it. It cannot "
                      "be undone, and the recovery key will not help.",
        "purge_type": "Type the capsule's name to confirm",
        "purge_btn": "Delete forever",
        # export / import
        "exp_title": "Export backup",
        "exp_working": "Writing the backup…",
        "exp_done": "Backup saved: {path}. It is still encrypted — the same password and "
                    "recovery key open it.",
        "exp_filter": "Capsule backup (*.capsule.tar)",
        "imp_done": "Imported “{name}”.",
        "link_done": "Added “{name}”.",
        "imp_filter": "Capsule backup (*.capsule.tar);;All files (*)",
        # copy
        "cp_in_title": "Copying into “{name}”",
        "cp_in_file": "{name}",
        "cp_in_done": "Copied {files} files ({size}) into “{name}”. The originals were left "
                      "where they were.",
        "cp_in_errors": "{n} items could not be copied: {first}",
        "cp_in_cancelled": "Copy cancelled. Files that were fully copied stay in the capsule; "
                           "nothing else was changed.",
        "pick_files": "Add files to “{name}”",
        "pick_folder": "Add a folder to “{name}”",
        # sandbox
        "sb_opened": "Sandbox shell opened: only “{name}” is visible, {net}.",
        "sb_net_off": "no network",
        "sb_net_on": "network allowed",
        "sb_missing": "The sandbox needs bubblewrap (bwrap) and a terminal.",
        # lock
        "locked_msg": "“{name}” is locked.",
        "unlocked_msg": "“{name}” is unlocked.",
        "busy_title": "“{name}” is still in use",
        "busy_body": "A program still has files open inside the capsule. Close it and try "
                     "again — or lock the capsule as soon as those files are closed. Locking "
                     "never interrupts a write in progress.",
        "busy_lazy": "Lock when closed",
        # quit
        "quit_title": "Capsules are still unlocked",
        "quit_body": "{n} capsule(s) are unlocked. Unlocked capsules stay open after Maze Capsule "
                     "closes, until you lock them or log out.",
        "quit_lock": "Lock all and quit",
        "quit_keep": "Keep unlocked",
        "quit_fail": "Some capsules could not be locked because files are open: {names}",
        # settings
        "st_title": "Settings",
        "st_language": "LANGUAGE",
        "st_autolock": "DEFAULT AUTO-LOCK",
        "st_autolock_note": "Locks an unlocked capsule after it has not been used for a while.",
        "st_sandbox": "SANDBOX SHELL",
        "st_sandbox_net": "Allow network access inside the sandbox",
        "st_about": "Maze Capsule {ver} · gocryptfs {gv}",
        # status
        "status_ready": "{n} capsules · {u} unlocked",
        "no_gocryptfs": "gocryptfs is not installed — Maze Capsule cannot open or create capsules.",
        # errors
        "e_wrong_password": "Wrong password.",
        "e_bad_master_key": "That is not a valid recovery key (64 hexadecimal characters).",
        "e_empty_password": "Enter a password.",
        "e_bad_character": "Passwords cannot contain line breaks.",
        "e_too_long": "That password is too long.",
        "e_busy": "Files inside the capsule are still open.",
        "e_unlocked": "Lock the capsule first.",
        "e_unavailable": "The capsule's folder is not available.",
        "e_config": "The capsule's key file is damaged and no intact copy was found. "
                    "Unlock with the recovery key.",
        "e_corrupt": "Damaged files were found.",
        "e_no_gocryptfs": "gocryptfs is not installed.",
        "e_in_progress": "Another operation on this capsule is still running.",
        "e_name_empty": "Enter a name.",
        "e_name_long": "The name is too long (64 characters at most).",
        "e_name_chars": "The name cannot contain / or \\.",
        "e_exists": "Something with that name already exists there.",
        "e_not_a_capsule": "That folder is not a capsule or a gocryptfs folder.",
        "e_already_listed": "That capsule is already in the list.",
        "e_bad_backup": "That file is not a Maze Capsule backup.",
        "e_backup_verify": "The backup could not be verified after writing; it was not kept.",
        "e_bare_export": "Plain gocryptfs folders cannot be exported; copy the folder instead.",
        "e_no_folder": "That folder does not exist.",
        "e_not_writable": "You cannot write to that folder.",
        "e_timeout": "gocryptfs did not respond in time.",
        "e_fuse": "FUSE is not available, so capsules cannot be opened.",
        "e_mountpoint": "The place to open the capsule is not usable.",
        "e_verify_failed": "The new password could not be verified; the old one was kept.",
        "e_missing": "A required program is missing.",
        "e_not_in_trash": "Only capsules in the trash can be deleted.",
        "e_not_found": "That capsule no longer exists.",
        "e_failed": "Something went wrong.",
        "e_unmount": "The capsule could not be locked.",
    },
    "tr": {
        "bug_body": "Bu bir hataydı, senin yaptığın bir şey değil. Hiçbir şey silinmedi; ayrıntılar sistem günlüğünde.",
        "tip_minimize": "Küçült",
        "tip_maximize": "Büyüt / Geri al",
        "tip_close": "Kapat",
        "tip_settings": "Ayarlar",
        "tip_language": "Dil",
        "eyebrow": "ŞİFRELİ ALANLAR",
        "hero_title": "Dosyaların,\nkapsüllerde mühürlü.",
        "hero_sub": "Her kapsül ayrı bir şifreli alandır. Dosyalarını ve klasörlerini içine koy, "
                    "kilitle; şifren olmadan bu sistemdeki hiçbir şey onları okuyamaz.",
        "point_1": "AES-256-GCM şifreleme — dosya adları ve klasör yapısı dahil",
        "point_2": "Her kapsül, gocryptfs olan her Linux'ta açılan tek ve taşınabilir bir klasördür",
        "point_3": "Root yok, bulut yok, telemetri yok — ve kurtarma anahtarı sayesinde unutulan şifre, kaybolan veri demek değil",
        "btn_new": "Yeni kapsül",
        "btn_add_existing": "Mevcut olanı ekle",
        "menu_import": "Yedeği içe aktar (.capsule.tar)…",
        "menu_link": "Kapsül klasörü ekle (USB disk, başka bir sürücü)…",
        "menu_link_bare": "Düz bir gocryptfs klasörü ekle…",
        "sec_capsules": "KAPSÜLLERİN",
        "tb_capsules": "Kapsüller",
        "btn_trash": "Çöp kutusu",
        "drawer_hint": "Silinen kapsüller, kalıcı olarak kaldırana kadar burada şifreli olarak durur.",
        "trash_empty": "Çöp kutusu boş.",
        "sec_trash": "ÇÖP KUTUSU",
        "btn_lock_all": "Hepsini kilitle",
        "empty_title": "Henüz kapsül yok",
        "empty_body": "İlk kapsülünü oluştur — bir isim ve bir şifre yeterli.",
        "pill_locked": "KİLİTLİ",
        "pill_unlocked": "AÇIK",
        "pill_ro": "SALT OKUNUR",
        "pill_offline": "BAĞLI DEĞİL",
        "created": "Oluşturuldu: {date}",
        "size": "{size} şifreli",
        "size_pending": "ölçülüyor…",
        "loc_default": "Maze Capsule içinde saklanıyor",
        "loc_linked": "Konum: {path}",
        "loc_offline": "Klasör bulunamadı: {path} — diski tak veya konumu kontrol et.",
        "mounted_at": "Açık konum: {path}",
        "no_recovery": "Kurtarma anahtarı henüz kaydedilmedi",
        "btn_save_now": "Şimdi kaydet",
        "drop_hint": "İçine kopyalamak için dosyaları buraya bırak",
        "btn_unlock": "Kilidi aç",
        "btn_open": "Aç",
        "btn_add_files": "Dosya ekle",
        "btn_add_folder": "Klasör ekle",
        "btn_shell": "Sandbox",
        "btn_lock": "Kilitle",
        "tip_more": "Diğer",
        "low_space": "Bu diskte yalnızca {free} boş alan var",
        "m_rename": "Yeniden adlandır…",
        "m_password": "Şifreyi değiştir…",
        "m_recovery": "Kurtarma anahtarını göster…",
        "m_check": "Bütünlüğü denetle…",
        "m_export": "Yedek dışa aktar…",
        "m_location": "Kapsül klasörünü göster",
        "m_delete": "Çöp kutusuna taşı…",
        "m_forget": "Listeden kaldır…",
        "m_lock_force": "Dosyalar kapanınca kilitle",
        "trash_row": "Silinme: {date}",
        "btn_restore": "Geri yükle",
        "btn_purge": "Kalıcı olarak sil…",
        "btn_cancel": "Vazgeç",
        "btn_close": "Kapat",
        "btn_done": "Tamam",
        "btn_create": "Kapsülü oluştur",
        "btn_save": "Kaydet",
        "btn_continue": "Devam",
        "btn_copy": "Kopyala",
        "btn_copied": "Kopyalandı",
        "btn_save_file": "Dosyaya kaydet…",
        "f_name": "İSİM",
        "f_password": "ŞİFRE",
        "f_confirm": "ŞİFRE TEKRAR",
        "f_current": "MEVCUT ŞİFRE",
        "f_new": "YENİ ŞİFRE",
        "f_location": "KONUM",
        "f_recovery": "KURTARMA ANAHTARI",
        "f_autolock": "OTOMATİK KİLİT",
        "show_pw": "Göster",
        "hide_pw": "Gizle",
        "ph_name": "örn. Belgeler, Fotoğraflar, İş",
        "ph_recovery": "xxxxxxxx-xxxxxxxx-… (64 karakter)",
        "loc_default_opt": "Maze Capsule klasörü (önerilen)",
        "loc_custom_opt": "Benim seçtiğim bir klasör — USB disk, başka bir sürücü…",
        "loc_choose": "Klasör seç…",
        "loc_none": "Klasör seçilmedi",
        "name_visible": "Kapsülün adı bu bilgisayarda görünür. İçeriği, dosya adları ve klasör "
                        "yapısı şifrelidir.",
        "strength_0": "Çok kısa — en az {n} karakter",
        "strength_1": "Zayıf",
        "strength_2": "Orta",
        "strength_3": "İyi",
        "strength_4": "Güçlü",
        "pw_mismatch": "Şifreler aynı değil.",
        "pw_hint": "Birkaç kelimeden oluşan bir parola kullan. Bir kapsül, şifresi veya kurtarma "
                   "anahtarı olmadan okunamaz — Maze Linux için bile.",
        "new_title": "Yeni kapsül",
        "creating": "Kapsül oluşturuluyor ve anahtarı mühürleniyor…",
        "rk_title": "Kurtarma anahtarın",
        "rk_body_new": "Şifreyi unutursan “{name}” kapsülüne geri dönmenin tek yolu bu anahtar. "
                       "Bir yere yaz veya bu bilgisayarın dışında sakla — bir parola yöneticisi, "
                       "kâğıt, bir USB bellek. Bu anahtara sahip olan herkes kapsülü açabilir; "
                       "gizli tut.",
        "rk_body_show": "Bu anahtar “{name}” kapsülünü şifre olmadan açar. Gizli tut.",
        "rk_stored": "Kurtarma anahtarını güvenli bir yerde sakladım",
        "rk_confirm": "Onaylamak için anahtarın son 8 karakterini yaz",
        "rk_wrong": "Bu, anahtarın sonuyla eşleşmiyor.",
        "rk_saved_to": "Kaydedildi: {path}",
        "rk_file_note": "Maze Capsule kurtarma anahtarı — bu dosyayı gizli tut.\n"
                        "Kapsül: {name}\nOluşturuldu: {date}\n\n{recovery_key}\n\n"
                        "Kapsülü bu anahtarla açmak için:\n"
                        "  gocryptfs -masterkey=stdin <kapsül>/vault <bağlama noktası>\n",
        "rk_later_title": "Kurtarma anahtarı kaydedilmeden geçilsin mi?",
        "rk_later_body": "Anahtar olmadan, unutulan bir şifre bu kapsüldeki dosyaların sonsuza dek "
                         "kaybolması demektir. Daha sonra kapsülün menüsünden kaydedebilirsin.",
        "rk_later_btn": "Sonra kaydet",
        "unlock_title": "“{name}” kilidini aç",
        "unlock_ro": "Salt okunur — hiçbir şey değiştirilemez veya eklenemez",
        "unlock_forgot": "Şifreyi mi unuttun? Kurtarma anahtarını kullan",
        "unlock_use_pw": "Bunun yerine şifreyi kullan",
        "unlocking": "Kilit açılıyor…",
        "autolock_off": "Kapalı",
        "autolock_m": "{n} dakika kullanılmazsa",
        "autolock_h": "{n} saat kullanılmazsa",
        "autolock_hs": "{n} saat kullanılmazsa",
        "after_rk_title": "Yeni bir şifre belirlensin mi?",
        "after_rk_body": "“{name}” kurtarma anahtarıyla açıldı. Bir dahaki sefere normal şekilde "
                         "açabilmek için şimdi yeni bir şifre belirle.",
        "after_rk_btn": "Yeni şifre belirle",
        "after_rk_later": "Şimdi değil",
        "ask_pw_title": "“{name}” şifresi",
        "ask_pw_recovery": "Kurtarma anahtarını görmek için şifreyi gir.",
        "ask_pw_check": "Kapsüldeki her dosyayı denetlemek için şifreyi gir.",
        "checking": "Her dosya denetleniyor…",
        "verifying": "Kontrol ediliyor…",
        "cp_title": "Şifreyi değiştir",
        "cp_body": "Dosyalar yeniden şifrelenmez; yalnızca onları açan anahtar yeni şifreyle "
                   "yeniden mühürlenir. Kurtarma anahtarı aynı kalır.",
        "cp_use_rk": "Mevcut şifreyi unuttum — kurtarma anahtarını kullan",
        "cp_working": "Şifre değiştiriliyor ve doğrulanıyor…",
        "cp_done": "“{name}” için şifre değiştirildi ve doğrulandı.",
        "rn_title": "Kapsülü yeniden adlandır",
        "ck_ok_title": "Tüm dosyalar sağlam",
        "ck_ok_body": "“{name}” içindeki tüm dosya ve klasörler çözüldü ve doğrulandı. Hiçbir şey "
                      "değiştirilmedi.",
        "ck_bad_title": "Hasarlı dosyalar bulundu",
        "ck_bad_body": "“{name}” içindeki bazı şifreli dosyalar doğrulanamadı — bir disk hatası "
                       "veya Maze Capsule dışından bir şey onları değiştirmiş. Hiçbir şey "
                       "değiştirilmedi veya silinmedi. Sağlam dosyalarını dışarı kopyala, hasarlı "
                       "olanları yedekten geri yükle.",
        "del_title": "“{name}” çöp kutusuna taşınsın mı?",
        "del_body": "Kapsül, şifreli hâliyle Maze Capsule'ün çöp kutusuna taşınır. Hiçbir şey "
                    "silinmez: istediğin zaman geri yükleyebilirsin.",
        "del_btn": "Çöp kutusuna taşı",
        "forget_title": "“{name}” listeden kaldırılsın mı?",
        "forget_body": "Kapsülün klasörü olduğu yerde kalır ({path}) ve hiçbir şey silinmez. "
                       "“Mevcut olanı ekle” ile yeniden ekleyebilirsin.",
        "forget_btn": "Listeden kaldır",
        "purge_title": "“{name}” kalıcı olarak silinsin mi?",
        "purge_body": "Bu, kapsülü ve içindeki her dosyayı kalıcı olarak siler. Geri alınamaz ve "
                      "kurtarma anahtarı da işe yaramaz.",
        "purge_type": "Onaylamak için kapsülün adını yaz",
        "purge_btn": "Kalıcı olarak sil",
        "exp_title": "Yedek dışa aktar",
        "exp_working": "Yedek yazılıyor…",
        "exp_done": "Yedek kaydedildi: {path}. Hâlâ şifreli — aynı şifre ve kurtarma anahtarı "
                    "onu açar.",
        "exp_filter": "Kapsül yedeği (*.capsule.tar)",
        "imp_done": "“{name}” içe aktarıldı.",
        "link_done": "“{name}” eklendi.",
        "imp_filter": "Kapsül yedeği (*.capsule.tar);;Tüm dosyalar (*)",
        "cp_in_title": "“{name}” içine kopyalanıyor",
        "cp_in_file": "{name}",
        "cp_in_done": "{files} dosya ({size}) “{name}” içine kopyalandı. Asıl dosyalar olduğu "
                      "yerde bırakıldı.",
        "cp_in_errors": "{n} öğe kopyalanamadı: {first}",
        "cp_in_cancelled": "Kopyalama iptal edildi. Tamamen kopyalanan dosyalar kapsülde kalır; "
                           "başka hiçbir şey değişmedi.",
        "pick_files": "“{name}” içine dosya ekle",
        "pick_folder": "“{name}” içine klasör ekle",
        "sb_opened": "Sandbox kabuğu açıldı: yalnızca “{name}” görünür, {net}.",
        "sb_net_off": "ağ erişimi yok",
        "sb_net_on": "ağ erişimi açık",
        "sb_missing": "Sandbox için bubblewrap (bwrap) ve bir terminal gerekiyor.",
        "locked_msg": "“{name}” kilitlendi.",
        "unlocked_msg": "“{name}” kilidi açıldı.",
        "busy_title": "“{name}” hâlâ kullanımda",
        "busy_body": "Bir program kapsül içindeki dosyaları hâlâ açık tutuyor. Onu kapatıp tekrar "
                     "dene — ya da dosyalar kapanır kapanmaz kapsülü kilitle. Kilitleme, süren bir "
                     "yazma işlemini asla yarıda kesmez.",
        "busy_lazy": "Kapanınca kilitle",
        "quit_title": "Açık kapsüller var",
        "quit_body": "{n} kapsül açık. Açık kapsüller, sen kilitleyene veya oturumu kapatana "
                     "kadar Maze Capsule kapandıktan sonra da açık kalır.",
        "quit_lock": "Hepsini kilitle ve çık",
        "quit_keep": "Açık bırak",
        "quit_fail": "Bazı kapsüller açık dosyalar yüzünden kilitlenemedi: {names}",
        "st_title": "Ayarlar",
        "st_language": "DİL",
        "st_autolock": "VARSAYILAN OTOMATİK KİLİT",
        "st_autolock_note": "Açık bir kapsül bir süre kullanılmazsa onu kilitler.",
        "st_sandbox": "SANDBOX KABUĞU",
        "st_sandbox_net": "Sandbox içinde ağ erişimine izin ver",
        "st_about": "Maze Capsule {ver} · gocryptfs {gv}",
        "status_ready": "{n} kapsül · {u} açık",
        "no_gocryptfs": "gocryptfs kurulu değil — Maze Capsule kapsül açamaz veya oluşturamaz.",
        "e_wrong_password": "Şifre yanlış.",
        "e_bad_master_key": "Bu geçerli bir kurtarma anahtarı değil (64 onaltılık karakter).",
        "e_empty_password": "Bir şifre gir.",
        "e_bad_character": "Şifre satır sonu içeremez.",
        "e_too_long": "Bu şifre çok uzun.",
        "e_busy": "Kapsül içindeki dosyalar hâlâ açık.",
        "e_unlocked": "Önce kapsülü kilitle.",
        "e_unavailable": "Kapsülün klasörüne erişilemiyor.",
        "e_config": "Kapsülün anahtar dosyası hasarlı ve sağlam bir kopyası bulunamadı. "
                    "Kurtarma anahtarıyla aç.",
        "e_corrupt": "Hasarlı dosyalar bulundu.",
        "e_no_gocryptfs": "gocryptfs kurulu değil.",
        "e_in_progress": "Bu kapsülde başka bir işlem hâlâ sürüyor.",
        "e_name_empty": "Bir isim gir.",
        "e_name_long": "İsim çok uzun (en fazla 64 karakter).",
        "e_name_chars": "İsim / veya \\ içeremez.",
        "e_exists": "Orada bu isimde bir şey zaten var.",
        "e_not_a_capsule": "Bu klasör bir kapsül veya gocryptfs klasörü değil.",
        "e_already_listed": "Bu kapsül zaten listede.",
        "e_bad_backup": "Bu dosya bir Maze Capsule yedeği değil.",
        "e_backup_verify": "Yedek yazıldıktan sonra doğrulanamadı; saklanmadı.",
        "e_bare_export": "Düz gocryptfs klasörleri dışa aktarılamaz; klasörü kopyala.",
        "e_no_folder": "Bu klasör yok.",
        "e_not_writable": "Bu klasöre yazma iznin yok.",
        "e_timeout": "gocryptfs zamanında yanıt vermedi.",
        "e_fuse": "FUSE kullanılamıyor, bu yüzden kapsüller açılamıyor.",
        "e_mountpoint": "Kapsülün açılacağı yer kullanılamıyor.",
        "e_verify_failed": "Yeni şifre doğrulanamadı; eski şifre korundu.",
        "e_missing": "Gerekli bir program eksik.",
        "e_not_in_trash": "Yalnızca çöp kutusundaki kapsüller silinebilir.",
        "e_not_found": "Bu kapsül artık yok.",
        "e_failed": "Bir şeyler ters gitti.",
        "e_unmount": "Kapsül kilitlenemedi.",
    },
}

_lang = "en"


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in STRINGS else "en"


def language() -> str:
    return _lang


def t(key: str, /, **kw) -> str:
    text = STRINGS.get(_lang, {}).get(key) or STRINGS["en"].get(key) or key
    return text.format(**kw) if kw else text


def err(exc: BaseException) -> str:
    """A user-facing message for a CapsuleError / GocryptError / OSError."""
    reason = getattr(exc, "reason", None)
    if reason:
        text = t(f"e_{reason}")
        if text == f"e_{reason}":
            text = t("e_failed")
        detail = getattr(exc, "detail", "")
        if reason in ("failed", "unmount", "missing", "fuse", "mountpoint") and detail:
            text += f" ({detail.splitlines()[-1][:160]})"
        return text
    if isinstance(exc, OSError):
        return f"{t('e_failed')} ({exc.strerror or exc})"
    return f"{t('e_failed')} ({exc})"


def human_size(n: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    f = float(n)
    for u in units:
        if f < 1000 or u == units[-1]:
            return f"{f:.0f} {u}" if u == "B" else f"{f:.1f} {u}"
        f /= 1000
    return f"{n} B"
