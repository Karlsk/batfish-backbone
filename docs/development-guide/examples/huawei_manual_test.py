"""Local-only Huawei acceptance checks; requires a freshly built Batfish service.

Run from any directory; --output must be a new directory outside the checkout.
Private captures are copied byte-for-byte, never cleaned or printed. Query answers
and snapshots stay in that directory and must not be published.
"""

import argparse
import hashlib
import importlib.metadata
import json
import logging
import re
import shutil
import time
import uuid
from pathlib import Path

from pybatfish.client.session import Session
from pybatfish.datamodel.route import BgpRoute


class CheckFailure(RuntimeError):
    """A failed acceptance invariant with a controlled, non-sensitive reason."""


def require(condition, safe_reason):
    """Enforce an invariant even when Python assertions are optimized away."""
    if not condition:
        raise CheckFailure(safe_reason)


def node(n, ibgp=False, h3c=False):
    """Synthetic fixture, intentionally independent of real device addresses."""
    other = 3 - n
    asn = 65001 if ibgp else 65000 + n
    remote = 65001 if ibgp else 65000 + other
    interface = "GigabitEthernet1/0/1" if h3c else "GigabitEthernet0/0/1"
    customer = "GigabitEthernet1/0/2" if h3c else "GigabitEthernet0/0/2"
    bgp = (
        f""" ip vpn-instance blue
  peer 198.51.100.{other} as-number {remote}
  address-family ipv4 unicast
   import-route direct
   import-route static
   peer 198.51.100.{other} enable
   peer 198.51.100.{other} advertise-community
   peer 198.51.100.{other} route-policy EXPORT export"""
        if h3c
        else f""" ipv4-family vpn-instance blue
  peer 198.51.100.{other} as-number {remote}
  peer 198.51.100.{other} advertise-community
  peer 198.51.100.{other} route-policy EXPORT export
  import-route direct
  import-route static"""
    )
    # H3C has an explicit IPv4 ISIS family; VRP enables IPv4 on the process.
    family = " address-family ipv4 unicast\n" if h3c else ""
    return f"""#BATFISH_FORMAT: {'h3c_comware' if h3c else 'huawei_vrp'}
sysname r{n}
ip vpn-instance blue
#
interface LoopBack0
 ip address 10.0.0.{n} 32
 isis enable 10
#
interface {interface}
 undo shutdown
 ip address 192.0.2.{n} 30
 isis enable 10
 isis circuit-type p2p
#
interface {customer}
 undo shutdown
 ip binding vpn-instance blue
 ip address 198.51.100.{n} 30
#
interface LoopBack1
 ip binding vpn-instance blue
 ip address 172.16.{n}.1 32
#
isis 10
 is-level level-2
 network-entity 49.0001.0000.0000.000{n}.00
{family}#
bgp {asn}
 router-id 10.0.0.{n}
{bgp}
#
route-policy EXPORT permit node 10
 apply cost 77
 apply community 65000:77 additive
#
ip route-static vpn-instance blue 203.0.{n}.0 24 NULL0
ip route-static vpn-instance blue 198.19.{n}.0 24 NULL0 preference 75
ip route-static 198.51.100.0 30 vpn-instance blue
return
"""


class Checks:
    def __init__(self, args):
        self.repo = Path(__file__).resolve().parents[3]
        self.output = args.output.resolve()
        if self.output.is_relative_to(self.repo):
            raise ValueError("--output must be outside the checkout (private data)")
        self.output.mkdir(parents=True, exist_ok=False)
        self.bf = Session(host="127.0.0.1", port=args.port)
        self.network = "huawei-manual-" + uuid.uuid4().hex[:12]
        self.bf.set_network(self.network)
        self.results = []

    def record(self, step, **data):
        row = {"step": step, **data}
        self.results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)

    def query(self, name, label=None, **kwargs):
        start = time.monotonic()
        frame = getattr(self.bf.q, name)(**kwargs).answer().frame()
        # initIssues may contain source commands; never persist or print them.
        if name != "initIssues":
            target = self.output / f"{self.bf.snapshot}-{label or name}.json"
            target.write_text(frame.to_json(orient="records", indent=2, default_handler=str))
        self.record(
            f"{self.bf.snapshot}/{label or name}",
            rows=len(frame),
            seconds=round(time.monotonic() - start, 2),
        )
        return frame

    def initialize(self, name, *, captures=None, synthetic=None):
        configs = self.output / ("input-" + name) / "configs"
        configs.mkdir(parents=True)
        for filename, source in (captures or {}).items():
            target = configs / filename
            shutil.copyfile(source, target)
            require(
                hashlib.sha256(source.read_bytes()).digest()
                == hashlib.sha256(target.read_bytes()).digest(),
                "Raw capture copy changed bytes",
            )
        for filename, text in (synthetic or {}).items():
            (configs / filename).write_text(text)
        self.bf.init_snapshot(str(configs.parent), name=name, overwrite=False)
        status = self.query("fileParseStatus")
        require(len(status) == len(captures or synthetic), "Unexpected parse-status row count")
        require(set(status.Status) == {"PASSED"}, "Snapshot did not fully parse")
        return status

    def issues(self, *, mixed=False, synthetic=False, unusable_sources=None):
        frame = self.query("initIssues")
        counts = {}
        unusable_source_summaries = 0
        allowed = (
            "Huawei ISIS:",
            "Huawei IPv6 retained, not simulated:",
            "Huawei EVPN/MPLS/SRv6 retained, not simulated:",
            "Huawei route-policy:",
            "Huawei OSPF retained, not simulated:",
            "Huawei BGP operational limitations",
        )
        h3c = (
            "H3C ISIS:",
            "H3C IPv6 retained, not simulated:",
            "H3C EVPN/MPLS/SRv6 retained, not simulated:",
            "H3C route-policy:",
            "H3C additional BGP instances retained, not converted:",
            "H3C BGP operational limitations",
        )
        for _, row in frame.iterrows():
            require(row.Type == "Convert warning (redflag)", "Unexpected parse/init issue")
            require(isinstance(row.Details, str), "Conversion warning details missing")
            matches = [p for p in allowed + (h3c if mixed else ()) if row.Details.startswith(p)]
            require(len(matches) == 1, "Unexpected conversion warning category")
            prefix = matches[0]
            require(
                not synthetic or prefix.startswith("H3C EVPN/"),
                "Unexpected synthetic conversion warning",
            )
            if unusable_sources is not None and row.Details.startswith(
                f"Huawei BGP operational limitations: {unusable_sources} peers have unusable "
                "source interfaces;"
            ):
                unusable_source_summaries += 1
            counts[prefix] = counts.get(prefix, 0) + 1
        if unusable_sources is not None:
            require(
                unusable_source_summaries == 1,
                "Missing or duplicate unusable-source summary",
            )
        self.record(f"{self.bf.snapshot}/warning-categories", categories=counts)
        return counts

    def boundaries(self, sessions):
        for name in ("vxlanVniProperties", "evpnL3VniProperties", "evpnRib"):
            require(self.query(name).empty, "Fabricated EVPN/VNI objects")
        require("Address_Families" in sessions.columns, "BGP session address families missing")
        require(
            not any("EVPN" in str(families).upper() for families in sessions.Address_Families),
            "Fabricated EVPN BGP session",
        )

    def real(self, pair=False):
        captures = {"r2": self.repo / "docs/configuration/NJ-SCT-R02"}
        if pair:
            captures["r1"] = self.repo / "docs/configuration/NJ_SCT_R1"
        status = self.initialize("raw-pair" if pair else "raw-r2", captures=captures)
        expected = {"HUAWEI_VRP", "H3C_COMWARE"} if pair else {"HUAWEI_VRP"}
        require(set(status.File_Format) == expected, "Unexpected raw configuration format")
        warnings = self.issues(mixed=pair, unusable_sources=3)
        require("Huawei ISIS:" in warnings, "Missing Huawei ISIS limitation summary")
        nodes = self.query("nodeProperties", properties="Configuration_Format,VRFs")
        # Select the node by format, not by a potentially sensitive hostname literal.
        candidates = nodes[nodes.Configuration_Format.astype(str).str.upper() == "HUAWEI_VRP"]
        require(len(candidates) == 1, "Huawei node missing or ambiguous")
        name = str(candidates.iloc[0].Node)
        selector = "/^" + re.escape(name) + "$/"
        interfaces = self.query("interfaceProperties", nodes=selector)
        require(len(interfaces) == 263, "Unexpected Huawei interface count")
        require(len(candidates.iloc[0].VRFs) == 59, "Unexpected Huawei VRF count")
        peers = self.query("bgpPeerConfiguration", nodes=selector)
        require(len(peers) == 40, "Unexpected Huawei IPv4 BGP peer count")
        routes = self.query("routes", nodes=selector)
        require("connected" in set(routes.Protocol), "Huawei connected routes missing")
        statics = routes[routes.Protocol == "static"]
        require(not statics.empty, "Huawei installed static routes missing")
        require(
            set(statics.Admin_Distance).issubset({60, 120, 123, 125}),
            "Unexpected Huawei installed static preference",
        )
        self.record(
            f"{self.bf.snapshot}/route-counts", protocols=routes.Protocol.value_counts().to_dict()
        )
        # No assertion that remote sessions establish: the captures omit external nodes.
        sessions = self.query("bgpSessionStatus", nodes=selector)
        if not pair:
            require(len(sessions) == 40, "Unexpected isolated Huawei BGP session count")
            require(
                set(sessions.Established_Status) == {"NOT_COMPATIBLE"},
                "Unexpected isolated Huawei BGP session status",
            )
        self.record(
            f"{self.bf.snapshot}/session-counts",
            statuses=sessions.Established_Status.value_counts().to_dict(),
        )
        isis_edges = self.query("isisEdges")
        if not pair:
            require(isis_edges.empty, "Unexpected isolated Huawei ISIS edge")
        self.boundaries(sessions)

    def dual(self, ibgp=False, mixed=False):
        name = ("mixed-" if mixed else "huawei-") + ("ibgp" if ibgp else "ebgp")
        self.initialize(name, synthetic={"r1": node(1, ibgp), "r2": node(2, ibgp, mixed)})
        self.issues(mixed=mixed, synthetic=True)
        peers = self.query("bgpPeerConfiguration")
        require(len(peers) == 2, "Unexpected synthetic configured BGP peer count")
        sessions = self.query("bgpSessionStatus")
        require(len(sessions) == 2, "Unexpected synthetic BGP session count")
        require(
            set(sessions.Established_Status) == {"ESTABLISHED"},
            "Synthetic BGP sessions not established",
        )
        require(
            all(
                {str(family).upper() for family in families} == {"IPV4_UNICAST"}
                for families in sessions.Address_Families
            ),
            "Unexpected synthetic BGP address family",
        )
        require(len(self.query("isisEdges")) == 2, "Unexpected synthetic ISIS edge count")
        routes = self.query("routes", nodes="r1")

        def route(vrf, prefix):
            rows = routes[(routes.VRF == vrf) & (routes.Network == prefix)]
            require(len(rows) == 1, "Expected one selected synthetic route")
            return rows.iloc[0]

        require(route("default", "10.0.0.2/32").Protocol == "isisL2", "ISIS route missing")
        require(
            route("default", "10.0.0.2/32").Admin_Distance == 15,
            "Unexpected ISIS preference",
        )
        require(
            str(route("default", "198.51.100.0/30").Next_Hop) == "vrf blue",
            "Next-table route not converted",
        )
        require(
            route("blue", "198.51.100.0/30").Protocol == "connected",
            "VPN connected route missing",
        )
        discard = route("blue", "203.0.1.0/24")
        require(
            discard.Admin_Distance == 60 and "discard" in str(discard.Next_Hop).lower(),
            "Default-preference discard route incorrect",
        )
        preferred_discard = route("blue", "198.19.1.0/24")
        require(
            preferred_discard.Admin_Distance == 75
            and "discard" in str(preferred_discard.Next_Hop).lower(),
            "Explicit-preference discard route incorrect",
        )
        learned = route("blue", "203.0.2.0/24")
        protocol = "ibgp" if ibgp else "bgp"
        require(
            learned.Protocol == protocol and learned.Admin_Distance == 255,
            "Learned synthetic BGP route incorrect",
        )
        require(learned.Metric == 77, "Learned synthetic MED incorrect")
        preferred_learned = route("blue", "198.19.2.0/24")
        require(
            preferred_learned.Protocol == protocol and preferred_learned.Admin_Distance == 255,
            "Learned explicit-preference route incorrect",
        )
        require(
            route("blue", "172.16.2.1/32").Protocol == protocol,
            "Learned synthetic loopback route missing",
        )
        bgp = self.query("routes", label="bgp-routes", nodes="r1", vrfs="blue", rib="bgp")
        learned_bgp = bgp[bgp.Network == "203.0.2.0/24"]
        require(not learned_bgp.empty, "Synthetic route missing from BGP RIB")
        require(
            all("65000:77" in row for row in learned_bgp.Communities),
            "Synthetic learned community missing",
        )
        inputs = [
            BgpRoute(
                network="203.0.113.0/24", originatorIp="192.0.2.1", originType="igp",
                protocol="bgp", communities=["65000:10"], metric=0,
            )
        ]
        result = self.query(
            "testRoutePolicies", nodes="r1", policies="EXPORT", direction="out", inputRoutes=inputs
        )
        require(
            len(result) == 1 and result.iloc[0].Action == "PERMIT",
            "Synthetic route policy did not permit",
        )
        require(result.iloc[0].Output_Route.metric == 77, "Synthetic policy MED incorrect")
        require(
            set(result.iloc[0].Output_Route.communities) == {"65000:10", "65000:77"},
            "Synthetic policy communities incorrect",
        )
        self.boundaries(sessions)
        self.record(name, result="PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=19998)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--synthetic-only", action="store_true", help="No private captures required")
    args = parser.parse_args()
    logging.getLogger("pybatfish").setLevel(logging.ERROR)
    checks = Checks(args)
    checks.record("client", version=importlib.metadata.version("pybatfish"), network=checks.network)
    try:
        if not args.synthetic_only:
            checks.real()
            checks.real(pair=True)
        for mixed in (False, True):
            for ibgp in (False, True):
                checks.dual(ibgp=ibgp, mixed=mixed)
        checks.record("acceptance", result="PASS")
    except Exception as error:
        # Do not render API exception text or response bodies containing private source lines.
        checks.record("acceptance", result="FAIL", exception=type(error).__name__)
        raise SystemExit(1) from None
    finally:
        (checks.output / "steps.json").write_text(json.dumps(checks.results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
