package org.batfish.vendor.huawei.grammar;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Set;
import java.util.function.Consumer;
import org.batfish.common.Warnings;
import org.batfish.datamodel.ConcreteInterfaceAddress;
import org.batfish.datamodel.IntegerSpace;
import org.batfish.datamodel.Ip;
import org.batfish.datamodel.Prefix;
import org.batfish.grammar.silent_syntax.SilentSyntaxCollection;
import org.batfish.grammar.silent_syntax.SilentSyntaxCollection.SilentSyntaxElem;
import org.batfish.vendor.huawei.representation.HuaweiConfiguration;
import org.batfish.vendor.huawei.representation.HuaweiModel;
import org.batfish.vendor.huawei.representation.HuaweiStatement;
import org.batfish.vendor.huawei.representation.HuaweiStructureType;
import org.batfish.vendor.huawei.representation.HuaweiStructureUsage;

/** Context-sensitive command validation and extraction for Huawei VRP views. */
final class HuaweiFeatureExtractor {
  private final HuaweiConfiguration _c;
  private final Warnings _w;
  private final HuaweiPolicyExtractor _policy;
  private final SilentSyntaxCollection _silent;

  // Explicit out-of-scope view heads. Unknown commands in target views do not use this list.
  private static final Set<String> IGNORED_ROOTS =
      Set.of(
          "aaa",
          "acl",
          "bfd",
          "bmp",
          "clock",
          "dcn",
          "dhcp",
          "diffserv",
          "dot1x-template",
          "ecc",
          "ifit",
          "info-center",
          "l2tp-group",
          "license",
          "lldp",
          "local-aaa-server",
          "netconf",
          "nqa",
          "ntp-service",
          "ops",
          "pki",
          "return",
          "sbfd",
          "security",
          "service-instance-group",
          "service-template",
          "sftp",
          "slot",
          "snetconf",
          "snmp-agent",
          "soc",
          "ssh",
          "stelnet",
          "te",
          "telemetry",
          "traffic",
          "tunnel-policy",
          "user-interface",
          "vlan",
          "warranty",
          "FTP");

  HuaweiFeatureExtractor(HuaweiConfiguration c, Warnings w, SilentSyntaxCollection silent) {
    _c = c;
    _w = w;
    _policy = new HuaweiPolicyExtractor(c, w);
    _silent = silent;
  }

  void extract(HuaweiStatement root) {
    children(root, this::root);
  }

  private void children(HuaweiStatement parent, Consumer<HuaweiStatement> handler) {
    for (HuaweiStatement s : parent.getChildren()) {
      try {
        handler.accept(s);
      } catch (IllegalArgumentException | IndexOutOfBoundsException e) {
        unknown(s, "Malformed Huawei VRP command");
      }
    }
  }

  private void root(HuaweiStatement s) {
    String t = s.getText();
    String[] a = s.words();
    if (a[0].equals("sysname")) {
      _c.setHostname(a[1]);
    } else if (a[0].equals("router") && a[1].equals("id")) {
      _c.setRouterId(Ip.parse(a[2]));
    } else if (a[0].equals("interface")) {
      HuaweiModel.Interface i =
          _c.getInterfaces().computeIfAbsent(a[1], k -> new HuaweiModel.Interface());
      i.name = a[1];
      i.bridge |= t.endsWith(" mode l2");
      define(HuaweiStructureType.INTERFACE, a[1], s);
      children(s, child -> iface(child, i));
      if (i.aggregateId != null) {
        i.aggregate = "Eth-Trunk" + i.aggregateId;
        ref(HuaweiStructureType.INTERFACE, i.aggregate, HuaweiStructureUsage.AGGREGATE_MEMBER, s);
      }
    } else if (t.startsWith("ip dcn vpn-instance ")) {
      _c.setDcnVpn(a[3]);
      define(HuaweiStructureType.VPN, a[3], s);
    } else if (t.startsWith("ip vpn-instance ")) {
      HuaweiModel.Vpn vpn = _c.getVpns().computeIfAbsent(a[2], k -> new HuaweiModel.Vpn());
      define(HuaweiStructureType.VPN, a[2], s);
      children(s, child -> vpn(child, vpn));
    } else if (t.startsWith("ip route-static bfd ")) {
      _c.getRetained().add(s);
    } else if (t.startsWith("ip route-static ")) {
      staticRoute(s);
    } else if (t.startsWith("ipv6 route-static ")) {
      _c.getIpv6StaticRoutes().add(s);
    } else if (a[0].equals("isis")) {
      HuaweiModel.Isis isis = new HuaweiModel.Isis();
      isis.id = Integer.parseInt(a[1]);
      String vpn = option(a, "vpn-instance");
      if (vpn != null) {
        isis.vrf = vpn;
        ref(HuaweiStructureType.VPN, vpn, HuaweiStructureUsage.INTERFACE_ISIS, s);
      }
      _c.getIsisProcesses().put(isis.id, isis);
      define(HuaweiStructureType.ISIS, a[1], s);
      children(s, child -> isis(child, isis));
    } else if (a[0].equals("bgp")) {
      HuaweiModel.Bgp bgp = new HuaweiModel.Bgp();
      bgp.asn = Long.parseLong(a[1]);
      bgp.instance = a.length > 3 ? a[3] : "default";
      define(HuaweiStructureType.BGP, bgp.instance, s);
      _c.getBgpProcesses().add(bgp);
      new HuaweiBgpExtractor(_c, _w).extract(s, bgp);
    } else if (a[0].equals("route-policy")) {
      HuaweiModel.Policy policy =
          _c.getPolicies().computeIfAbsent(a[1], k -> new HuaweiModel.Policy());
      HuaweiModel.PolicyNode node = new HuaweiModel.PolicyNode();
      node.permit = a[2].equals("permit");
      policy.nodes.put(Integer.parseInt(a[4]), node);
      define(HuaweiStructureType.ROUTE_POLICY, a[1], s);
      children(
          s,
          child -> {
            try {
              _policy.node(child, node);
            } catch (IllegalArgumentException | IndexOutOfBoundsException e) {
              node.unsupported = true;
              unknown(child, "Malformed route-policy command; node disabled");
            }
          });
    } else if (t.startsWith("ip ip-prefix ")) {
      _policy.prefixList(s);
    } else if (t.startsWith("ip ipv6-prefix ")) {
      _c.getIpv6PrefixLists().computeIfAbsent(a[2], k -> new ArrayList<>()).add(s);
      define(HuaweiStructureType.IPV6_PREFIX_LIST, a[2], s);
    } else if (t.startsWith("ip community-filter ") || t.startsWith("ip extcommunity-filter ")) {
      _policy.communityList(s);
    } else if (t.startsWith("ip rd-filter ")) {
      _c.getRdLists().computeIfAbsent(a[2], k -> new ArrayList<>()).add(s);
      define(HuaweiStructureType.RD_LIST, a[2], s);
    } else if (t.startsWith("evpn vpn-instance ")
        || t.startsWith("evpl instance ")
        || a[0].equals("bridge-domain")) {
      HuaweiModel.Evpn evpn = new HuaweiModel.Evpn();
      if (a[0].equals("bridge-domain")) {
        _c.getBridgeDomains().put(Integer.valueOf(a[1]), evpn);
        define(HuaweiStructureType.BRIDGE_DOMAIN, a[1], s);
      } else {
        (a[0].equals("evpn") ? _c.getEvpnInstances() : _c.getEvpls()).put(a[2], evpn);
        evpn.encapsulation = a.length > 3 ? a[3] : null;
        define(a[0].equals("evpn") ? HuaweiStructureType.EVPN : HuaweiStructureType.EVPL, a[2], s);
      }
      children(s, child -> evpn(child, evpn));
    } else if (t.equals("segment-routing ipv6")) {
      _c.getRetained().add(s);
      children(s, this::srv6);
    } else if (t.equals("segment-routing")) {
      _c.getRetained().add(s);
    } else if (a[0].equals("ospf") || a[0].equals("ospfv3")) {
      _c.getOspfProcesses().add(s);
    } else if (IGNORED_ROOTS.contains(a[0])
        || knownRootCommand(t)
        || starts(
            t,
            "set neid",
            "ip dcn",
            "undo FTP",
            "undo web-auth-server",
            "undo user-security-policy",
            "undo dcn",
            "undo telnet",
            "undo ftp",
            "undo icmp",
            "undo lldp",
            "undo ntp-service",
            "undo snmp-agent",
            "undo ssh",
            "undo sftp",
            "undo stelnet",
            "undo snetconf",
            "undo web-manager",
            "undo local-aaa-server",
            "undo hwtacacs",
            "undo nqa",
            "undo radius",
            "undo pnp",
            "undo diffserv",
            "evpn source-address")
        || t.equals("evpn")) {
      silent(s);
    } else {
      unknown(s, "Unrecognized Huawei VRP top-level command");
    }
  }

  private static boolean starts(String text, String... prefixes) {
    return Arrays.stream(prefixes).anyMatch(p -> text.equals(p) || text.startsWith(p + " "));
  }

  private static boolean knownRootCommand(String t) {
    return starts(
            t,
            "ip ttl-expires",
            "ip unreachables",
            "ip load-sharing",
            "ip icmp",
            "ip netstream",
            "ipv6 netstream",
            "arp",
            "l2vpn enable",
            "mpls lsr-id",
            "mpls ldp",
            "mpls te",
            "mpls rsvp-te")
        || t.equals("mpls");
  }

  private void iface(HuaweiStatement s, HuaweiModel.Interface i) {
    String t = s.getText();
    String[] a = s.words();
    validateInterfaceCommand(a);
    if (a[0].equals("description")) {
      i.description = t.substring(12);
    } else if (t.equals("shutdown")) {
      i.shutdown = true;
    } else if (t.equals("undo shutdown")) {
      i.shutdown = false;
    } else if (t.startsWith("ip address ")) {
      i.addresses.add(ConcreteInterfaceAddress.create(Ip.parse(a[2]), mask(a[3])));
    } else if (t.startsWith("ipv6 address ")) {
      i.ipv6Addresses.add(a[2]);
      i.retained.add(s);
    } else if (t.startsWith("ip binding vpn-instance ")) {
      i.vrf = a[3];
      ref(HuaweiStructureType.VPN, i.vrf, HuaweiStructureUsage.INTERFACE_VPN, s);
    } else if (a[0].equals("mtu")) {
      i.mtu = Integer.valueOf(a[1]);
    } else if (t.startsWith("ip mtu ")) {
      i.mtu = Integer.valueOf(a[2]);
    } else if (t.startsWith("vlan-type dot1q ")) {
      i.vlan = Integer.valueOf(a[2]);
    } else if (t.equals("portswitch") || t.equals("undo portswitch")) {
      i.bridge = t.equals("portswitch");
    } else if (t.startsWith("port link-type ")) {
      i.trunk = a[2].equals("trunk");
    } else if (t.startsWith("port default vlan ")) {
      i.accessVlan = Integer.parseInt(a[3]);
    } else if (t.startsWith("port trunk allow-pass vlan ")) {
      i.allowedVlans =
          a[4].equals("all")
              ? IntegerSpace.of(new org.batfish.datamodel.SubRange(1, 4094))
              : IntegerSpace.parse(
                  String.join(",", Arrays.copyOfRange(a, 4, a.length)).replace(",to,", "-"));
    } else if (t.startsWith("eth-trunk ")) {
      i.aggregateId = Integer.valueOf(a[1]);
    } else if (t.startsWith("isis enable ")) {
      i.isis = Integer.valueOf(a[2]);
      ref(HuaweiStructureType.ISIS, a[2], HuaweiStructureUsage.INTERFACE_ISIS, s);
    } else if (t.startsWith("isis ipv6 enable ")) {
      i.ipv6Isis = Integer.valueOf(a[3]);
      ref(HuaweiStructureType.ISIS, a[3], HuaweiStructureUsage.INTERFACE_ISIS, s);
    } else if (t.startsWith("isis circuit-level ")) {
      i.isisLevel = a[2];
    } else if (t.startsWith("isis circuit-type ")) {
      i.isisP2p = a[2].equals("p2p");
    } else if (t.startsWith("isis cost ")) {
      long cost = Long.parseLong(a[2]);
      if (a.length == 3) {
        i.isisCost = cost;
      } else if (a[3].equals("level-1")) {
        i.isisCostL1 = cost;
      } else if (a[3].equals("level-2")) {
        i.isisCostL2 = cost;
      } else {
        unknown(s, "Unknown ISIS cost level");
      }
    } else if (t.equals("isis silent")) {
      i.isisSilent = true;
    } else if (t.equals("isis bfd enable")) {
      i.isisBfd = true;
    } else if (t.startsWith("evpn binding vpn-instance ")) {
      i.evpn = a[3];
      ref(HuaweiStructureType.EVPN, i.evpn, HuaweiStructureUsage.INTERFACE_EVPN, s);
    } else if (a[0].equals("bridge-domain")) {
      i.bridgeDomain = Integer.valueOf(a[1]);
      ref(HuaweiStructureType.BRIDGE_DOMAIN, a[1], HuaweiStructureUsage.INTERFACE_EVPN, s);
    } else if (a[0].equals("evpl")) {
      i.evpl = Integer.valueOf(a[2]);
      ref(HuaweiStructureType.EVPL, a[2], HuaweiStructureUsage.INTERFACE_EVPN, s);
    } else if (t.startsWith("isis bfd min-tx-interval ")) {
      i.bfdMinimumInterval = Long.valueOf(a[3]);
    } else if (starts(
        t,
        "ipv6 enable",
        "encapsulation",
        "rewrite",
        "binding tunnel",
        "mode",
        "isis ipv6 cost",
        "isis ipv6 bfd",
        "isis prefix-sid",
        "isis adjacency-sid",
        "isis small-hello",
        "ipv6 mtu",
        "ipv6 forwarding",
        "source",
        "destination")) {
      i.retained.add(s);
    } else if (starts(
        t,
        "speed",
        "duplex",
        "dcn",
        "undo dcn",
        "statistic",
        "traffic-policy",
        "hold-up",
        "ppp authentication-mode",
        "mpls",
        "qos",
        "ospf",
        "packet-filter",
        "ptp",
        "flow-interval",
        "network-slice",
        "mode channel-bandwidth",
        "loopback",
        "statistics",
        "synchronous",
        "traffic-statistic",
        "ip netstream",
        "ipv6 netstream",
        "bandwidth",
        "tunnel-protocol",
        "tunnel",
        "keepalive")) {
      silent(s);
    } else {
      unknown(s, "Unrecognized interface command");
    }
  }

  private void vpn(HuaweiStatement s, HuaweiModel.Vpn vpn) {
    String t = s.getText();
    String[] a = s.words();
    if (a[0].equals("route-distinguisher")) {
      vpn.rd = a[1];
    } else if (a[0].equals("ipv4-family") || a[0].equals("ipv6-family")) {
      HuaweiModel.Evpn af =
          vpn.families.computeIfAbsent(a[0].substring(0, 4), k -> new HuaweiModel.Evpn());
      children(s, child -> evpn(child, af));
    } else if (starts(
        t, "description", "routing-table limit", "tnl-policy", "vpn-target", "ttl-mode")) {
      vpn.retained.add(s);
      if (a[0].equals("vpn-target")) {
        evpn(s, vpn.families.computeIfAbsent("instance", k -> new HuaweiModel.Evpn()));
      }
    } else {
      unknown(s, "Unrecognized VPN instance command");
    }
  }

  private void staticRoute(HuaweiStatement s) {
    String[] a = s.words();
    int p = 2;
    HuaweiModel.StaticRoute r = new HuaweiModel.StaticRoute();
    if (a[p].equals("vpn-instance")) {
      r.vrf = a[++p];
      p++;
    }
    r.network = Prefix.create(Ip.parse(a[p]), mask(a[p + 1]));
    p += 2;
    if (a[p].equals("vpn-instance")) {
      r.nextHopVrf = a[++p];
      p++;
    }
    if (p < a.length && Ip.tryParse(a[p]).isPresent()) {
      r.nextHop = Ip.parse(a[p++]);
    } else if (p < a.length
        && !Set.of("preference", "tag", "description", "public").contains(a[p])) {
      r.nextHopInterface = a[p++];
      if (p < a.length && Ip.tryParse(a[p]).isPresent()) {
        r.nextHop = Ip.parse(a[p++]);
      }
    }
    while (p < a.length) {
      switch (a[p++]) {
        case "preference" -> r.preference = Integer.parseInt(a[p++]);
        case "tag" -> r.tag = Long.parseLong(a[p++]);
        case "description" -> {
          r.description = String.join(" ", Arrays.copyOfRange(a, p, a.length));
          p = a.length;
        }
        case "public" -> r.nextHopVrf = "default";
        case "vpn-instance" -> r.nextHopVrf = a[p++];
        default -> {
          unknown(s, "Unrecognized static route option");
          return;
        }
      }
    }
    if (r.nextHop == null && r.nextHopInterface == null && r.nextHopVrf == null) {
      throw new IllegalArgumentException("missing next hop");
    }
    if (!r.vrf.equals("default")) {
      ref(HuaweiStructureType.VPN, r.vrf, HuaweiStructureUsage.STATIC_VPN, s);
    }
    if (r.nextHopVrf != null && !r.nextHopVrf.equals("default")) {
      ref(HuaweiStructureType.VPN, r.nextHopVrf, HuaweiStructureUsage.STATIC_VPN, s);
    }
    if (r.nextHopInterface != null && !r.nextHopInterface.equalsIgnoreCase("NULL0")) {
      ref(
          HuaweiStructureType.INTERFACE,
          r.nextHopInterface,
          HuaweiStructureUsage.STATIC_INTERFACE,
          s);
    }
    _c.getStaticRoutes().add(r);
  }

  private void isis(HuaweiStatement s, HuaweiModel.Isis isis) {
    String t = s.getText();
    String[] a = s.words();
    if (a[0].equals("network-entity")) {
      isis.net = a[1];
    } else if (a[0].equals("is-level")) {
      isis.level = a[1];
    } else if (t.equals("bfd all-interfaces enable")) {
      isis.bfd = true;
    } else if (t.startsWith("bfd all-interfaces min-tx-interval ")) {
      isis.bfdMinimumInterval = Long.valueOf(a[3]);
    } else if (a[0].equals("set-overload")) {
      isis.overload = !t.contains("on-startup");
      isis.retained.add(s);
    } else if (a[0].equals("address-family")) {
      // VRP's documented IPv6 commands are directly in the IS-IS view. Never
      // interpret another dialect's unsupported nested AF children as IPv4 commands.
      isis.retained.add(s);
      unknown(s, "Unsupported Huawei ISIS address-family view; subtree not converted");
    } else if (t.startsWith("ipv6 enable")) {
      isis.ipv6 = true;
      isis.retained.add(s);
    } else if (t.startsWith("ipv6 import-route ")) {
      isis.ipv6 = true;
      isis.retained.add(s);
      referencePolicy(a, s);
    } else if (a[0].equals("import-route")) {
      isis.retained.add(s);
      if (a.length > 1) {
        isis.redistribution.remove(a[1]);
      }
      HuaweiModel.Redistribution rule = HuaweiRedistributionExtractor.parse(a, false);
      if (rule.supported()) {
        isis.redistribution.put(a[1], rule);
      } else {
        _c.getUnsupportedRedistributions()
            .add(new HuaweiModel.UnsupportedRedistribution("ISIS", s));
      }
      referencePolicy(a, s);
    } else if (starts(
        t,
        "ipv6",
        "bfd",
        "bgp-ls",
        "traffic-eng",
        "frr",
        "cost-style",
        "is-name",
        "flash-flood",
        "timer",
        "mpls te",
        "distribute bgp-ls",
        "segment-routing",
        "fast-reroute",
        "maximum load-balancing",
        "advertise",
        "multi-topology",
        "import-route")) {
      isis.retained.add(s);
      referenceLocator(a, s);
    } else {
      unknown(s, "Unrecognized ISIS command");
    }
  }

  private void evpn(HuaweiStatement s, HuaweiModel.Evpn evpn) {
    String t = s.getText();
    String[] a = s.words();
    evpn.retained.add(s);
    if (a[0].equals("route-distinguisher")) {
      evpn.rd = a[1];
    } else if (a[0].equals("vpn-target")) {
      if (a[2].equals("both") || a[2].equals("import-extcommunity")) {
        evpn.importTargets.add(a[1]);
      }
      if (a[2].equals("both") || a[2].equals("export-extcommunity")) {
        evpn.exportTargets.add(a[1]);
      }
    } else if (t.startsWith("evpn binding vpn-instance ")) {
      evpn.vpn = a[3];
      ref(HuaweiStructureType.EVPN, a[3], HuaweiStructureUsage.INTERFACE_EVPN, s);
    } else if (t.startsWith("local-service-id ")) {
      evpn.localServiceId = Long.valueOf(a[1]);
      evpn.remoteServiceId = Long.valueOf(a[3]);
    } else if (t.startsWith("segment-routing ipv6 locator ")) {
      evpn.locator = a[3];
      referenceLocator(a, s);
    } else if (starts(
        t,
        "description",
        "mac",
        "vpn frr",
        "ip frr",
        "apply-label",
        "import route-policy",
        "restrain",
        "statistics",
        "evpn mpls routing-enable",
        "segment-routing ipv6 traffic-engineering",
        "segment-routing ipv6 traffic-engineer",
        "tnl-policy",
        "routing-table limit",
        "ttl-mode")) {
      referencePolicy(a, s);
    } else {
      unknown(s, "Unrecognized EVPN command");
    }
  }

  private void srv6(HuaweiStatement s) {
    String[] a = s.words();
    if (a[0].equals("locator")) {
      HuaweiModel.Locator locator = new HuaweiModel.Locator();
      locator.prefix = option(a, "ipv6-prefix");
      if (a.length > 4) {
        locator.prefixLength = Integer.valueOf(a[4]);
      }
      String staticLength = option(a, "static");
      if (staticLength != null) {
        locator.staticLength = Integer.valueOf(staticLength);
      }
      _c.getLocators().put(a[1], locator);
      define(HuaweiStructureType.LOCATOR, a[1], s);
      children(
          s,
          child -> {
            String[] words = child.words();
            if (!words[0].equals("opcode")
                || words.length < 3
                || !Set.of(
                        "end",
                        "end-x",
                        "end-op",
                        "end-dt4",
                        "end-dt6",
                        "end-dt46",
                        "end-dt2u",
                        "end-dt2m",
                        "end-dt2ul",
                        "end-am",
                        "end-as",
                        "end-ad")
                    .contains(words[2])) {
              unknown(child, "Unrecognized SRv6 locator command");
              return;
            }
            HuaweiModel.Opcode opcode = new HuaweiModel.Opcode();
            opcode.function = words[2];
            opcode.interfaceName = option(words, "interface");
            opcode.vpn = option(words, "vpn-instance");
            String bd = option(words, "bridge-domain");
            if (bd != null) {
              opcode.bridgeDomain = Integer.valueOf(bd);
              ref(HuaweiStructureType.BRIDGE_DOMAIN, bd, HuaweiStructureUsage.SRV6_LOCATOR, child);
            }
            opcode.retained.add(child);
            locator.opcodes.put(words[1], opcode);
            String iface = option(words, "interface");
            if (iface != null) {
              ref(HuaweiStructureType.INTERFACE, iface, HuaweiStructureUsage.EVPN_AC, child);
            }
            String vpn = option(words, "vpn-instance");
            if (vpn != null) {
              ref(HuaweiStructureType.VPN, vpn, HuaweiStructureUsage.SRV6_LOCATOR, child);
            }
            children(
                child,
                nested -> {
                  if (!starts(nested.getText(), "encapsulation eth")) {
                    unknown(nested, "Unrecognized SRv6 opcode command");
                  }
                });
          });
    } else if (!starts(
        s.getText(),
        "sr-te",
        "path-mtu",
        "segment-list",
        "srv6-te",
        "encapsulation",
        "reduce-srh",
        "traffic-engineering",
        "srv6-policy",
        "srv6-te-policy",
        "srv6-policy-group",
        "path",
        "mapping-policy")) {
      unknown(s, "Unrecognized SRv6 command");
    }
  }

  private static int mask(String value) {
    if (value.contains(".")) {
      Ip ip = Ip.parse(value);
      require(ip.isValidNetmask1sLeading());
      return ip.numSubnetBits();
    }
    return range(value, 0, 32);
  }

  private static void require(boolean valid) {
    if (!valid) {
      throw new IllegalArgumentException("Invalid Huawei VRP command arguments");
    }
  }

  private static int range(String value, int min, int max) {
    int number = Integer.parseInt(value);
    require(number >= min && number <= max);
    return number;
  }

  private static void validateInterfaceCommand(String[] a) {
    String text = String.join(" ", a);
    if (text.startsWith("ip address ")) {
      require(a.length == 4 || a.length == 5 && a[4].equals("sub"));
      Ip.parse(a[2]);
      mask(a[3]);
    } else if (text.startsWith("ip binding vpn-instance ")) {
      require(a.length == 4);
    } else if (text.startsWith("isis circuit-level ")) {
      require(a.length == 3 && Set.of("level-1", "level-2", "level-1-2").contains(a[2]));
    } else if (text.startsWith("isis circuit-type ")) {
      require(a.length == 3 && a[2].equals("p2p"));
    } else if (text.startsWith("isis enable ")) {
      require(a.length == 3);
      range(a[2], 1, 65535);
    } else if (text.startsWith("isis ipv6 enable ")) {
      require(a.length == 4);
      range(a[3], 1, 65535);
    } else if (text.startsWith("isis cost ") || text.startsWith("isis ipv6 cost ")) {
      int offset = a[1].equals("ipv6") ? 3 : 2;
      require(
          a.length == offset + 1
              || a.length == offset + 2 && Set.of("level-1", "level-2").contains(a[offset + 1]));
      range(a[offset], 0, 16777215);
    } else if (text.startsWith("port link-type ")) {
      require(a.length == 3 && Set.of("access", "trunk").contains(a[2]));
    } else if (text.startsWith("eth-trunk ")) {
      require(a.length == 2);
      range(a[1], 0, 65535);
    } else if (text.startsWith("vlan-type dot1q ")) {
      require(a.length == 3);
      range(a[2], 1, 4094);
    } else if (text.startsWith("port default vlan ")) {
      require(a.length == 4);
      range(a[3], 1, 4094);
    } else if (a[0].equals("mtu") || text.startsWith("ip mtu ")) {
      int offset = a[0].equals("mtu") ? 1 : 2;
      require(a.length == offset + 1);
      range(a[offset], 1, 65535);
    }
  }

  private static String option(String[] a, String key) {
    for (int i = 0; i < a.length - 1; i++) {
      if (a[i].equals(key)) {
        return a[i + 1];
      }
    }
    return null;
  }

  private void referencePolicy(String[] a, HuaweiStatement s) {
    String policy = option(a, "route-policy");
    if (policy != null) {
      ref(HuaweiStructureType.ROUTE_POLICY, policy, HuaweiStructureUsage.REDISTRIBUTION_POLICY, s);
    }
  }

  private void referenceLocator(String[] a, HuaweiStatement s) {
    String locator = option(a, "locator");
    if (locator != null) {
      ref(HuaweiStructureType.LOCATOR, locator, HuaweiStructureUsage.SRV6_LOCATOR, s);
    }
  }

  private void define(HuaweiStructureType type, String name, HuaweiStatement s) {
    _c.defineSingleLineStructure(type, name, s.getLine());
  }

  private void ref(
      HuaweiStructureType type, String name, HuaweiStructureUsage usage, HuaweiStatement s) {
    _c.referenceStructure(type, name, usage, s.getLine());
  }

  private void unknown(HuaweiStatement s, String reason) {
    _c.setUnrecognized(true);
    // Do not copy configuration values (which may be credentials) into diagnostics.
    _w.getParseWarnings()
        .add(new Warnings.ParseWarning(s.getLine(), s.words()[0], "huawei", reason));
  }

  private void silent(HuaweiStatement s) {
    _silent.addElement(new SilentSyntaxElem("huawei_ignored", s.getLine(), s.words()[0]));
    s.getChildren().forEach(this::silent);
  }
}
