#!/usr/bin/env python3
"""Task 12 - Kubernetes cluster setup and deployment (Kind or Minikube).

Usage:
    python deploy_k8s.py --tool kind        # default
    python deploy_k8s.py --tool minikube
    python deploy_k8s.py --cleanup          # delete cluster afterwards

Every command and its real output is saved to evidence/run_log.json and
evidence/run_log.txt, and rendered as terminal-style PNG screenshots in
evidence/ (needs: pip install pillow).
"""
import argparse, json, shutil, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
EVID = ROOT / "evidence"
EVID.mkdir(exist_ok=True)
NS = "k8s-demo"
CLUSTER = "task12"
LOG = []  # list of {"title", "cmd", "output"}


def run(title, cmd, check=True, timeout=600):
    """Run a shell command, print + record its output."""
    print(f"\n=== {title} ===\n$ {cmd}")
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    out = (p.stdout + p.stderr).strip()
    print(out)
    LOG.append({"title": title, "cmd": cmd, "output": out, "rc": p.returncode})
    if check and p.returncode != 0:
        save_logs()
        sys.exit(f"Command failed ({p.returncode}): {cmd}")
    return out


def save_logs():
    (EVID / "run_log.json").write_text(json.dumps(LOG, indent=2))
    with open(EVID / "run_log.txt", "w") as f:
        for e in LOG:
            f.write(f"=== {e['title']} ===\n$ {e['cmd']}\n{e['output']}\n\n")
    try:
        render_screenshots()
    except ImportError:
        print("Pillow not installed - skipping PNG rendering (pip install pillow)")


def render_screenshots():
    """Render each recorded command as a terminal-style PNG."""
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for f in ("DejaVuSansMono.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
              "Menlo.ttc", "Consolas.ttf", "Courier New.ttf"):
        try:
            font = ImageFont.truetype(f, 15); break
        except OSError:
            continue
    font = font or ImageFont.load_default()
    for i, e in enumerate(LOG, 1):
        lines = [f"$ {e['cmd']}"] + e["output"].splitlines()[:45]
        lines = [l[:130] for l in lines]
        w = max(900, 9 * max(len(l) for l in lines) + 40)
        h = 40 + 21 * len(lines)
        img = Image.new("RGB", (w, h), (24, 26, 31))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, w, 26], fill=(50, 54, 62))
        d.text((10, 5), e["title"], fill=(220, 220, 220), font=font)
        for n, l in enumerate(lines):
            d.text((14, 36 + 21 * n), l, fill=(120, 220, 140) if n == 0 else (225, 225, 225), font=font)
        img.save(EVID / f"{i:02d}_{e['title'].lower().replace(' ', '_').replace('/', '-')[:40]}.png")


def create_cluster(tool):
    if tool == "kind":
        existing = run("List kind clusters", "kind get clusters", check=False)
        if CLUSTER not in existing.split():
            run("Create Kind cluster (1 control-plane + 2 workers)",
                f"kind create cluster --name {CLUSTER} --config kind-config.yaml --wait 120s")
        run("Set kubectl context", f"kubectl config use-context kind-{CLUSTER}")
    else:
        run("Start Minikube cluster", f"minikube start -p {CLUSTER} --nodes=2 --driver=docker")
        run("Set kubectl context", f"kubectl config use-context {CLUSTER}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", choices=["kind", "minikube"], default="kind")
    ap.add_argument("--cleanup", action="store_true", help="delete the cluster at the end")
    a = ap.parse_args()

    # 1. Prerequisites
    for t in ("docker", "kubectl", a.tool):
        if not shutil.which(t):
            sys.exit(f"'{t}' not found in PATH - install it first (see README.md)")
    run("Tool versions", f"docker --version && kubectl version --client && {a.tool} version")

    # 2. Cluster setup
    create_cluster(a.tool)
    run("Cluster info", "kubectl cluster-info")
    run("Cluster nodes", "kubectl get nodes -o wide")

    # 3. Deploy manifests
    run("Apply manifests", "kubectl apply -f k8s/")
    run("Wait for rollout", f"kubectl rollout status deployment/web-app -n {NS} --timeout=180s")

    # 4. Verify pods and services
    run("Get pods", f"kubectl get pods -n {NS} -o wide")
    run("Get deployment, service, endpoints", f"kubectl get deploy,svc,endpoints,cm -n {NS}")
    run("Describe service", f"kubectl describe svc web-service -n {NS}")

    # 5. Functional test
    if a.tool == "kind":
        url = "http://localhost:8080"
    else:
        url = run("Minikube service URL", f"minikube service web-service -n {NS} -p {CLUSTER} --url").splitlines()[-1]
    time.sleep(3)
    try:
        body = urllib.request.urlopen(url, timeout=10).read().decode()
        LOG.append({"title": "HTTP test", "cmd": f"curl {url}", "output": body.strip(), "rc": 0})
        print(f"\nHTTP test OK ({url}):\n{body}")
    except Exception as ex:
        LOG.append({"title": "HTTP test", "cmd": f"curl {url}", "output": f"FAILED: {ex}", "rc": 1})
        print("HTTP test failed:", ex)

    # 6. Scaling + self-healing
    run("Scale to 5 replicas", f"kubectl scale deployment/web-app --replicas=5 -n {NS}")
    run("Wait after scale", f"kubectl rollout status deployment/web-app -n {NS} --timeout=120s")
    run("Pods after scaling", f"kubectl get pods -n {NS}")
    victim = run("Pick a pod", f"kubectl get pods -n {NS} -o jsonpath='{{.items[0].metadata.name}}'").strip("'")
    run("Delete a pod (self-healing test)", f"kubectl delete pod {victim} -n {NS}")
    run("Wait for recovery", f"kubectl rollout status deployment/web-app -n {NS} --timeout=120s")
    run("Pods after self-healing", f"kubectl get pods -n {NS}")

    # 7. Rolling update
    run("Rolling update to nginx 1.27.3-alpine",
        f"kubectl set image deployment/web-app nginx=nginx:1.27.3-alpine -n {NS}")
    run("Rollout status", f"kubectl rollout status deployment/web-app -n {NS} --timeout=180s")
    run("Rollout history", f"kubectl rollout history deployment/web-app -n {NS}")

    # 8. Monitoring deployment status
    run("Deployment details", f"kubectl describe deployment web-app -n {NS}")
    run("Pod logs", f"kubectl logs deployment/web-app -n {NS} --tail=10")
    run("Recent events", f"kubectl get events -n {NS} --sort-by=.lastTimestamp")
    run("Resource usage (needs metrics-server)", f"kubectl top pods -n {NS}", check=False)

    save_logs()
    print(f"\nDone. Logs + screenshots saved in {EVID}")

    if a.cleanup:
        if a.tool == "kind":
            subprocess.run(f"kind delete cluster --name {CLUSTER}", shell=True)
        else:
            subprocess.run(f"minikube delete -p {CLUSTER}", shell=True)


if __name__ == "__main__":
    main()
