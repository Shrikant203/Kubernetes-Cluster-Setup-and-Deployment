#!/usr/bin/env python3
"""Builds Task12_Cluster_Setup_Report.pdf from the YAML files, source code,
real command output (evidence/run_log.json) and screenshots (evidence/*.png).
Run AFTER deploy_k8s.py:   python build_report.py --name "Your Name" --id "Your ID"
Extra screenshots (e.g. browser showing the app) can be dropped in evidence/
as browser_*.png and are added automatically.
"""
import argparse, json, textwrap
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                                Preformatted, Image, Table, TableStyle)
from reportlab.lib import colors
from PIL import Image as PILImage

ROOT = Path(__file__).parent
EV = ROOT / "evidence"
ap = argparse.ArgumentParser()
ap.add_argument("--name", default="<Your Name>")
ap.add_argument("--id", default="<Your ID>")
a = ap.parse_args()

ss = getSampleStyleSheet()
H1, H2, B = ss["Heading1"], ss["Heading2"], ss["BodyText"]
code = ParagraphStyle("code", fontName="Courier", fontSize=7.2, leading=8.8,
                      backColor=colors.HexColor("#f4f4f4"), borderPadding=4)
S = []

def P(t, st=B): S.append(Paragraph(t, st))
def code_block(text, width=105):
    lines = []
    for l in text.splitlines():
        lines += textwrap.wrap(l, width, replace_whitespace=False, drop_whitespace=False) or [""]
    S.append(Preformatted("\n".join(lines), code)); S.append(Spacer(1, 6))
def img(path, maxw=17*cm):
    w, h = PILImage.open(path).size
    s = min(maxw / w, 20*cm / h)
    S.append(Image(str(path), width=w*s, height=h*s))
    S.append(Spacer(1, 6))

# ---------- Title ----------
P("Task 12: Kubernetes Cluster Setup and Deployment", ss["Title"])
P(f"Name: {a.name} &nbsp;&nbsp; ID: {a.id}")
P("Tools: Kubernetes, Kind / Minikube, kubectl, Docker, Python")
S.append(Spacer(1, 10))

P("1. Objective", H1)
P("To understand Kubernetes orchestration and deploy a containerized application "
  "(nginx web server) on a local Kubernetes cluster created with Kind (or Minikube), "
  "using declarative YAML manifests, then verify and monitor the deployment.")

P("2. Architecture", H1)
t = Table([["Object", "Name", "Purpose"],
           ["Cluster", "task12 (Kind: 1 control-plane + 2 workers)", "Local multi-node cluster running in Docker"],
           ["Namespace", "k8s-demo", "Isolates the application's resources"],
           ["ConfigMap", "web-content", "Holds index.html, mounted into the nginx pods"],
           ["Deployment", "web-app (3 replicas)", "Manages pods, rolling updates, self-healing"],
           ["Service", "web-service (NodePort 30080)", "Stable endpoint load-balancing across pods"]],
          colWidths=[3*cm, 6.5*cm, 7.5*cm])
t.setStyle(TableStyle([("GRID", (0,0), (-1,-1), .5, colors.grey),
                       ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#dde6f5")),
                       ("FONTSIZE", (0,0), (-1,-1), 8), ("VALIGN", (0,0), (-1,-1), "TOP")]))
S.append(t)

P("3. Cluster Setup Procedure", H1)
for s in ["Install Docker, kubectl and Kind (or Minikube).",
          "Create the cluster: <font face='Courier'>kind create cluster --name task12 --config kind-config.yaml</font> "
          "(port mapping 30080 -> localhost:8080 exposes the NodePort).",
          "Verify: <font face='Courier'>kubectl cluster-info</font> and <font face='Courier'>kubectl get nodes</font>.",
          "Deploy: <font face='Courier'>kubectl apply -f k8s/</font>.",
          "Verify pods/services, test over HTTP, scale, self-heal, rolling update and monitor "
          "(all automated by <font face='Courier'>deploy_k8s.py</font>)."]:
    P("&bull; " + s)

# ---------- YAML ----------
S.append(PageBreak()); P("4. Kubernetes YAML Files", H1)
for f in ["kind-config.yaml"] + [f"k8s/{p.name}" for p in sorted((ROOT/"k8s").glob("*.yaml"))]:
    P(f, H2); code_block((ROOT/f).read_text())
P("Key configuration points", H2)
for s in ["<b>replicas: 3</b> - desired pod count; the Deployment controller keeps it true.",
          "<b>RollingUpdate (maxSurge 1, maxUnavailable 0)</b> - zero-downtime image upgrades.",
          "<b>readiness/liveness probes</b> - traffic only reaches ready pods; failed pods are restarted.",
          "<b>resources requests/limits</b> - scheduling hints and protection against noisy neighbours.",
          "<b>Service selector app=web-app</b> - routes to all matching pods; NodePort 30080 exposes it outside the cluster.",
          "<b>ConfigMap volume</b> - configuration decoupled from the container image."]:
    P("&bull; " + s)

# ---------- Source ----------
S.append(PageBreak()); P("5. Source Code (deploy_k8s.py)", H1)
code_block((ROOT/"deploy_k8s.py").read_text(), 110)

# ---------- Outputs ----------
S.append(PageBreak()); P("6. Execution Output and Deployment Screenshots", H1)
log = EV / "run_log.json"
if log.exists():
    for i, e in enumerate(json.loads(log.read_text()), 1):
        P(f"6.{i} {e['title']}", H2)
        code_block(f"$ {e['cmd']}\n{e['output'][:3500]}")
    pngs = sorted(EV.glob("[0-9][0-9]_*.png"))
    if pngs:
        S.append(PageBreak()); P("Terminal screenshots", H2)
        for p in pngs:
            P(p.stem.replace("_", " "), ss["Italic"]); img(p)
else:
    P("<b>run_log.json not found - run deploy_k8s.py first, then rebuild this report.</b>")
for p in sorted(EV.glob("browser_*.png")):
    S.append(PageBreak()); P(f"Application in browser: {p.name}", H2); img(p)

# ---------- Observations ----------
S.append(PageBreak()); P("7. Observations and Operational Understanding", H1)
for s in [
 "<b>Declarative model:</b> applying YAML describes the desired state; controllers continuously reconcile actual state to match it.",
 "<b>Deployment -> ReplicaSet -> Pods:</b> the Deployment owns a ReplicaSet which owns the pods; changing the image creates a new ReplicaSet (visible in rollout history).",
 "<b>Self-healing:</b> deleting a pod causes the ReplicaSet to create a replacement automatically so the replica count is restored.",
 "<b>Scaling:</b> <font face='Courier'>kubectl scale</font> changes replicas; the scheduler spreads new pods across worker nodes.",
 "<b>Services:</b> the Service gives a stable virtual IP and load-balances across pod endpoints (see <font face='Courier'>kubectl get endpoints</font>).",
 "<b>Rolling update:</b> with maxUnavailable 0 and readiness probes, pods are replaced one at a time with no downtime.",
 "<b>Monitoring:</b> <font face='Courier'>kubectl get/describe</font>, <font face='Courier'>logs</font>, <font face='Courier'>events</font> and <font face='Courier'>rollout status</font> show deployment health. "
 "<font face='Courier'>kubectl top</font> needs metrics-server (Minikube: <font face='Courier'>minikube addons enable metrics-server</font>)."]:
    P("&bull; " + s)
P("8. Conclusion", H1)
P("A multi-node Kubernetes cluster was created locally, a containerized nginx application was "
  "deployed through declarative manifests, exposed through a Service, verified, scaled, "
  "self-healed and upgraded with a rolling update, demonstrating core Kubernetes orchestration concepts.")

SimpleDocTemplate(str(ROOT/"Task12_Cluster_Setup_Report.pdf"), pagesize=A4,
                  leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
                  title="Task 12 - Kubernetes Cluster Setup and Deployment").build(S)
print("Created Task12_Cluster_Setup_Report.pdf")
