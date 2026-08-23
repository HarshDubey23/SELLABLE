<!-- Day 1  -->
Goal
Razorpay test account, zrok tunnel, webhook receiver end-to-end verify karna.

Built

Repo scaffold (apps/api, tests, eval, docs structure)
Webhook receiver: FastAPI + uvicorn
HMAC-SHA256 signature verification on RAW body
zrok v2 tunnel setup
Verified
 Success payment -> 4 events received (payment.authorized, order.paid,payment.captured, payment_link.paid) at 11:44 AM
 Failure payments -> payment.failed x2 (11:52 AM, 12:00 PM)
 Unsigned curl POST rejected with 400 - signature gate working
 events.log file mein saare events save ho rahe hain
 Screenshot liya (docs/notes/first-webhook-events.png)

What broke (and how I got out)

PowerShell mein "mkdir -p" kaam nahi karta (Mac/Linux command hai).Error: A positional parameter cannot be found.Fix: comma-separated syntax use kiya - "mkdir apps/api, docs/log, ..."
zrok ka naya version (v2.0.4) download hua. Purana command"zrok http 8000" chalaya to error aaya:"unknown command http for zrok".Fix: --help dekha, naya v2 syntax mila - "zrok share public 8000".
zrok download "zrok2.exe" naam se extract hua tha, isliye commandsfail ho rahi thi (file exist nahi karti thi us naam se).Fix: Rename-Item se zrok.exe kar diya.
UPI se payment try kiya (success@razorpay VPA) - payment nahi horaha tha. Search karke pata chala NPCI ne UPI Collect flow Feb 2026se deprecate kar diya hai. VPA manually daal ke ab payment nahi hota.Fix: Card flow se payment kiya. Note: VPA entry wala path khatam,ab UPI Intent flow hi hai.
<!-- Test mode mein payment ke baad ek "Demo Bank" page aata hai jo khudpoochta hai "Success ya Failure?" - manually button dabana padta hai.Failure card ka asli error code test karne ke liye bhi yahi page usehua. NOTE: Day 4 pe Playwright agent ko ye button click karna hoga,automation mein extra step. -->
Events print hote waqt event id "None" aa rahi hai - Razorpay payloadmein id ka field naam alag hai. Day 2 mein webhook update karkex-razorpay-event-id header se event id lena hai (idempotency keliye bhi zaroori hai, warna duplicate events revenue doublecount karenge).
Learned
Webhook signature RAW body pe verify hoti hai, parsed JSON pe nahi
ngrok.io Razorpay ne webhooks ke liye blacklist kiya hai - isliye zrok
Ek successful payment 4-5 events bhejta hai, aur order alag ho sakta hai
PowerShell: python3 nahi python, venv\Scripts\activate (backslash)

