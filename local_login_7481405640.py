from telethon.sync import TelegramClient

client = TelegramClient('telethon_7481405640', 33502931, '06788928efba1a505f317d277fdc1b87')
client.connect()
sent = client.send_code_request('+998932551563')
print("Kod so'raldi, hash:", sent.phone_code_hash)
code = input("Kelgan kodni kiriting: ")
try:
    client.sign_in('+998932551563', code, phone_code_hash=sent.phone_code_hash)
    print("MUVAFFAQIYATLI ULANDI!")
except Exception as e:
    if "password" in str(e).lower() or "Two-steps" in str(e):
        password = input("2FA parolni kiriting: ")
        client.sign_in(password=password)
        print("MUVAFFAQIYATLI ULANDI!")
    else:
        raise
client.disconnect()
