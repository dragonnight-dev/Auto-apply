# Auto Apply

Opens a job application page in several people's browsers at once and fills each form from that
person's own profile and resume, using a small language model running on your machine.

- **`extension/`**: Chrome extension installed on each client PC. Signs up or in, opens pages, reads
  the form, fills it, and uploads the resume.
- **`backend/`**: Django and Channels server. Extracts profiles, creates the fill data with the local
  model, runs the workflow, and stores history.
- **`frontend/`**: React console for the boss. Shows client state, syncs URLs, sends fill data, and
  manages history.

All live communication uses WebSockets, so the server can push to any client at any time.

## Run the server

You need [Ollama](https://ollama.com), Python 3.12 and Node 20. Without a supported GPU, Ollama runs the
model on the CPU, which is much slower.

```powershell
copy .env.example .env     # then replace the values
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

- The script installs dependencies, builds the console, starts Ollama, downloads the model (about 4.7 GB)
  on the first run, and starts the server.
- In `.env`, add this machine's LAN address to `ALLOWED_HOSTS`, or other PCs will get a 400 error.
- The console is at `http://localhost:8000`. Choose **Create an account with a boss key** and enter the
  `BOSS_KEY` from `.env`.
- Other PCs must be able to reach port 8000, so allow it through this machine's firewall.
- Data is stored in `backend/dev.sqlite3`, and resumes in `backend/DB/[email].pdf`. To use PostgreSQL
  instead, set the `POSTGRES_*` values in `.env`.
- After changing the console's code, delete `frontend/dist` so the script rebuilds it.

## Install the extension on a client PC

1. Copy the `extension/` folder to the PC. Chrome 116 or newer is required.
2. Open `chrome://extensions`, turn on **Developer mode**, choose **Load unpacked**, and select the folder.
3. Open the extension, enter the server address (`http://<server LAN address>:8000`), and sign up with a
   PDF resume. The client then appears in the console.

## Apply to a job

1. A client opens a job page. Its URL appears in the console.
2. Hover over that row and choose **Sync URL**. Every enabled, connected client opens the page in a
   dedicated tab, and one of them sends the form back to the server.
3. Wait for **Fill data is ready to send**, then choose **Fill data**.
4. Each client's results appear in the console and are saved to its history.

## What it will and won't fill

| Field | Behaviour |
| --- | --- |
| Name, email, phone, links, location | Filled from the profile by exact rules |
| Other short fields, dropdowns, radios | Answered by the model; the answer must match a real option or use only words from the profile |
| Open questions | Written by the model from the profile and job text, or left blank if it can't answer |
| Gender, race, veteran, disability, birth date, ID and bank details | Never filled |
| Terms and consent boxes, signatures | Never ticked: these need the applicant |
| Password and hidden inputs | Never read or filled |

Skipped fields are listed in the console with the reason. A history result of `filled` means every planned
field was set. It does not mean an application was submitted.

**Submitting:** forms are left for a person to review. Set `AUTO_CLICK_SUBMIT=true` to click the submit
button automatically. Applications then go out with no review, including any wrong model answers.

**Tailored resumes:** the model rewrites the resume for each job, and the rewrite is uploaded in place of the
original. It is discarded if it is too short or contains a number the original doesn't. That check can't
catch every invented claim, such as an added skill. Set `TAILOR_RESUME=false` to always upload the original.

**Hidden instructions:** a job page can contain text aimed at AI models. Short answers never see the page
text. Open answers do, so instruction-like sentences are removed first, but that can't catch every wording.
Review open answers before submitting, which is another reason `AUTO_CLICK_SUBMIT` is off by default.

## Configuration

Set these in `.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY`, `BOSS_KEY` | required | Secrets |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Addresses the server answers on |
| `SLM_MODEL` | `qwen2.5:7b` | Any Ollama model that supports tools |
| `SLM_NUM_CTX` | `8192` | Model context size in tokens; lower it if the GPU runs out of memory |
| `TAILOR_RESUME` | `true` | Rewrite the resume for each job |
| `AUTO_CLICK_SUBMIT` | `false` | Click submit after filling |
| `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | unset | Use PostgreSQL instead of SQLite |

## Limitations

- **Traffic is not encrypted.** Passwords and resumes cross the network over plain HTTP, so use this only on
  a network you trust, or put an HTTPS proxy in front of port 8000.
- **Sign-in has no rate limiting.** Don't expose the port to the internet.
- **Main page only.** Forms inside iframes are not detected, and some hosted application systems embed
  their forms that way.
- **One step at a time.** On a multi-step form, sync captures the first step only.
- **CAPTCHAs and logins** are left to the person at that browser.
- **English only**, as designed.
- **Site rules.** Some job sites prohibit automated applications in their terms, so check before using it.

## Tests

```sh
cd backend && python manage.py test     # uses SQLite and a fake model
cd extension && npm install && npm test
cd frontend && npm install && npm test
```
