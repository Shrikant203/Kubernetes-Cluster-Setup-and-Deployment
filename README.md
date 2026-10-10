# Kubernetes Cluster Setup and Deployment

## Objective
Understand Kubernetes orchestration and deploy a containerised application on a local cluster created with **Kind** (Minikube is also supported).

## What this project does
1. Creates a 3-node Kind cluster (1 control-plane + 2 workers).
2. Deploys an **nginx** web app from declarative YAML manifests.
3. Verifies pods, Service and endpoints, and tests the app over HTTP.
4. Scales the Deployment 3 → 5 replicas.
5. Deletes a pod to demonstrate **self-healing**.
6. Performs a **rolling update** (`nginx:1.27-alpine` → `nginx:1.27.3-alpine`).
7. Monitors the deployment (rollout status/history, `describe`, logs, events).

## Files
| File | Purpose |
|---|---|
| `kind-config.yaml` | Cluster definition; host port **8080** → NodePort **30080** |
| `k8s/00-namespace.yaml` | Namespace `k8s-demo` |
| `k8s/01-configmap.yaml` | ConfigMap `web-content` (custom `index.html`) |
| `k8s/02-deployment.yaml` | Deployment `web-app`: 3 replicas, readiness/liveness probes, requests/limits, RollingUpdate (maxSurge 1, maxUnavailable 0) |
| `k8s/03-service.yaml` | NodePort Service `web-service` (30080 → 80) |
| `deploy_k8s.py` | Automation: runs every step and saves the real output |
| `Task12_Kubernetes.ipynb` | Notebook version of the same workflow |
| `build_report.py` | Builds the PDF report from the evidence |
| `evidence/` | `run_log.json`, `run_log.txt`, terminal screenshots (PNG), `browser_app.png` |
| `Task12_Cluster_Setup_Report.pdf` | Final report |

## Prerequisites
Docker Desktop (running), `kubectl`, `kind` (`brew install kind kubectl`), Python 3.9+ and `pip install pillow reportlab`.

## How to run
```bash
python deploy_k8s.py                 # or: python deploy_k8s.py --tool minikube
# open http://localhost:8080  → save a screenshot as evidence/browser_app.png
python build_report.py --name "Your Name" --id "Your ID"
open Task12_Cluster_Setup_Report.pdf
```
Cleanup (after submitting): `kind delete cluster --name task12`

## Architecture
```
Browser / curl ──► localhost:8080 ──► NodePort 30080 ──► Service web-service ──► 3 × nginx pods
                       (Kind port mapping)              (selector app=web-app)     (ConfigMap page)
```

## Run result
| Step | Result |
|---|---|
| Cluster | Kind v0.33.0, Kubernetes v1.37.0, 3 nodes |
| Deployment | 3/3 replicas available, Service with 3 endpoints |
| HTTP test | `curl http://localhost:8080` returned the custom "Hello from Kubernetes!" page |
| Scaling | 3 → 5 replicas, 5/5 available |
| Self-healing | Deleted pod `web-app-…-9zb9t`; replacement pod created automatically |
| Rolling update | Image updated to `nginx:1.27.3-alpine`, revision 2, old ReplicaSet scaled to 0 |
| Resource usage | `kubectl top` → *Metrics API not available* (metrics-server not installed – expected) |

## Observations
- The initial `FailedScheduling` warnings were a start-up race: the manifests were applied while the workers were still `NotReady`; the pods were scheduled about a second later.
- Deployment → ReplicaSet → Pods: the image change created a second ReplicaSet (revision 2) and kept the first at 0/0 for rollback.
- The Service load-balances over pod IPs selected by label; replacement pods join automatically.

## Troubleshooting
| Problem | Fix |
|---|---|
| Cannot connect to Docker daemon | Start Docker Desktop and wait until it says *running* |
| Port 8080 already in use | Change `hostPort` in `kind-config.yaml`, delete and recreate the cluster |
| `kubectl top` error | Expected without metrics-server |
