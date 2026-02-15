"""K8sGhost CLI — Find and reclaim zombie Kubernetes resources."""
import json
import click
from scanner import KubeScanner

FREE_LIMIT = 5


def format_table(zombies, pro=False):
    if not zombies:
        return "\n✅ No zombie resources found. Your cluster is clean!\n"
    shown = zombies if pro else zombies[:FREE_LIMIT]
    lines = ["", "🧟 K8sGhost Scan Results", "=" * 78,
             f"{'KIND':<16} {'NAMESPACE':<14} {'NAME':<22} {'REASON':<22} {'AGE':>4} {'$/MO':>7}",
             "-" * 78]
    for z in shown:
        lines.append(f"{z.kind:<16} {z.namespace:<14} {z.name:<22} "
                     f"{z.reason:<22} {z.age_days:>3}d ${z.monthly_cost:>6.1f}")
    total = sum(z.monthly_cost for z in zombies)
    lines.append("-" * 78)
    lines.append(f"💀 {len(zombies)} zombie resources | 💸 ${total:,.2f}/month reclaimable")
    if not pro and len(zombies) > FREE_LIMIT:
        hidden = len(zombies) - FREE_LIMIT
        lines.append(f"\n🔒 {hidden} more zombies hidden. Set K8SGHOST_PRO_KEY to unlock.")
        lines.append("   Get your key → https://k8sghost.dev/pro")
    lines.append("")
    return "\n".join(lines)


@click.command()
@click.option("--namespace", "-n", default=None, help="Scan specific namespace only")
@click.option("--kubeconfig", default=None, help="Path to kubeconfig file")
@click.option("--context", default=None, help="Kubernetes context to use")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
@click.option("--pro-key", envvar="K8SGHOST_PRO_KEY", default=None, hidden=True)
def scan(namespace, kubeconfig, context, fmt, pro_key):
    """Scan Kubernetes cluster for zombie resources and estimate reclaimable cost."""
    pro = bool(pro_key and len(pro_key) >= 8)
    scanner = KubeScanner(kubeconfig=kubeconfig, context=context)
    zombies = scanner.scan_all(namespace)
    if fmt == "json":
        items = zombies if pro else zombies[:FREE_LIMIT]
        data = [{"kind": z.kind, "name": z.name, "namespace": z.namespace,
                 "reason": z.reason, "monthly_cost": z.monthly_cost,
                 "age_days": z.age_days} for z in items]
        click.echo(json.dumps({"zombies": data, "total_monthly": sum(z.monthly_cost for z in zombies),
                               "count": len(zombies), "pro": pro}, indent=2))
    else:
        click.echo(format_table(zombies, pro))


if __name__ == "__main__":
    scan()
