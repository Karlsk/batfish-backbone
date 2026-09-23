package org.batfish.vendor.h3c.grammar;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.function.Consumer;
import org.batfish.common.Warnings;
import org.batfish.datamodel.ConcreteInterfaceAddress;
import org.batfish.datamodel.IntegerSpace;
import org.batfish.datamodel.Ip;
import org.batfish.datamodel.Prefix;
import org.batfish.grammar.silent_syntax.SilentSyntaxCollection;
import org.batfish.grammar.silent_syntax.SilentSyntaxCollection.SilentSyntaxElem;
import org.batfish.vendor.h3c.representation.H3cConfiguration;
import org.batfish.vendor.h3c.representation.H3cModel;
import org.batfish.vendor.h3c.representation.H3cStatement;
import org.batfish.vendor.h3c.representation.H3cStructureType;
import org.batfish.vendor.h3c.representation.H3cStructureUsage;

/** Context-sensitive command validation and extraction for Comware views. */
final class H3cFeatureExtractor {
  private final H3cConfiguration _c;
  private final Warnings _w;
  private final SilentSyntaxCollection _silent;

  // Explicit out-of-scope view heads. Unknown commands in target views do not use this list.
  private static final Set<String> IGNORED_ROOTS =
      Set.of(
          "acl",
          "apn",
          "bfd",
          "bmp",
          "detnetip",
          "detnetoam",
          "domain",
          "explicit-path",
          "flow-route",
          "flowspec",
          "ifit",
          "line",
          "local-user",
          "mpls",
          "nat",
          "network-slice",
          "nqa",
          "ospf",
          "pce-client",
          "public-key",
          "pw-class",
          "qos",
          "role",
          "rtm",
          "telemetry",
          "track",
          "traffic",
          "tunnel-policy",
          "user-group",
          "vlan",
          "version",
          "return",
          "clock",
          "telnet",
          "ssh",
          "sftp",
          "stelnet",
          "ftp",
          "snmp-agent",
          "info-center",
          "lldp",
          "undo",
          "irf",
          "system-working-mode",
          "hardware-resource",
          "scheduler",
          "password-control",
          "ntp-service",
          "forward-path-detection",
          "seu-error",
          "vxlan",
          "sbfd",
          "te",
          "bandwidth-based-sharing",
          "sampler",
          "mirroring-group",
          "flow-interval",
          "password-recovery",
          "tftp-server",
          "security-enhanced");

  H3cFeatureExtractor(H3cConfiguration c, Warnings w, SilentSyntaxCollection silent) {
    _c = c;
    _w = w;
    _silent = silent;
  }

  void extract(H3cStatement root) {
    children(root, this::root);
  }

  private void children(H3cStatement parent, Consumer<H3cStatement> handler) {
    for (H3cStatement s : parent.getChildren()) {
      try {
        handler.accept(s);
      } catch (IllegalArgumentException | IndexOutOfBoundsException e) {
        unknown(s, "Malformed Comware command");
      }
    }
  }

  private void root(H3cStatement s) {
    String t = s.getText();
    String[] a = s.words();
    if (a[0].equals("sysname")) {
      _c.setHostname(a[1]);
    } else if (a[0].equals("router") && a[1].equals("id")) {
      _c.setRouterId(Ip.parse(a[2]));
    } else if (a[0].equals("interface")) {
      H3cModel.Interface i =
          _c.getInterfaces().computeIfAbsent(a[1], k -> new H3cModel.Interface());
      i.name = a[1];
      i.bridge |= i.name.startsWith("Bridge-Aggregation");
      define(H3cStructureType.INTERFACE, a[1], s);
      children(s, child -> iface(child, i));
      if (i.aggregateId != null) {
        i.aggregate = (i.bridge ? "Bridge-Aggregation" : "Route-Aggregation") + i.aggregateId;
        ref(H3cStructureType.INTERFACE, i.aggregate, H3cStructureUsage.AGGREGATE_MEMBER, s);
      }
    } else if (t.startsWith("ip vpn-instance ")) {
      H3cModel.Vpn vpn = _c.getVpns().computeIfAbsent(a[2], k -> new H3cModel.Vpn());
      define(H3cStructureType.VPN, a[2], s);
      children(s, child -> vpn(child, vpn));
    } else if (t.startsWith("ip route-static bfd ")) {
      _c.getRetained().add(s);
    } else if (t.startsWith("ip route-static ")) {
      staticRoute(s);
    } else if (t.startsWith("ipv6 route-static ")) {
      _c.getIpv6StaticRoutes().add(s);
    } else if (a[0].equals("isis")) {
      H3cModel.Isis isis = new H3cModel.Isis();
      isis.id = Integer.parseInt(a[1]);
      _c.getIsisProcesses().put(isis.id, isis);
      define(H3cStructureType.ISIS, a[1], s);
      children(s, child -> isis(child, isis, ""));
    } else if (a[0].equals("bgp")) {
      H3cModel.Bgp bgp = new H3cModel.Bgp();
      bgp.asn = Long.parseLong(a[1]);
      bgp.instance = a.length > 3 ? a[3] : "default";
      define(H3cStructureType.BGP, bgp.instance, s);
      _c.getBgpProcesses().add(bgp);
      children(s, child -> bgp(child, bgp, "default", ""));
    } else if (a[0].equals("route-policy")) {
      H3cModel.Policy policy = _c.getPolicies().computeIfAbsent(a[1], k -> new H3cModel.Policy());
      H3cModel.PolicyNode node = new H3cModel.PolicyNode();
      node.permit = a[2].equals("permit");
      policy.nodes.put(Integer.parseInt(a[4]), node);
      define(H3cStructureType.ROUTE_POLICY, a[1], s);
      children(
          s,
          child -> {
            try {
              policy(child, node);
            } catch (IllegalArgumentException | IndexOutOfBoundsException e) {
              node.unsupported = true;
              unknown(child, "Malformed route-policy command; node disabled");
            }
          });
    } else if (t.startsWith("ip prefix-list ")) {
      prefixList(s);
    } else if (t.startsWith("ipv6 prefix-list ")) {
      _c.getIpv6PrefixLists().computeIfAbsent(a[2], k -> new ArrayList<>()).add(s);
      define(H3cStructureType.IPV6_PREFIX_LIST, a[2], s);
    } else if (t.startsWith("ip community-list ") || t.startsWith("ip extcommunity-list ")) {
      communityList(s);
    } else if (t.startsWith("ip rd-list ")) {
      _c.getRdLists().computeIfAbsent(a[2], k -> new ArrayList<>()).add(s);
      define(H3cStructureType.RD_LIST, a[2], s);
    } else if (a[0].equals("vsi") || a[0].equals("xconnect-group")) {
      boolean vsi = a[0].equals("vsi");
      H3cModel.Evpn evpn = new H3cModel.Evpn();
      (vsi ? _c.getVsis() : _c.getXconnects()).put(a[1], evpn);
      define(vsi ? H3cStructureType.VSI : H3cStructureType.XCONNECT, a[1], s);
      children(s, child -> evpn(child, evpn));
    } else if (t.equals("segment-routing ipv6")) {
      _c.getRetained().add(s);
      children(s, this::srv6);
    } else if (t.equals("segment-routing")) {
      _c.getRetained().add(s);
    } else if (IGNORED_ROOTS.contains(a[0]) || knownRootCommand(t)) {
      silent(s);
    } else {
      unknown(s, "Unrecognized Comware top-level command");
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
        "ip http",
        "ip forwarding",
        "ipv6 forwarding",
        "ipv6 icmpv6",
        "ipv6 netstream",
        "ipv6 unreachables",
        "l2vpn enable",
        "link-aggregation",
        "tcp",
        "udp",
        "fib",
        "rib",
        "arp",
        "mac-address",
        "load",
        "monitor",
        "transceiver",
        "port",
        "switch-mode",
        "system",
        "header",
        "dcn",
        "sflow",
        "grpc",
        "netconf",
        "cwmp",
        "performance-management",
        "session",
        "routing",
        "multicast",
        "igmp",
        "dhcp",
        "dhcpv6",
        "radius",
        "hwtacacs",
        "l2tp",
        "ssl",
        "pki",
        "rmon",
        "stp",
        "ptp",
        "precision-time",
        "network-clock",
        "smartmc",
        "ip fast-forwarding",
        "ipv6 fast-forwarding",
        "ip vpn-instance-mib",
        "ip statistics",
        "ipv6 statistics");
  }

  private void iface(H3cStatement s, H3cModel.Interface i) {
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
      ref(H3cStructureType.VPN, i.vrf, H3cStructureUsage.INTERFACE_VPN, s);
    } else if (a[0].equals("mtu")) {
      i.mtu = Integer.valueOf(a[1]);
    } else if (t.startsWith("ip mtu ")) {
      i.mtu = Integer.valueOf(a[2]);
    } else if (t.startsWith("vlan-type dot1q vid ")) {
      i.vlan = Integer.valueOf(a[3]);
    } else if (t.startsWith("port link-mode ")) {
      i.bridge = a[2].equals("bridge");
    } else if (t.startsWith("port link-type ")) {
      i.trunk = a[2].equals("trunk");
    } else if (t.startsWith("port access vlan ")) {
      i.accessVlan = Integer.parseInt(a[3]);
    } else if (t.startsWith("port trunk permit vlan ")) {
      i.allowedVlans =
          a[4].equals("all")
              ? IntegerSpace.of(new org.batfish.datamodel.SubRange(1, 4094))
              : IntegerSpace.parse(
                  String.join(",", Arrays.copyOfRange(a, 4, a.length)).replace(",to,", "-"));
    } else if (t.startsWith("port link-aggregation group ")) {
      i.aggregateId = Integer.valueOf(a[3]);
    } else if (t.startsWith("isis enable ")) {
      i.isis = Integer.valueOf(a[2]);
      ref(H3cStructureType.ISIS, a[2], H3cStructureUsage.INTERFACE_ISIS, s);
    } else if (t.startsWith("isis ipv6 enable ")) {
      i.ipv6Isis = Integer.valueOf(a[3]);
      ref(H3cStructureType.ISIS, a[3], H3cStructureUsage.INTERFACE_ISIS, s);
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
    } else if (t.startsWith("bfd min-transmit-interval ")) {
      i.bfdMinimumInterval = Long.valueOf(a[2]);
    } else if (t.startsWith("xconnect vsi ")) {
      i.vsi = a[2];
      ref(H3cStructureType.VSI, i.vsi, H3cStructureUsage.INTERFACE_VSI, s);
    } else if (starts(
        t,
        "isis ipv6 cost",
        "isis ipv6 bfd",
        "isis prefix-sid",
        "isis adjacency-sid",
        "isis small-hello",
        "ipv6 mtu",
        "ipv6 forwarding",
        "bfd min-receive-interval",
        "port link-type",
        "port trunk permit",
        "link-aggregation mode",
        "source",
        "destination")) {
      i.retained.add(s);
    } else if (starts(
        t,
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

  private void vpn(H3cStatement s, H3cModel.Vpn vpn) {
    String t = s.getText();
    String[] a = s.words();
    if (a[0].equals("route-distinguisher")) {
      vpn.rd = a[1];
    } else if (a[0].equals("address-family")) {
      H3cModel.Evpn af = vpn.families.computeIfAbsent(a[1], k -> new H3cModel.Evpn());
      children(s, child -> evpn(child, af));
    } else if (starts(
        t, "description", "routing-table limit", "tnl-policy", "vpn-target", "ttl-mode")) {
      vpn.retained.add(s);
      if (a[0].equals("vpn-target")) {
        evpn(s, vpn.families.computeIfAbsent("instance", k -> new H3cModel.Evpn()));
      }
    } else {
      unknown(s, "Unrecognized VPN instance command");
    }
  }

  private void staticRoute(H3cStatement s) {
    String[] a = s.words();
    int p = 2;
    H3cModel.StaticRoute r = new H3cModel.StaticRoute();
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
    } else if (p < a.length && !Set.of("preference", "tag", "description").contains(a[p])) {
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
      ref(H3cStructureType.VPN, r.vrf, H3cStructureUsage.STATIC_VPN, s);
    }
    if (r.nextHopVrf != null) {
      ref(H3cStructureType.VPN, r.nextHopVrf, H3cStructureUsage.STATIC_VPN, s);
    }
    if (r.nextHopInterface != null && !r.nextHopInterface.equalsIgnoreCase("NULL0")) {
      ref(H3cStructureType.INTERFACE, r.nextHopInterface, H3cStructureUsage.STATIC_INTERFACE, s);
    }
    _c.getStaticRoutes().add(r);
  }

  private void isis(H3cStatement s, H3cModel.Isis isis, String family) {
    String t = s.getText();
    String[] a = s.words();
    if (a[0].equals("network-entity")) {
      isis.net = a[1];
    } else if (a[0].equals("is-level")) {
      isis.level = a[1];
    } else if (a[0].equals("set-overload")) {
      isis.overload = !t.contains("on-startup");
      isis.retained.add(s);
    } else if (a[0].equals("address-family")) {
      isis.ipv4 |= a[1].equals("ipv4");
      isis.ipv6 |= a[1].equals("ipv6");
      children(s, child -> isis(child, isis, a[1]));
    } else if (a[0].equals("import-route") && !family.equals("ipv6")) {
      isis.redistribution.put(a[1], option(a, "route-policy"));
      referencePolicy(a, s);
    } else if (starts(
        t,
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

  private void bgp(H3cStatement s, H3cModel.Bgp bgp, String vrfName, String family) {
    String t = s.getText();
    String[] a = s.words();
    H3cModel.BgpVrf vrf = bgp.vrfs.computeIfAbsent(vrfName, k -> new H3cModel.BgpVrf());
    if (t.startsWith("ip vpn-instance ")) {
      ref(H3cStructureType.VPN, a[2], H3cStructureUsage.BGP_VPN, s);
      children(s, child -> bgp(child, bgp, a[2], ""));
    } else if (a[0].equals("address-family")) {
      children(
          s,
          child -> bgp(child, bgp, vrfName, String.join(" ", Arrays.copyOfRange(a, 1, a.length))));
      vrf.retained.add(s);
    } else if (a[0].equals("router-id")) {
      vrf.routerId = Ip.parse(a[1]);
      if (vrfName.equals("default")) {
        bgp.routerId = vrf.routerId;
      }
    } else if (a[0].equals("peer")) {
      validatePeerCommand(a);
      H3cModel.Peer peer = vrf.peers.computeIfAbsent(a[1], k -> new H3cModel.Peer());
      boolean ipv4 = family.isEmpty() || family.equals("ipv4 unicast");
      if (!ipv4) {
        if (!Set.of(
                "as-number",
                "description",
                "connect-interface",
                "ebgp-max-hop",
                "enable",
                "ignore",
                "advertise-community",
                "advertise-ext-community",
                "allow-as-loop",
                "substitute-as",
                "next-hop-local",
                "route-policy",
                "timer",
                "bfd",
                "route-limit",
                "advertise")
            .contains(a[2])) {
          unknown(s, "Unrecognized BGP peer command");
        } else {
          peer.retained.add(s);
          referenceLocator(a, s);
        }
        return;
      }
      switch (a[2]) {
        case "as-number" -> peer.remoteAs = Long.valueOf(a[3]);
        case "description" ->
            peer.description = String.join(" ", Arrays.copyOfRange(a, 3, a.length));
        case "connect-interface" -> {
          peer.sourceInterface = a[3];
          if (a.length > 4 && Ip.tryParse(a[4]).isPresent()) {
            peer.sourceIp = Ip.parse(a[4]);
          }
          ref(H3cStructureType.INTERFACE, a[3], H3cStructureUsage.BGP_SOURCE, s);
        }
        case "ebgp-max-hop" -> peer.multihop = true;
        case "enable" -> peer.enabled = true;
        case "ignore" -> peer.shutdown = true;
        case "advertise-community" -> peer.sendCommunity = true;
        case "advertise-ext-community" -> peer.sendExtendedCommunity = true;
        case "allow-as-loop" -> peer.allowAs = a.length > 3 ? Integer.parseInt(a[3]) : 1;
        case "substitute-as" -> peer.replaceAs = true;
        case "next-hop-local" -> peer.nextHopSelf = true;
        case "route-policy" -> {
          if (a[4].equals("import")) {
            peer.importPolicy = a[3];
          } else if (a[4].equals("export")) {
            peer.exportPolicy = a[3];
          } else {
            throw new IllegalArgumentException("policy direction");
          }
          ref(H3cStructureType.ROUTE_POLICY, a[3], H3cStructureUsage.BGP_POLICY, s);
        }
        case "timer", "bfd", "route-limit", "advertise" -> peer.retained.add(s);
        default -> unknown(s, "Unrecognized BGP peer command");
      }
    } else if (a[0].equals("import-route") && (family.isEmpty() || family.equals("ipv4 unicast"))) {
      vrf.redistribution.put(a[1], option(a, "route-policy"));
      referencePolicy(a, s);
    } else if (a[0].equals("network") && (family.isEmpty() || family.equals("ipv4 unicast"))) {
      int end = a.length > 2 && a[2].equals("mask") ? 4 : 3;
      require(a.length == end || a.length == end + 2 && a[end].equals("route-policy"));
      int length = a.length > 2 && a[2].equals("mask") ? mask(a[3]) : mask(a[2]);
      vrf.networks.put(Prefix.create(Ip.parse(a[1]), length), option(a, "route-policy"));
      referencePolicy(a, s);
    } else if (starts(
        t,
        "pic",
        "segment-routing",
        "import-route",
        "network",
        "preference",
        "timer",
        "graceful-restart",
        "log-peer-change")) {
      vrf.retained.add(s);
      referenceLocator(a, s);
    } else {
      unknown(s, "Unrecognized BGP command");
    }
  }

  private void prefixList(H3cStatement s) {
    String[] a = s.words();
    int p = 3;
    Map<Integer, H3cModel.PrefixEntry> list =
        _c.getPrefixLists().computeIfAbsent(a[2], k -> new TreeMap<>());
    int index = list.keySet().stream().mapToInt(Integer::intValue).max().orElse(0) + 10;
    if (a[p].equals("index")) {
      index = Integer.parseInt(a[++p]);
      p++;
    }
    require(Set.of("permit", "deny").contains(a[p]));
    boolean permit = a[p++].equals("permit");
    Prefix prefix = Prefix.create(Ip.parse(a[p++]), Integer.parseInt(a[p++]));
    int min = prefix.getPrefixLength();
    int max = min;
    while (p < a.length) {
      switch (a[p++]) {
        case "greater-equal" -> {
          min = Integer.parseInt(a[p++]);
          max = 32;
        }
        case "less-equal" -> max = Integer.parseInt(a[p++]);
        default -> throw new IllegalArgumentException("prefix-list option");
      }
    }
    require(min >= prefix.getPrefixLength() && max >= min && max <= 32);
    list.put(index, new H3cModel.PrefixEntry(permit, prefix, min, max));
    define(H3cStructureType.PREFIX_LIST, a[2], s);
  }

  private void communityList(H3cStatement s) {
    String[] a = s.words();
    boolean ext = a[1].equals("extcommunity-list");
    int p = 2;
    boolean regex = a[p].equals("advanced");
    if (a[p].equals("basic") || regex) {
      p++;
    }
    String name = a[p++];
    regex |= !ext && name.matches("1[0-9]{2}");
    Map<Integer, H3cModel.CommunityEntry> entries =
        (ext ? _c.getExtcommunities() : _c.getCommunities())
            .computeIfAbsent(name, k -> new TreeMap<>());
    int index = entries.keySet().stream().mapToInt(Integer::intValue).max().orElse(0) + 10;
    if (a[p].equals("index")) {
      index = Integer.parseInt(a[p + 1]);
      p += 2;
    }
    require(Set.of("permit", "deny").contains(a[p]));
    boolean permit = a[p++].equals("permit");
    require(p < a.length);
    entries.put(
        index,
        new H3cModel.CommunityEntry(permit, regex, List.of(Arrays.copyOfRange(a, p, a.length))));
    define(ext ? H3cStructureType.EXTCOMMUNITY_LIST : H3cStructureType.COMMUNITY_LIST, name, s);
  }

  private void policy(H3cStatement s, H3cModel.PolicyNode node) {
    String t = s.getText();
    String[] a = s.words();
    if (a[0].equals("if-match")) {
      H3cStructureType type;
      String key;
      int p;
      if (t.startsWith("if-match ip address prefix-list ")) {
        type = H3cStructureType.PREFIX_LIST;
        key = "prefix";
        p = 4;
      } else if (t.startsWith("if-match ipv6 next-hop prefix-list ")) {
        type = H3cStructureType.IPV6_PREFIX_LIST;
        key = "ipv6-next-hop";
        p = 4;
      } else if (a[1].equals("community")) {
        type = H3cStructureType.COMMUNITY_LIST;
        key = "community";
        p = a[2].equals("name") ? 3 : 2;
      } else if (a[1].equals("extcommunity")) {
        type = H3cStructureType.EXTCOMMUNITY_LIST;
        key = "extcommunity";
        p = 2;
      } else if (a[1].equals("rd-list")) {
        type = H3cStructureType.RD_LIST;
        key = "rd";
        p = 2;
      } else {
        node.unsupported = true;
        unknown(s, "Unrecognized route-policy match");
        return;
      }
      require(p < a.length);
      List<String> names = node.matches.computeIfAbsent(key, k -> new ArrayList<>());
      for (; p < a.length; p++) {
        if (key.equals("community") && a[p].equals("name")) {
          continue;
        }
        if (a[p].equals("whole-match")) {
          node.unsupported = true;
          _c.getRetained().add(s);
          continue;
        }
        names.add(a[p]);
        ref(type, a[p], H3cStructureUsage.POLICY_MATCH, s);
      }
    } else if (starts(
        t,
        "apply community",
        "apply extcommunity color",
        "apply cost",
        "apply local-preference",
        "apply ip-address next-hop")) {
      try {
        validateAction(a);
      } catch (IllegalArgumentException | IndexOutOfBoundsException e) {
        node.unsupported = true;
        unknown(s, "Malformed route-policy action; node disabled");
        return;
      }
      node.actions.add(s);
    } else {
      node.unsupported = true;
      unknown(s, "Unrecognized route-policy command");
    }
  }

  private void evpn(H3cStatement s, H3cModel.Evpn evpn) {
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
    } else if (t.startsWith("evpn encapsulation ")) {
      evpn.encapsulation = a[2];
      children(s, child -> evpn(child, evpn));
    } else if (t.startsWith("segment-routing ipv6 locator ")) {
      evpn.locator = a[3];
      referenceLocator(a, s);
    } else if (a[0].equals("connection")) {
      H3cModel.Evpn connection = new H3cModel.Evpn();
      evpn.connections.put(a[1], connection);
      children(s, child -> evpn(child, connection));
    } else if (t.startsWith("evpn local-service-id ")) {
      evpn.localServiceId = Long.valueOf(a[2]);
      evpn.remoteServiceId = Long.valueOf(a[4]);
    } else if (t.startsWith("ac interface ")) {
      evpn.attachmentCircuit = a[2];
      ref(H3cStructureType.INTERFACE, a[2], H3cStructureUsage.EVPN_AC, s);
    } else if (a[0].equals("default-color")) {
      evpn.color = Long.valueOf(a[1]);
    } else if (t.startsWith("default color ")) {
      evpn.color = Long.valueOf(a[2]);
    } else if (starts(
        t,
        "description",
        "restrain",
        "statistics",
        "evpn mpls routing-enable",
        "segment-routing ipv6 traffic-engineering",
        "pw-class",
        "tnl-policy",
        "routing-table limit",
        "ttl-mode")) {
      /* retained */
    } else {
      unknown(s, "Unrecognized EVPN command");
    }
  }

  private void srv6(H3cStatement s) {
    String[] a = s.words();
    if (a[0].equals("locator")) {
      _c.getLocators().put(a[1], s);
      define(H3cStructureType.LOCATOR, a[1], s);
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
                        "end-am",
                        "end-as",
                        "end-ad")
                    .contains(words[2])) {
              unknown(child, "Unrecognized SRv6 locator command");
              return;
            }
            String iface = option(words, "interface");
            if (iface != null) {
              ref(H3cStructureType.INTERFACE, iface, H3cStructureUsage.EVPN_AC, child);
            }
            String vpn = option(words, "vpn-instance");
            if (vpn != null) {
              ref(H3cStructureType.VPN, vpn, H3cStructureUsage.SRV6_LOCATOR, child);
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
      throw new IllegalArgumentException("Invalid Comware command arguments");
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
    } else if (text.startsWith("port link-mode ")) {
      require(a.length == 3 && Set.of("bridge", "route").contains(a[2]));
    } else if (text.startsWith("port link-type ")) {
      require(a.length == 3 && Set.of("access", "trunk").contains(a[2]));
    } else if (text.startsWith("port link-aggregation group ")) {
      require(a.length == 4);
      range(a[3], 1, 65535);
    } else if (text.startsWith("vlan-type dot1q vid ")) {
      require(a.length == 4);
      range(a[3], 1, 4094);
    } else if (text.startsWith("port access vlan ")) {
      require(a.length == 4);
      range(a[3], 1, 4094);
    } else if (a[0].equals("mtu") || text.startsWith("ip mtu ")) {
      int offset = a[0].equals("mtu") ? 1 : 2;
      require(a.length == offset + 1);
      range(a[offset], 1, 65535);
    }
  }

  private static void validatePeerCommand(String[] a) {
    require(a.length >= 3);
    switch (a[2]) {
      case "as-number" -> {
        require(a.length == 4);
        long asn = Long.parseLong(a[3]);
        require(asn > 0 && asn <= 0xFFFFFFFFL);
      }
      case "enable",
          "ignore",
          "advertise-community",
          "advertise-ext-community",
          "substitute-as",
          "next-hop-local" ->
          require(a.length == 3);
      case "connect-interface" -> {
        require(a.length == 4 || a.length == 5);
        if (a.length == 5) {
          // IPv6 source addresses are retained but not converted.
          if (a[4].contains(":")) {
            org.batfish.datamodel.Ip6.parse(a[4]);
          } else {
            Ip.parse(a[4]);
          }
        }
      }
      case "ebgp-max-hop", "allow-as-loop" -> {
        require(a.length == 3 || a.length == 4);
        if (a.length == 4) {
          range(a[3], 1, 255);
        }
      }
      case "route-policy" -> require(a.length == 5 && Set.of("import", "export").contains(a[4]));
      case "description" -> require(a.length >= 4);
      default -> {
        /* Known operational options are retained by the view handler. */
      }
    }
  }

  private static void validateAction(String[] a) {
    if (a[1].equals("cost") || a[1].equals("local-preference")) {
      if (a.length != 3 || !a[2].matches("[0-9]+") || Long.parseLong(a[2]) > 0xFFFFFFFFL) {
        throw new IllegalArgumentException("invalid numeric action");
      }
    } else if (a[1].equals("ip-address")) {
      if (a.length != 4 || !a[2].equals("next-hop")) {
        throw new IllegalArgumentException("next hop");
      }
      Ip.parse(a[3]);
    } else if (a[1].equals("community")) {
      int end = a.length - (a[a.length - 1].equals("additive") ? 1 : 0);
      if (end <= 2) {
        throw new IllegalArgumentException("missing community");
      }
      for (int p = 2; p < end; p++) {
        org.batfish.datamodel.bgp.community.StandardCommunity.parse(a[p]);
      }
    } else if (a[1].equals("extcommunity")) {
      int end = a.length - (a[a.length - 1].equals("additive") ? 1 : 0);
      if (end <= 3) {
        throw new IllegalArgumentException("missing color");
      }
      for (int p = 3; p < end; p++) {
        String[] color = a[p].split(":");
        if (color.length > 2 || Long.parseLong(color[color.length - 1]) > 0xFFFFFFFFL) {
          throw new IllegalArgumentException("invalid color");
        }
        if (color.length == 2 && Long.parseLong(color[0], 16) > 0xFFFF) {
          throw new IllegalArgumentException("invalid color flags");
        }
      }
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

  private void referencePolicy(String[] a, H3cStatement s) {
    String policy = option(a, "route-policy");
    if (policy != null) {
      ref(H3cStructureType.ROUTE_POLICY, policy, H3cStructureUsage.REDISTRIBUTION_POLICY, s);
    }
  }

  private void referenceLocator(String[] a, H3cStatement s) {
    String locator = option(a, "locator");
    if (locator != null) {
      ref(H3cStructureType.LOCATOR, locator, H3cStructureUsage.SRV6_LOCATOR, s);
    }
  }

  private void define(H3cStructureType type, String name, H3cStatement s) {
    _c.defineSingleLineStructure(type, name, s.getLine());
  }

  private void ref(H3cStructureType type, String name, H3cStructureUsage usage, H3cStatement s) {
    _c.referenceStructure(type, name, usage, s.getLine());
  }

  private void unknown(H3cStatement s, String reason) {
    _c.setUnrecognized(true);
    // Do not copy configuration values (which may be credentials) into diagnostics.
    _w.getParseWarnings().add(new Warnings.ParseWarning(s.getLine(), s.words()[0], "h3c", reason));
  }

  private void silent(H3cStatement s) {
    _silent.addElement(new SilentSyntaxElem("h3c_ignored", s.getLine(), s.words()[0]));
  }
}
