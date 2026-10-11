# Putting FinTwin online

This guide publishes FinTwin as a free public website on Hugging Face Spaces. Visitors can read every recorded run and use Predict and What if. People who sign in with GitHub can run small workloads.

Everything needed is already in the repository. You create two accounts' worth of settings (a Space and a GitHub sign-in app), paste four values, and push one folder. Allow about 30 minutes the first time.

## What the public site does and does not allow

| Who | Can do |
|---|---|
| Anyone | Read all runs, models and validation results; use Predict and What if (60 predictions a minute each) |
| Signed in with GitHub | Also run a workload or a validation: up to 16 workers, 100 TPS and 10 seconds, 10 runs a day, one run at a time for the whole site |

- No password is stored. GitHub confirms who the person is; the site keeps only their GitHub login name, and shows it to nobody else.
- The site resets. A free Space has no permanent disk, so when it restarts it returns to the recorded dataset and runs made by visitors are gone.
- The models were trained on a different machine. Measurements on the Space will differ from predictions, most of all for host CPU. The site says so in its footer.
- A free Space sleeps when idle and takes a short while to wake for the next visitor.

## Step 1: test the public version on your own machine (optional but recommended)

From the project root, with Docker running:

```powershell
python scripts/build_space.py
docker build -t fintwin-space build/space
docker run --rm -p 127.0.0.1:7860:7860 -e FINTWIN_BASE_URL=http://127.0.0.1:7860 -e FINTWIN_DEV_LOGIN=tester fintwin-space
```

Open `http://127.0.0.1:7860/`. You are a visitor: the Run and Validation pages ask you to sign in. Click **Sign in**; because the address is local and `FINTWIN_DEV_LOGIN` is set, you are signed in as "tester" without GitHub. This stand-in is ignored on any address that is not local, so it cannot be used on the real site.

## Step 2: create the Space

1. Create a free account at `https://huggingface.co` if you do not have one.
2. Go to `https://huggingface.co/new-space`.
3. Name it (for example `fintwin`), choose **Docker** as the SDK and the **Blank** template, keep the free CPU hardware, set visibility to **Public**, and create it.
4. Note the two addresses. If your username is `yourname` and the Space is `fintwin`:
   - Space page: `https://huggingface.co/spaces/yourname/fintwin`
   - Direct address: `https://yourname-fintwin.hf.space` (this is the one to share, and the one used below)

## Step 3: create the GitHub sign-in app

1. On GitHub open **Settings → Developer settings → OAuth Apps → New OAuth App** (`https://github.com/settings/developers`).
2. Fill in:
   - Application name: `FinTwin`
   - Homepage URL: `https://yourname-fintwin.hf.space`
   - Authorization callback URL: `https://yourname-fintwin.hf.space/api/auth/callback`
3. Register it. Copy the **Client ID**.
4. Click **Generate a new client secret** and copy the secret. GitHub shows it only once.

The app asks for no permissions. It can only learn the public login name of a person who approves it.

## Step 4: give the Space its settings

On the Space page open **Settings → Variables and secrets** and add:

| Kind | Name | Value |
|---|---|---|
| Variable | `FINTWIN_BASE_URL` | `https://yourname-fintwin.hf.space` (no trailing slash) |
| Variable | `GITHUB_CLIENT_ID` | the Client ID from step 3 |
| Secret | `GITHUB_CLIENT_SECRET` | the client secret from step 3 |
| Secret | `FINTWIN_SESSION_SECRET` | a long random string, for example the output of `python -c "import secrets; print(secrets.token_urlsafe(48))"` |

Keep the two secrets out of the repository, chat messages and screenshots. If `FINTWIN_SESSION_SECRET` is left out the site still works, but everyone is signed out whenever it restarts.

If you skip step 3 and add only `FINTWIN_BASE_URL`, the site runs as a read-and-predict demonstration with no sign-in and no way to start a run.

## Step 5: push the code to the Space

The Space is its own Git repository, separate from the GitHub one. `scripts/build_space.py` assembles what it needs into `build/space` (which is not part of the GitHub repository).

```powershell
python scripts/build_space.py
cd build/space
git init -b main
git remote add space https://huggingface.co/spaces/yourname/fintwin
git add .
git commit -m "FinTwin public demonstration"
git push --force space main
```

When Git asks for a password, use a Hugging Face access token with write permission (create one under **Settings → Access Tokens** on Hugging Face), not your account password. `--force` is needed only the first time, to replace the placeholder files the Space was created with.

The Space page shows the build log. The first build takes several minutes. When it says **Running**, open the direct address.

## Step 6: check it

1. Open `https://yourname-fintwin.hf.space`. The Overview should show the recorded runs, and the footer should say it is a public demonstration.
2. Open **Run**. It should ask you to sign in.
3. Click **Sign in with GitHub**, approve, and you should return signed in, with your login name in the header.
4. Start a small run. It should finish and appear under **Experiments → Mine**.
5. Open **Validation** and run a check. Expect the measured CPU to differ from the prediction; that is the point of the page.

## Updating the site later

After changing code, or after retraining and refreshing `bundled/`:

```powershell
python scripts/build_space.py
cd build/space
git add -A
git commit -m "Update"
git push space main
```

`build_space.py` keeps the `.git` folder inside `build/space`, so the link to the Space survives a rebuild.

## If something goes wrong

| Symptom | Cause and fix |
|---|---|
| "Sign-in is not configured on this server" | One of `FINTWIN_BASE_URL`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` is missing. Add it and restart the Space |
| GitHub says the redirect URI does not match | The callback URL in the GitHub app must be exactly `FINTWIN_BASE_URL` plus `/api/auth/callback` |
| Signed in on the direct address but not inside the Hugging Face page | Expected. The Space page shows the site inside a frame, where browsers do not keep the sign-in cookie. Use and share the direct `hf.space` address |
| "This sign-in link is not valid any more" | The sign-in was started more than ten minutes ago or in another browser. Start again from the site |
| Push rejected for a large file | Run `python scripts/build_space.py` again and push from `build/space`, not from the project root |
| The site is slow to open | It was asleep. Free Spaces sleep when idle |

## Changing the limits

The caps and allowances are constants at the top of `backend/app/access.py`: workers, rate and duration per run, runs per day, how many runs may wait, and predictions per minute. Change them, rebuild and push.

## What this deployment is not

- It is not a load-testing service. The caps keep runs far below the 600 TPS at which the recorded campaign saturated the database; those results are shown as recorded data.
- It is not private. Anything a signed-in person runs is visible to all visitors as a run, without their name.
- It has no administrator page. To remove someone's access, lower `RUNS_PER_DAY` or rotate `FINTWIN_SESSION_SECRET` (which signs everyone out).
