# 🧟 K8sGhost — Kubernetes Zombie Resource Hunter

**Stop burning money on resources nobody uses.** K8sGhost scans your cluster and finds orphaned PVCs, CrashLoop zombie pods, and unused LoadBalancers — with exact monthly cost estimates.

> First scan typically finds **$500–$5,000/month** in reclaimable waste.

## 🚀 Quick Start

```bash
pip install -r requirements.txt

# Scan current cluster (uses ~/.kube/config)
python main.py

# Scan specific namespace
python main.py -n production

# JSON output for CI/CD
python main.py --format json

# Pro mode (full results)
export K8SGHOST_PRO_KEY="your-license-key"
python main.py
```

## 🔍 What It Detects

| Zombie Type | Detection Method | Typical Waste |
|---|---|---|
| Orphaned PVCs | Not mounted by any pod | $0.10/GB/mo |
| CrashLoop Pods | CrashLoopBackOff status | $30/vCPU + $4/GB RAM |
| Stuck Pods | Terminating > threshold | $30/vCPU + $4/GB RAM |
| Unused LoadBalancers | No healthy endpoints | $18/mo each |

## 💰 Pricing

| Feature | Free | Pro ($99/mo) | Enterprise ($399/mo) |
|---|---|---|---|
| Zombie scan | ✅ (5 results) | ✅ Unlimited | ✅ Unlimited |
| Cost estimation | ✅ Total only | ✅ Per-resource | ✅ Per-resource |
| JSON export | ❌ | ✅ | ✅ |
| CI/CD integration | ❌ | ✅ | ✅ |
| Multi-cluster | ❌ | ❌ | ✅ |
| Slack/PagerDuty alerts | ❌ | ❌ | ✅ |
| Auto-cleanup (dry-run) | ❌ | ❌ | ✅ |
| SSO & audit log | ❌ | ❌ | ✅ |

## 📊 Why Pay?

A single forgotten LoadBalancer costs **$18/month**. One orphaned 100GB PVC costs **$10/month**. A cluster with 50+ microservices typically has **$1,500–$5,000/month** in zombie resources.

K8sGhost Pro at **$99/month** pays for itself on the first scan.

**ROI Example:**
- 3 orphaned PVCs (50GB each): $15/mo
- 5 unused LoadBalancers: $90/mo
- 12 CrashLoop pods: $180/mo
- **Total found: $285/mo → $3,420/year saved**

## 🏗️ CI/CD Integration (Pro)

```yaml
# .github/workflows/k8sghost.yml
- name: K8sGhost Scan
  run: python main.py --format json --pro-key ${{ secrets.K8SGHOST_KEY }}
```

## License

BSL 1.1 — Free for clusters < 20 nodes. Commercial license required for larger deployments.
