#!/usr/bin/env bash
# Builds a kubeconfig for the limited "github-actions-deployer" ServiceAccount and prints it
# base64-encoded, ready to paste into the GitHub secret KUBE_CONFIG.
#
# Prerequisites: your current kubectl context is an ADMIN on the target cluster, and
#   kubectl apply -f k8s/namespace.yaml -f k8s/rbac-ci.yaml   has been run.
#
# Usage: ./scripts/generate-ci-kubeconfig.sh [public-api-server-url]
#   The API server URL must be reachable from the internet for GitHub-hosted runners.
set -euo pipefail

NS=cloud-native-app
SECRET=github-actions-deployer-token
SERVER="${1:-$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')}"

TOKEN=$(kubectl -n "$NS" get secret "$SECRET" -o jsonpath='{.data.token}' | base64 -d)
CA=$(kubectl -n "$NS" get secret "$SECRET" -o jsonpath='{.data.ca\.crt}')

[ -n "$TOKEN" ] || { echo "Token not populated yet - wait a few seconds and retry" >&2; exit 1; }

OUT=$(mktemp)
cat > "$OUT" <<KCFG
apiVersion: v1
kind: Config
clusters:
  - name: target
    cluster:
      server: ${SERVER}
      certificate-authority-data: ${CA}
users:
  - name: github-actions-deployer
    user:
      token: ${TOKEN}
contexts:
  - name: ci
    context:
      cluster: target
      user: github-actions-deployer
      namespace: ${NS}
current-context: ci
KCFG

echo "Server in kubeconfig: ${SERVER}" >&2
echo "Verifying access..." >&2
KUBECONFIG="$OUT" kubectl -n "$NS" get deploy >&2 || echo "(verification failed - is the API server reachable from here?)" >&2

echo "----- BASE64 (paste into the KUBE_CONFIG secret) -----" >&2
base64 -w0 "$OUT" 2>/dev/null || base64 "$OUT" | tr -d '\n'
echo
rm -f "$OUT"
