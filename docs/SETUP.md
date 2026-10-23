# Setup Guide – GitHub, GitHub Actions, Docker Hub & Kubernetes

The pipeline code is already in the repository, but **several things can only be done by hand in
the GitHub / Docker Hub / Kubernetes web UIs or CLIs**. Follow the sections in order.

| # | What you do | Where | Needed for |
|---|-------------|-------|-----------|
| 1 | Create the GitHub repository and push the code | GitHub + git | everything |
| 2 | Enable GitHub Actions | GitHub | everything |
| 3 | Create a Docker Hub account + access token | Docker Hub | image push |
| 4 | Add repository **secrets** | GitHub | image push |
| 5 | Provision a Kubernetes cluster | cloud / local | deploy |
| 6 | Create the namespace + CI ServiceAccount | `kubectl` | deploy |
| 7 | Add `KUBE_CONFIG` secret, `DEPLOY_ENABLED` variable, `production` environment | GitHub | deploy |
| 8 | (Recommended) Protect the `main` branch | GitHub | quality gate |
| 9 | Trigger and verify the pipeline | GitHub + `kubectl` | – |

> **Minimum viable setup:** sections 1–4 give you test → build → push to Docker Hub, plus an
> end-to-end test on a throw-away **kind** cluster inside the runner. Sections 5–7 add the
> deployment to *your* cluster.

---

## 0. Prerequisites

Install locally: `git`, `docker`, `kubectl`, and (optional, for local tests) Python 3.13.
You need accounts on **GitHub** and **Docker Hub** (both free).

---

## 1. Create the GitHub repository and push the code

1. Go to <https://github.com/new>.
2. **Repository name:** `cloud-native-cicd` (any name works).
3. Visibility: **Public** is simplest (unlimited free Actions minutes, and Docker Hub public images
   need no pull secret). Private also works – see the note in section 5.
4. Do **not** tick "Add README / .gitignore / license" (the project already has them).
5. Click **Create repository**, then from the project folder:

```bash
cd cloud-native-cicd
git init -b main
git add .
git commit -m "Initial commit: services, Dockerfiles, k8s manifests, CI/CD pipeline"
git remote add origin https://github.com/<YOUR-GITHUB-USER>/cloud-native-cicd.git
git push -u origin main
```

> The first push will start the pipeline. It is **expected** to fail at the push step until you
> finish sections 3–4 – the `test` and `e2e` jobs should already pass.

Confirm that `.github/workflows/ci-cd.yml` is visible in the repo on GitHub.

---

## 2. Enable GitHub Actions

Actions is on by default for new repositories, but verify it:

1. Repository → **Settings → Actions → General**.
2. **Actions permissions:** select **Allow all actions and reusable workflows**
   (the workflow uses `actions/*`, `docker/*`, `helm/kind-action` and `azure/setup-kubectl`).
   If your organisation restricts actions, allow those publishers.
3. **Workflow permissions:** leave **Read repository contents permission** (the workflow declares
   its own `permissions: contents: read`).
4. Click **Save**.
5. Open the **Actions** tab. If you see "Workflows aren't being run on this repository", click
   **I understand my workflows, go ahead and enable them**.

> **Forked repo?** Actions are disabled on forks until you enable them in the Actions tab.

---

## 3. Create a Docker Hub account, repositories and access token

1. Sign up / log in at <https://hub.docker.com>. Remember your **username** (lower-case, **not** your e-mail).
2. **Repositories are created automatically on first push**, so creating them is optional. To create
   them manually: **Repositories → Create repository** → names
   `course-service` and `registration-service`, visibility **Public**.
3. Create an access token (never use your password in CI):
   1. Avatar → **Account settings → Personal access tokens** (older UI: *Security → New Access Token*).
   2. **Generate new token**.
   3. Description: `github-actions-cicd`.
   4. Access permissions: **Read & Write** (minimum needed to push).
   5. **Generate**, then **copy the token now** – it is shown only once.

---

## 4. Add GitHub repository secrets

Repository → **Settings → Secrets and variables → Actions → Secrets tab → New repository secret**.

| Secret name | Value |
|-------------|-------|
| `DOCKERHUB_USERNAME` | your Docker Hub username |
| `DOCKERHUB_TOKEN` | the access token from section 3 |

Names are **case-sensitive** and must match exactly. Secrets cannot be read back after saving; to
change one, just add it again.

Images will be published as:

```
docker.io/<DOCKERHUB_USERNAME>/course-service:latest | sha-<short-commit> | <version>
docker.io/<DOCKERHUB_USERNAME>/registration-service:latest | sha-<short-commit> | <version>
```

✅ **Checkpoint:** Actions tab → open the latest run → **Re-run all jobs**. The `build` jobs should
now log in, push, and you should see the two repositories with new tags on Docker Hub.

---

## 5. Provision a Kubernetes cluster (for the deploy job)

GitHub-hosted runners run on the public internet, so the cluster's **API server must be reachable
from the internet**. Pick one option:

| Option | Reachable by GitHub-hosted runners? | Notes |
|--------|-------------------------------------|-------|
| **A. Managed cloud cluster** (GKE, EKS, AKS, DigitalOcean, Linode…) | ✅ yes | Most realistic. Many offer a free tier/credits. |
| **B. k3s on a small VPS** | ✅ yes (open port 6443) | Cheapest. `curl -sfL https://get.k3s.io \| sh -` |
| **C. Minikube / kind / Docker Desktop on your laptop** | ❌ not directly | Use a **self-hosted runner** (see below) or a tunnel. |

### Option C – local cluster with a self-hosted runner
1. Start the cluster, e.g. `minikube start` (or `kind create cluster`).
2. Repository → **Settings → Actions → Runners → New self-hosted runner**; follow the commands
   shown (download, `./config.sh --url … --token …`, `./run.sh`) on the **same machine**.
3. In `.github/workflows/ci-cd.yml`, change the `deploy` job to `runs-on: self-hosted`.
4. In that case you do not need a `KUBE_CONFIG` secret if the runner user's `~/.kube/config` already
   points at the cluster – replace the "Configure kubeconfig" step with nothing.
5. ⚠️ Self-hosted runners execute workflow code from your repo: only use them on **private**
   repositories or with strict approval for fork PRs.

> **Private Docker Hub repositories?** The cluster then needs credentials to pull:
> ```bash
> kubectl -n cloud-native-app create secret docker-registry dockerhub-pull \
>   --docker-username=<user> --docker-password=<token> --docker-email=<email>
> ```
> and add `imagePullSecrets: [{name: dockerhub-pull}]` under `spec.template.spec` in
> `k8s/course.yaml` and `k8s/registration.yaml`. (Not needed for public images.)

Verify your own access works before continuing: `kubectl get nodes`.

---

## 6. Create the namespace and a least-privilege CI identity

Run as a **cluster admin** from the repository root:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/rbac-ci.yaml
```

This creates the `cloud-native-app` namespace and a `github-actions-deployer` ServiceAccount that
can manage Deployments/Services **only in that namespace** (it cannot touch the rest of the cluster).

Now generate a kubeconfig for that account:

```bash
./scripts/generate-ci-kubeconfig.sh
# if the API server URL in your kubeconfig is private (e.g. https://127.0.0.1:...),
# pass the public one explicitly:
./scripts/generate-ci-kubeconfig.sh https://<PUBLIC-API-SERVER-HOST>:6443
```

The script prints a single long **base64 string** on stdout. Copy it (it is a credential – do not
commit or share it).

> If the script says the token is empty, wait a few seconds and run it again.
> If `kubectl … get deploy` in the script's verification step fails, the server URL is not reachable
> from your current network – fix that before moving on.

---

## 7. Add the deployment secret, variable and environment

All in **Settings** of your GitHub repository:

1. **Secrets and variables → Actions → Secrets → New repository secret**
   * Name `KUBE_CONFIG` → value: the base64 string from section 6.
2. **Secrets and variables → Actions → Variables tab → New repository variable**
   * Name `DEPLOY_ENABLED` → value `true`.
   * (This switch lets the pipeline run without a cluster; the `deploy` job is skipped until it is `true`.)
3. **Environments → New environment** → name it exactly `production` → **Configure environment**.
   * *Optional but recommended:* tick **Required reviewers** and add yourself. Every deploy will
     then pause for a manual **Approve and deploy** click.
   * *Optional:* **Deployment branches → Selected branches → `main`**.

---

## 8. (Recommended) Protect the `main` branch

Settings → **Branches → Add branch ruleset** (or *Add classic branch protection rule*):

* Branch name pattern: `main`
* ✅ Require a pull request before merging
* ✅ Require status checks to pass → add **`Lint & unit test (course)`**,
  **`Lint & unit test (registration)`** and **`E2E on kind cluster`**
  (status checks only appear in the search box after the workflow has run at least once)
* ✅ Require branches to be up to date before merging

Now nothing reaches `main` – and therefore nothing gets deployed – unless it passes the pipeline.

---

## 9. Trigger and verify the pipeline

```bash
git checkout -b feature/test-pipeline
# make a small change, e.g. add a course to course/app.py (and a test!)
git commit -am "Add CS04 course"
git push -u origin feature/test-pipeline
```

1. Open a **Pull Request** → the `test`, `build` (build only, no push) and `e2e` jobs run.
2. **Merge** the PR → on `main`, the images are pushed and the `deploy` job rolls them out.
3. Watch it live: **Actions** tab → the run → click each job to see logs.

Verify the deployment on the cluster:

```bash
kubectl -n cloud-native-app get pods,svc
kubectl -n cloud-native-app get deploy -o wide        # image tag should be sha-<your commit>
kubectl -n cloud-native-app rollout history deployment/registration

# reach the app
kubectl -n cloud-native-app port-forward svc/registration 5000:5000 &
BASE_URL=http://localhost:5000 ./scripts/smoke-test.sh
# or via NodePort: http://<node-ip>:30080/courses   (minikube: `minikube service registration -n cloud-native-app --url`)
```

Create a release tag to also publish a semver image tag:

```bash
git tag v1.0.0 && git push origin v1.0.0     # pushes images tagged 1.0.0
```

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `build` fails: `unauthorized` / `denied: requested access to the resource is denied` | Wrong `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN`, token is Read-only, or secret names mis-typed. |
| `build` fails: `Username required` | Secrets missing – you pushed before section 4 (re-run after adding them). |
| `deploy` job doesn't appear / is skipped | `DEPLOY_ENABLED` variable isn't exactly `true`, or the run isn't a push to `main`. |
| `deploy` fails: `Secret KUBE_CONFIG is not set` | Section 7 step 1 missed (secret names are case-sensitive). |
| `Unable to connect to the server: dial tcp … i/o timeout` | API server not reachable from the internet / firewall blocks 6443 / kubeconfig points to a private IP. See section 5. |
| `forbidden: User "system:serviceaccount:…" cannot …` | RBAC missing; re-apply `k8s/rbac-ci.yaml`. |
| Pods in `ImagePullBackOff` | Image/tag not on Docker Hub, wrong username, or private repo without pull secret (section 5 note). |
| Pods in `CrashLoopBackOff` | `kubectl -n cloud-native-app logs deploy/registration`. |
| `rollout status` times out | `kubectl -n cloud-native-app describe pod -l app=registration` and check the Events section. |
| `e2e` fails but local works | Open the "Dump cluster state on failure" step output. |
| Workflow doesn't start at all | Actions disabled (section 2), or YAML error – GitHub shows it on the workflow file page. |

## Security notes

* Use an access token (not your password) and scope it Read & Write.
* The CI ServiceAccount is namespace-scoped. Rotate by deleting and re-creating the
  `github-actions-deployer-token` Secret, then regenerating the kubeconfig.
* Secrets are not passed to workflows triggered by PRs from forks; that's why PR runs only *build*.
* Images are tagged with the commit SHA, so every deployment is traceable and rollback-able.
  (`latest` is only a convenience tag – manifests deploy the SHA tag.)
