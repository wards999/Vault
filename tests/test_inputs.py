"""Odd values from a database or typed in: 2FA settings no code can be made with are refused (they used
to crash every time the code was shown, or the save); where site icons are looked for. No window."""
import os, sys
import helpers  # repo path; temporary folder, settings and test databases
import favicon, totp

fails = []
def ok(label, cond, extra=""):
    print(("OK   " if cond else "FAIL ") + label + ("" if cond else f"  [{extra}]"), flush=True)
    if not cond: fails.append(label)

SECRET = "JBSWY3DPEHPK3PXP"
link = lambda extra: f"otpauth://totp/Site:me?secret={SECRET}{extra}"
ok("a normal link: accepted, with a code", totp.validate(link("")) is None and len(totp.code(totp.params(link("")))[0]) == 6)
ok("SHA256, 8 digits, 60 s: accepted", totp.params(link("&algorithm=SHA256&digits=8&period=60"))
   == dict(secret=SECRET, digits=8, period=60, algorithm="SHA256"))
for extra, what in (("&period=0", "period 0"), ("&period=-30", "a negative period"),
                    ("&digits=0", "0 digits"), ("&digits=40", "40 digits"), ("&algorithm=SHA224", "SHA224")):
    ok(f"{what}: refused as invalid", totp.params(link(extra)) is None and totp.validate(link(extra)) is not None)
ok("KeePass 2's fields with period 0: no 2FA", totp.params("", {"TimeOtp-Secret-Base32": SECRET, "TimeOtp-Period": "0"}) is None)
ok("SHA224 link: no KeePass 2 fields (saving used to fail)", totp.keepass2_fields(link("&algorithm=SHA224")) == {})

for host, expected in (("accounts.google.com", ["accounts.google.com", "google.com"]),
                       ("github.com", ["github.com"]),
                       ("www.example.de", ["www.example.de"]),
                       ("bbc.co.uk", ["bbc.co.uk"]),
                       ("mail.bbc.co.uk", ["mail.bbc.co.uk", "bbc.co.uk"]),
                       ("my.abc.net.au", ["my.abc.net.au", "abc.net.au"]),
                       ("login.yahoo.co.jp", ["login.yahoo.co.jp", "yahoo.co.jp"])):
    ok(f"icons for {host}: {', '.join(expected)}", favicon.icon_hosts(host) == expected, favicon.icon_hosts(host))

print(f"--- {'ALL PASSED' if not fails else str(len(fails)) + ' FAILED'}", flush=True)
sys.stdout.flush(); os._exit(1 if fails else 0)
