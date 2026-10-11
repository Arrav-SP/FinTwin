# Putting FinTwin online

This guide publishes FinTwin as a free public website on **Render**, with **Neon** keeping the data and **GitHub** handling sign-in. Allow about 45 minutes the first time. Free-tier terms change; check each provider's pricing page before you start.

## What the site does

| Who | Can do |
|---|---|
| Anyone | Read the 278 recorded reference runs, the models and their accuracy; use Predict and What if |
| Signed in with GitHub | Also run a workload or a validation: up to 8 workers, 20 TPS and 8 seconds, 10 runs a day, one run at a time for the whole site |

- **Runs are private.** A person sees the reference runs and their own runs. Someone else's run, its latency, advisor findings and validations answer "not found", exactly as if they did not exist.
- **Models learn from everyone.** Once 60 runs have been made on the site, it retrains itself on site runs only, and again after every 25 more. Until then it shows the laptop-trained models with a notice that they describe another machine.
- **No password is stored.** GitHub confirms who a person is. The site keeps only their GitHub login name, shows it to nobody, and uses it to decide which runs are theirs.
- **People can delete their runs** with "Delete my runs" in the footer. Models already trained keep what they learned in aggregate.

## Why three services

- **Render** runs the container (PostgreSQL, API and interface together). Its free tier gives 512 MB and a fraction of a CPU, sleeps after 15 idle minutes, and **wipes the container's disk on every restart**.
- **Neon** is a free PostgreSQL database that does not expire. FinTwin copies each finished run, each person's allowance and each retrained model to it, and copies them back when the site wakes. Without Neon the site still works, but visitors' runs vanish at every sleep and there is nothing lasting to train on.
- **GitHub** provides sign-in.

## What to expect from free hardware

Measured on 2026-10-11 by running the image under the same limits (512 MB, 0.1 CPU):

- The whole site delivers about **8 TPS**. A run asking for more saturates, which is why the caps are low. Saturated runs can take a minute or more.
- A page of data loads in well under a second. After a restart, the first prediction is quick only once a background warm-up has finished (under a minute).
- Retraining takes a few minutes and makes the site sluggish while it runs. It goes through the same queue as runs, so it never overlaps a measurement.
- After sleeping, the site takes up to a minute to answer the first visitor.

## Step 1: try it on your own machine (optional, recommended)

From the project root, with Docker running:

```powershell
docker build -f deploy/public/Dockerfile -t fintwin-public .
docker run --rm -p 127.0.0.1:7860:7860 -e PORT=7860 -e FINTWIN_BASE_URL=http://127.0.0.1:7860 -e FINTWIN_DEV_LOGIN=tester fintwin-public
```

Open `http://127.0.0.1:7860/`. Click **Sign in**: because the address is local and `FINTWIN_DEV_LOGIN` is set, you are signed in as "tester" without GitHub. That stand-in is ignored on any address that is not local, so it cannot be used on the real site. No archive is configured in this trial, so your runs last until you stop the container.

## Step 2: commit and push the code to GitHub

Render builds from your GitHub repository, so the public-site code must be there. Commit and push as you normally do. The repository must contain `render.yaml`, `deploy/public/`, `bundled/` and the rest of the project.

## Step 3: create the Neon database

1. Sign up at `https://neon.com` and create a project (any name, any region near you; PostgreSQL 16 or later).
2. On the project dashboard click **Connect** and copy the connection string. It looks like `postgresql://user:password@ep-something.region.aws.neon.tech/neondb?sslmode=require`.
3. Keep it private: it contains the database password. You will paste it into Render in step 5.

You do not create any tables. FinTwin creates them the first time it connects.

## Step 4: create the Render service

1. Sign up at `https://render.com` and connect your GitHub account.
2. Choose **New → Blueprint**, pick the FinTwin repository, and confirm. Render reads `render.yaml` and proposes one free web service named `fintwin`.
3. Render asks for four values. Leave them blank for now if it lets you, or enter placeholders; you will fill them in step 5. Create the service.
4. Note the address Render gives the service, for example `https://fintwin-abcd.onrender.com`. This is the site's address.

The first build takes several minutes.

## Step 5: create the GitHub sign-in app

1. On GitHub open **Settings → Developer settings → OAuth Apps → New OAuth App** (`https://github.com/settings/developers`).
2. Fill in:
   - Application name: `FinTwin`
   - Homepage URL: your Render address, for example `https://fintwin-abcd.onrender.com`
   - Authorization callback URL: the same address followed by `/api/auth/callback`
3. Register it and copy the **Client ID**.
4. Click **Generate a new client secret** and copy it. GitHub shows it once.

The app asks for no permissions. It can only learn the public login name of a person who approves it.

## Step 6: give Render its settings

In the Render dashboard open the service, then **Environment**, and set:

| Name | Value |
|---|---|
| `FINTWIN_BASE_URL` | your Render address, no trailing slash |
| `GITHUB_CLIENT_ID` | the Client ID from step 5 |
| `GITHUB_CLIENT_SECRET` | the client secret from step 5 |
| `FINTWIN_ARCHIVE_URL` | the Neon connection string from step 3 |

`FINTWIN_PUBLIC` and `FINTWIN_SESSION_SECRET` are set by the blueprint; leave them. Save, and let Render redeploy.

Never put these values in the repository, a chat message or a screenshot.

## Step 7: check it

1. Open the site. The Overview shows the reference runs; the footer says it is a public demonstration.
2. Open **Run**. It asks you to sign in.
3. Click **Sign in with GitHub**, approve, and you return signed in, with your login in the header.
4. Start a small run. It finishes and shows as "yours" under **Experiments**.
5. In a private browser window (not signed in), open the address of that run. It should say the run could not be found.
6. In Render, use **Manual Deploy → Restart** (this wipes the disk), reopen the site and sign in. Your run should still be there. That confirms the Neon archive works.
7. Open **Models**. It should say the models were trained on another machine and show how many site runs have been collected.

## Day-to-day

- **Updating the site:** push to GitHub; Render redeploys. Site runs and site-trained models come back from Neon.
- **When retraining happens:** automatically, at 60 site runs and after every 25 more. The Models page then says the models describe this server.
- **Seeing how full Neon is:** the Neon dashboard shows storage. FinTwin stops accepting runs at 20,000 archived runs, well inside the free 1 GB.

## Changing the limits

| What | Where |
|---|---|
| Workers, rate, duration per run; runs per day; how many may wait; predictions per minute | constants at the top of `backend/app/access.py` |
| Site runs needed before the first retraining, and between retrainings | environment variables `FINTWIN_SITE_MIN_RUNS` (60) and `FINTWIN_RETRAIN_EVERY` (25) |
| Maximum archived runs | `MAX_ARCHIVED_RUNS` in `backend/app/archive.py` |

If you move to a larger paid instance, raise the caps and rerun the measurement before trusting higher rates.

## Removing someone's data yourself

People can do this themselves with "Delete my runs". To do it for them, run this in the Neon SQL editor, replacing the login, then restart the Render service:

```sql
DELETE FROM validation_experiments WHERE started_by = 'their-login';
DELETE FROM experiment_runs WHERE started_by = 'their-login';
DELETE FROM usage_log WHERE login = 'their-login';
```

To sign everyone out, change `FINTWIN_SESSION_SECRET` in Render.

## If something goes wrong

| Symptom | Cause and fix |
|---|---|
| "Sign-in is not configured on this server" | `FINTWIN_BASE_URL`, `GITHUB_CLIENT_ID` or `GITHUB_CLIENT_SECRET` is missing in Render |
| GitHub says the redirect URI does not match | The callback URL in the GitHub app must be exactly `FINTWIN_BASE_URL` plus `/api/auth/callback` |
| "This sign-in link is not valid any more" | The sign-in was started more than ten minutes ago or in another browser. Start again from the site |
| Runs disappear after the site sleeps | `FINTWIN_ARCHIVE_URL` is missing or wrong. Check the Render logs for "Archive" messages |
| The site is slow to open | It was asleep. Free services sleep after 15 idle minutes |
| A run takes much longer than its duration | The host is saturated; that is a real result on this hardware |
| Render reports the service ran out of memory | Retraining is the tightest moment. Raise `FINTWIN_SITE_MIN_RUNS` to a very large number to switch automatic retraining off, and tell the developer |
| The Models page still says "trained on another machine" after 60 runs | Retraining is queued behind runs, or the site-run data does not yet cover two scenarios and several loads. It tries again after the next batch |

## What this deployment is not

- **Not a load-testing service.** The caps keep runs far below the 600 TPS at which the recorded campaign saturated a laptop; those results are shown as recorded data.
- **Not verified on the real services by the developer.** The image was built and exercised locally under Render's limits with a second PostgreSQL container standing in for Neon. The real GitHub round trip, Neon and Render themselves are first exercised by the steps above.
- **No administrator page.** Limits and deletions are done as described above.
